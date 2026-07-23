#!/usr/bin/env python3
"""orchestrate: enumerate available subagents into a catalog (stdlib-only).

There is no built-in machine-readable "list agents" command in Claude Code; the
harness injects only name+description into the orchestrator's context. This script
scans agent scopes, parses each definition's YAML frontmatter (without a yaml
dependency), and emits a catalog the orchestrator matches task->agent against on
demand -- including model/tools/isolation the auto-roster lacks. It degrades
gracefully on generic platforms where none of our agents are present.

Default scope (cheap, local only):
    ./.claude/agents/           (project)
    ~/.claude/agents/           (user)

`--include-plugins` restores the broader old behavior: cross-runtime scopes
(`./.agents/agents/`, `./.codex/agents/`) plus a walk of every enabled plugin's
`agents/` dir under `~/.claude/plugins/marketplaces/`. That walk is expensive
(tens of thousands of tokens of JSON on a populated marketplace) so it is
opt-in, not the default.

Usage:
    discover-agents.py [--json] [--role coder] [--include-plugins] [--extra-dir DIR ...]
    --role filters by a coarse heuristic (coder/review/research/...) matched on
    whole words (word-boundary regex) in name+description, so "coder" no
    longer false-positives on "encoder"/"decoder".
Exit 0 always (empty catalog is valid); prints to stdout.

Default (non-JSON) output is one compact line per agent:
    name | model | tools-summary | first sentence of description

JSON output also includes optional ``task_kinds`` and ``capabilities`` arrays.
Definitions without those declarations remain discoverable, but cannot be
selected as capability-matched specialists.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
AGENT_NAME = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
ROUTING_SLUG = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")


def _default_scopes() -> list[str]:
    home = os.path.expanduser("~")
    cwd = os.getcwd()
    return [
        os.path.join(cwd, ".claude", "agents"),
        os.path.join(home, ".claude", "agents"),
    ]


def _plugin_scopes() -> list[str]:
    home = os.path.expanduser("~")
    cwd = os.getcwd()
    candidates = [
        os.path.join(cwd, ".agents", "agents"),
        os.path.join(cwd, ".codex", "agents"),
    ]
    plugroot = os.path.join(home, ".claude", "plugins", "marketplaces")
    if os.path.isdir(plugroot):
        for dirpath, dirnames, _ in os.walk(plugroot):
            if os.path.basename(dirpath) == "agents":
                candidates.append(dirpath)
                dirnames[:] = []
    return candidates


def _scopes(extra: list[str], include_plugins: bool) -> list[str]:
    candidates = list(_default_scopes())
    if include_plugins:
        candidates.extend(_plugin_scopes())
    candidates.extend(extra or [])
    seen, out = set(), []
    for c in candidates:
        rp = os.path.realpath(c)
        if rp not in seen and os.path.isdir(c):
            seen.add(rp)
            out.append(c)
    return out


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Minimal YAML-frontmatter reader: top-level `key: value` scalars plus
    folded/literal block scalars (`>-`, `|`, `>`). Nested mappings (e.g. the
    x-agentic block) are collapsed away. Sufficient for
    name/description/model/tools/isolation without a yaml dependency."""
    m = FRONTMATTER.match(text)
    if not m:
        raise ValueError("missing or unterminated YAML frontmatter")
    fm: dict[str, str] = {}
    lines = m.group(1).splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line.strip() or line[0] in " \t#":
            continue  # skip indented (nested), blank, and comment lines
        if ":" not in line:
            raise ValueError(f"invalid top-level frontmatter line: {line!r}")
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if not key or key in fm:
            raise ValueError(f"invalid or duplicate frontmatter key: {key!r}")
        if val in (">-", "|", ">", ">+", "|-", "|+"):
            # block scalar: gather following more-indented lines
            block = []
            while i < len(lines) and (not lines[i].strip() or lines[i][:1] in " \t"):
                block.append(lines[i].strip())
                i += 1
            fm[key] = " ".join(b for b in block if b).strip()
        else:
            fm[key] = val.strip("'\"")
    return fm


def _metadata_list(fm: dict[str, str], *keys: str) -> list[str]:
    raw = next((fm[key] for key in keys if key in fm), "").strip()
    if not raw:
        return []
    if raw.startswith("[") or raw.endswith("]"):
        if not (raw.startswith("[") and raw.endswith("]")):
            raise ValueError("malformed inline metadata list")
        raw = raw[1:-1]
    values = [value.strip().strip("'\"") for value in raw.split(",")]
    if not values or any(
        not value or not ROUTING_SLUG.fullmatch(value) for value in values
    ):
        raise ValueError("metadata lists require comma-separated lowercase slugs")
    if len(values) != len(set(values)):
        raise ValueError("metadata lists cannot contain duplicates")
    return sorted(values)


