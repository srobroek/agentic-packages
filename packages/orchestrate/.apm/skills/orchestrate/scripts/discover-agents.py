#!/usr/bin/env python3
"""orchestrate: enumerate available subagents into a catalog (stdlib-only).

There is no built-in machine-readable "list agents" command in Claude Code; the
harness injects only name+description into the orchestrator's context. This script
scans every agent scope, parses each definition's YAML frontmatter (without a yaml
dependency), and emits a catalog the orchestrator matches task->agent against on
demand -- including model/tools/isolation the auto-roster lacks. It degrades
gracefully on generic platforms where none of our agents are present.

Scopes scanned (Claude), in precedence order, plus Codex/AGENTS equivalents:
    ./.claude/agents/           (project)
    ~/.claude/agents/           (user)
    <plugin>/agents/            (enabled plugins, if discoverable)
    ./.agents/agents/ , ./.codex/agents/   (cross-runtime, best-effort)

Usage:
    discover-agents.py [--json] [--role coder] [--extra-dir DIR ...]
    --role filters by a coarse heuristic (coder/review/research/...) on name+desc.
Exit 0 always (empty catalog is valid); prints to stdout.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _scopes(extra: list[str]) -> list[str]:
    home = os.path.expanduser("~")
    cwd = os.getcwd()
    candidates = [
        os.path.join(cwd, ".claude", "agents"),
        os.path.join(home, ".claude", "agents"),
        os.path.join(cwd, ".agents", "agents"),
        os.path.join(cwd, ".codex", "agents"),
    ]
    # enabled plugin agent dirs (best-effort; ignore if absent)
    plugroot = os.path.join(home, ".claude", "plugins", "marketplaces")
    if os.path.isdir(plugroot):
        for dirpath, dirnames, _ in os.walk(plugroot):
            if os.path.basename(dirpath) == "agents":
                candidates.append(dirpath)
                dirnames[:] = []
    candidates.extend(extra or [])
    seen, out = set(), []
    for c in candidates:
        rp = os.path.realpath(c)
        if rp not in seen and os.path.isdir(c):
            seen.add(rp)
            out.append(c)
    return out


def _parse_frontmatter(text: str) -> dict:
    """Minimal YAML-frontmatter reader: top-level `key: value` scalars plus
    folded/literal block scalars (`>-`, `|`, `>`). Nested mappings (e.g. the
    x-agentic block) are collapsed away. Sufficient for
    name/description/model/tools/isolation without a yaml dependency."""
    m = FRONTMATTER.match(text)
    if not m:
        return {}
    fm: dict[str, str] = {}
    lines = m.group(1).splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line.strip() or line[0] in " \t#" or ":" not in line:
            continue  # skip indented (nested), blank, comment, non-kv lines
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
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


ROLE_HINTS = {
    "coder": ("coder", "implement", "refactor", "migrat"),
    "review": ("review", "critic", "challeng"),
    "research": ("research", "explore", "investigat"),
    "merge": ("merge", "gatekeep", "integrat", "pull request"),
    "debug": ("debug", "diagnos"),
}


def _role_match(role: str, name: str, desc: str) -> bool:
    hints = ROLE_HINTS.get(role, (role,))
    blob = f"{name} {desc}".lower()
    return any(h in blob for h in hints)


def collect(extra: list[str], role: str | None) -> list[dict]:
    out: list[dict] = []
    seen_names: set[str] = set()
    for scope in _scopes(extra):
        for fn in sorted(os.listdir(scope)):
            if not fn.endswith((".md", ".agent.md")):
                continue
            path = os.path.join(scope, fn)
            try:
                with open(path, encoding="utf-8") as fh:
                    fm = _parse_frontmatter(fh.read())
            except (OSError, UnicodeDecodeError):
                continue
            name = fm.get("name") or fn.rsplit(".", 1)[0]
            if name in seen_names:  # higher-precedence scope already won
                continue
            desc = fm.get("description", "")
            if role and not _role_match(role, name, desc):
                continue
            seen_names.add(name)
            out.append({
                "name": name,
                "model": fm.get("model") or "inherit",
                "tools": fm.get("tools") or "(all)",
                "isolation": fm.get("isolation") or "",
                "scope_dir": scope,
                "description": desc[:200],
            })
    return out


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="discover-agents.py", description=__doc__)
    p.add_argument("--json", action="store_true")
    p.add_argument("--role")
    p.add_argument("--extra-dir", action="append", default=[])
    args = p.parse_args(argv)

    agents = collect(args.extra_dir, args.role)
    if args.json:
        import json
        print(json.dumps(agents, indent=2))
        return
    if not agents:
        print("(no agents found in scanned scopes)", file=sys.stderr)
        return
    width = max(len(a["name"]) for a in agents)
    for a in agents:
        print(f"{a['name']:<{width}}  {a['model']:<8}  {a['description']}")


if __name__ == "__main__":
    main()
