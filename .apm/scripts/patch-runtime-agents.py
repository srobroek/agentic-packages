#!/usr/bin/env python3
"""Patch APM-generated runtime agents from namespaced source frontmatter.

APM can convert `.agent.md` into runtime-native files, but some Codex and
Claude fields are still runtime-specific. This finalizer is intended to run via
`apm run patch-agents` after `apm install`.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    end = text.find("\n---", 4)
    if end == -1:
        return "", text
    return text[4:end], text[end + 4 :].lstrip("\n")


def parse_scalar_map(frontmatter: str) -> dict:
    """Parse the small YAML subset used by our x-agentic metadata."""
    root: dict = {}
    stack: list[tuple[int, dict]] = [(-1, root)]

    for raw in frontmatter.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.lstrip().startswith("- "):
            continue

        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]

        if value == "":
            child: dict = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = value

    return root


def source_agents_dir(root: Path) -> Path:
    candidates = [
        root / ".apm" / "agents",
        root / "apm_modules" / "_local" / "agentic-packages" / ".apm" / "agents",
        root / "apm_modules" / "srobroek" / "agentic-packages" / ".apm" / "agents",
    ]
    candidates.extend(root.glob("apm_modules/**/agentic-packages/.apm/agents"))
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise SystemExit("No source .apm/agents directory found.")


def source_agent_metadata(root: Path) -> dict[str, dict]:
    agents: dict[str, dict] = {}
    for path in sorted(source_agents_dir(root).glob("*.agent.md")):
        frontmatter, _ = split_frontmatter(path.read_text(encoding="utf-8"))
        parsed = parse_scalar_map(frontmatter)
        name = str(parsed.get("name") or path.name.removesuffix(".agent.md"))
        agents[name] = parsed.get("x-agentic", {}) if isinstance(parsed.get("x-agentic"), dict) else {}
    return agents


def set_toml_string(text: str, key: str, value: str) -> str:
    line = f'{key} = "{value}"'
    pattern = re.compile(rf"^{re.escape(key)}\s*=.*$", re.MULTILINE)
    if pattern.search(text):
        return pattern.sub(line, text, count=1)
    insert_at = text.find("\ndeveloper_instructions")
    if insert_at != -1:
        return text[: insert_at + 1] + line + "\n" + text[insert_at + 1 :]
    return text.rstrip() + "\n" + line + "\n"


def patch_codex(root: Path, agents: dict[str, dict]) -> int:
    target_dir = root / ".codex" / "agents"
    if not target_dir.is_dir():
        print("codex: .codex/agents not found; skipping")
        return 0

    patched = 0
    for name, metadata in agents.items():
        codex = metadata.get("codex") if isinstance(metadata, dict) else None
        if not isinstance(codex, dict):
            continue
        path = target_dir / f"{name}.toml"
        if not path.is_file():
            print(f"codex: missing generated agent {path}")
            continue
        text = path.read_text(encoding="utf-8")
        if codex.get("model"):
            text = set_toml_string(text, "model", str(codex["model"]))
        if codex.get("reasoning_effort"):
            text = set_toml_string(text, "model_reasoning_effort", str(codex["reasoning_effort"]))
        if codex.get("sandbox_mode"):
            text = set_toml_string(text, "sandbox_mode", str(codex["sandbox_mode"]))
        if codex.get("approval_policy"):
            text = set_toml_string(text, "approval_policy", str(codex["approval_policy"]))
        path.write_text(text, encoding="utf-8")
        patched += 1
    print(f"codex: patched {patched} agent(s)")
    return patched


def upsert_frontmatter_scalar(frontmatter: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}\s*:.*$", re.MULTILINE)
    line = f"{key}: {value}"
    if pattern.search(frontmatter):
        return pattern.sub(line, frontmatter, count=1)
    return frontmatter.rstrip() + "\n" + line


def patch_claude(root: Path, agents: dict[str, dict]) -> int:
    target_dir = root / ".claude" / "agents"
    if not target_dir.is_dir():
        print("claude: .claude/agents not found; skipping")
        return 0

    patched = 0
    for name, metadata in agents.items():
        claude = metadata.get("claude") if isinstance(metadata, dict) else None
        if not isinstance(claude, dict):
            continue
        path = target_dir / f"{name}.md"
        if not path.is_file():
            print(f"claude: missing generated agent {path}")
            continue
        text = path.read_text(encoding="utf-8")
        frontmatter, body = split_frontmatter(text)
        if not frontmatter:
            continue
        if claude.get("model"):
            frontmatter = upsert_frontmatter_scalar(frontmatter, "model", str(claude["model"]))
        if claude.get("effort"):
            frontmatter = upsert_frontmatter_scalar(frontmatter, "effort", str(claude["effort"]))
        permissions = claude.get("permissions")
        if isinstance(permissions, dict) and permissions.get("mode"):
            frontmatter = upsert_frontmatter_scalar(
                frontmatter,
                "permission-mode",
                str(permissions["mode"]),
            )
        path.write_text("---\n" + frontmatter.rstrip() + "\n---\n\n" + body, encoding="utf-8")
        patched += 1
    print(f"claude: patched {patched} agent(s)")
    return patched


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Project root containing runtime output")
    parser.add_argument("--codex", action="store_true")
    parser.add_argument("--claude", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    agents = source_agent_metadata(root)

    run_codex = args.all or args.codex or not (args.codex or args.claude)
    run_claude = args.all or args.claude or not (args.codex or args.claude)

    if run_codex:
        patch_codex(root, agents)
    if run_claude:
        patch_claude(root, agents)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