def _agent_metadata(text: str) -> dict[str, object]:
    fm = _parse_frontmatter(text)
    name = fm.get("name", "")
    description = fm.get("description", "").strip()
    if not AGENT_NAME.fullmatch(name):
        raise ValueError("agent name must be a lowercase slug")
    if not description:
        raise ValueError("agent description is required")

    model = fm.get("model", "inherit").strip()
    tools = fm.get("tools", "(all)").strip()
    isolation = fm.get("isolation", "").strip()
    if not model or not tools:
        raise ValueError("model and tools cannot be blank")

    return {
        "name": name,
        "description": description,
        "model": model,
        "tools": tools,
        "isolation": isolation,
        "task_kinds": _metadata_list(fm, "task-kinds", "task_kinds", "taskKinds"),
        "capabilities": _metadata_list(fm, "capabilities"),
    }


# Whole words only (matched with \b on both sides) -- explicit conjugations
# instead of bare stems so "coder" doesn't false-positive on "encoder"/
# "decoder" while still covering "implementation"/"migration" style variants.
ROLE_HINTS = {
    "coder": (
        "coder",
        "implement",
        "implementation",
        "refactor",
        "refactoring",
        "migrate",
        "migration",
        "migrating",
    ),
    "review": ("review", "reviewer", "critic", "challenge", "challenger"),
    "research": ("research", "explore", "investigate", "investigation"),
    "merge": ("merge", "gatekeeper", "integrate", "integration", "pull request"),
    "debug": ("debug", "debugger", "diagnose", "diagnostic"),
}


def _role_match(role: str, name: str, desc: str) -> bool:
    hints = ROLE_HINTS.get(role, (role,))
    blob = f"{name} {desc}".lower()
    return any(re.search(rf"\b{re.escape(h)}\b", blob) for h in hints)


def _tools_summary(tools: str) -> str:
    if not tools or tools.strip().lower() in ("(all)", "all tools", "*", "all"):
        return "all"
    names = [t.strip() for t in tools.split(",") if t.strip()]
    if len(names) <= 3:
        return ",".join(names)
    return ",".join(names[:3]) + f"+{len(names) - 3}"


def _first_sentence(desc: str) -> str:
    desc = desc.strip()
    if not desc:
        return ""
    m = re.search(r"(.+?[.!?])(\s|$)", desc)
    return m.group(1) if m else desc


def collect(
    extra: list[str], role: str | None, include_plugins: bool
) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    seen_names: set[str] = set()
    for scope in _scopes(extra, include_plugins):
        for fn in sorted(os.listdir(scope)):
            if not fn.endswith((".md", ".agent.md")):
                continue
            path = os.path.join(scope, fn)
            try:
                with open(path, encoding="utf-8") as fh:
                    metadata = _agent_metadata(fh.read())
            except (OSError, UnicodeDecodeError, ValueError):
                continue
            name = str(metadata["name"])
            if name in seen_names:  # higher-precedence scope already won
                continue
            seen_names.add(name)
            desc = str(metadata["description"])
            if role and not _role_match(role, name, desc):
                continue
            out.append(
                {
                    "name": name,
                    "model": metadata["model"],
                    "tools": metadata["tools"],
                    "isolation": metadata["isolation"],
                    "task_kinds": metadata["task_kinds"],
                    "capabilities": metadata["capabilities"],
                    "scope_dir": scope,
                    "description": desc[:200],
                }
            )
    return sorted(out, key=lambda agent: str(agent["name"]))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="discover-agents.py", description=__doc__)
    p.add_argument("--json", action="store_true")
    p.add_argument("--role")
    p.add_argument(
        "--include-plugins",
        action="store_true",
        help="also scan .agents/.codex dirs + the plugin marketplace (expensive)",
    )
    p.add_argument("--extra-dir", action="append", default=[])
    args = p.parse_args(argv)

    agents = collect(args.extra_dir, args.role, args.include_plugins)
    if args.json:
        import json

        print(json.dumps(agents, indent=2))
        return
    if not agents:
        print("(no agents found in scanned scopes)", file=sys.stderr)
        return
    for a in agents:
        print(
            f"{a['name']} | {a['model']} | {_tools_summary(a['tools'])} | "
            f"{_first_sentence(a['description'])}"
        )


if __name__ == "__main__":
    main()
