#!/usr/bin/env python3
"""Sync .apm agent frontmatter from the reviewed recommendation matrix."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = ROOT / ".apm" / "agents"
RECOMMENDATIONS = ROOT / "reviews" / "voltagent-agent-metadata-recommendations.md"


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    end = text.find("\n---", 4)
    if end == -1:
        return "", text
    return text[4:end], text[end + 4 :].lstrip("\n")


def strip_managed_blocks(frontmatter: str) -> str:
    lines = frontmatter.splitlines()
    kept: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.match(r"^tools\s*:", line):
            i += 1
            while i < len(lines) and (lines[i].startswith(" ") or lines[i].strip().startswith("- ")):
                i += 1
            continue
        if re.match(r"^x-agentic\s*:", line):
            i += 1
            while i < len(lines) and (lines[i].startswith(" ") or not lines[i].strip()):
                i += 1
            continue
        kept.append(line)
        i += 1
    while kept and not kept[-1].strip():
        kept.pop()
    return "\n".join(kept)


def parse_existing_x_agentic(frontmatter: str) -> dict[str, dict[str, str] | str]:
    root: dict[str, dict[str, str] | str] = {}
    stack: list[tuple[int, dict]] = [(-1, root)]
    in_x_agentic = False

    for raw in frontmatter.splitlines():
        if raw.startswith("x-agentic:"):
            in_x_agentic = True
            continue
        if not in_x_agentic:
            continue
        if raw and not raw.startswith(" "):
            break
        if not raw.strip() or ":" not in raw:
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        key, value = raw.strip().split(":", 1)
        value = value.strip().strip('"').strip("'")
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if value:
            parent[key] = value
        else:
            child: dict = {}
            parent[key] = child
            stack.append((indent, child))
    return root


def quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def emit_map(name: str, values: dict, indent: int = 0) -> list[str]:
    prefix = " " * indent
    lines = [f"{prefix}{name}:"]
    for key, value in values.items():
        if isinstance(value, dict):
            lines.extend(emit_map(key, value, indent + 2))
        else:
            lines.append(f"{' ' * (indent + 2)}{key}: {quote(str(value))}")
    return lines


def parse_recommendations(path: Path) -> dict[str, dict[str, str]]:
    recommendations: dict[str, dict[str, str]] = {}
    row_pattern = re.compile(r"^\| `([^`]+)` \|")
    for line in path.read_text(encoding="utf-8").splitlines():
        if not row_pattern.match(line):
            continue
        columns = [column.strip() for column in line.strip("|").split("|")]
        if len(columns) < 10:
            continue
        agent = columns[0].strip("`")
        codex_model_effort = re.findall(r"`([^`]+)`", columns[2])
        claude_model_effort = re.findall(r"`([^`]+)`", columns[5])
        if len(codex_model_effort) < 2 or len(claude_model_effort) < 2:
            continue
        recommendations[agent] = {
            "codex_model": codex_model_effort[0],
            "codex_effort": codex_model_effort[1],
            "access": columns[3].strip("`"),
            "approval": columns[4].strip("`"),
            "claude_model": claude_model_effort[0],
            "claude_effort": claude_model_effort[1],
            "claude_permissions": columns[6].strip("`"),
            "mcp_tools": columns[7],
            "skills": columns[8],
        }
    return recommendations


def normalized_tools(recommendation: dict[str, str]) -> list[str]:
    tools = ["terminal", "file-manager"]
    for item in recommendation["mcp_tools"].split(","):
        tool = item.strip()
        if not tool or tool == "filesystem":
            continue
        if tool == "shell":
            tool = "terminal"
        tools.append(tool)
    if recommendation["skills"] != "-":
        for item in recommendation["skills"].split(","):
            skill = item.strip()
            if skill:
                tools.append(skill)
    return list(dict.fromkeys(tools))


def sync_agent(path: Path, recommendation: dict[str, str]) -> bool:
    text = path.read_text(encoding="utf-8")
    frontmatter, body = split_frontmatter(text)
    if not frontmatter:
        raise SystemExit(f"{path}: missing frontmatter")

    existing = parse_existing_x_agentic(frontmatter)
    base = strip_managed_blocks(frontmatter)
    tools = normalized_tools(recommendation)

    x_agentic: dict = {}
    for key in ("source", "category", "upstream"):
        if key in existing:
            x_agentic[key] = existing[key]
    x_agentic["codex"] = {
        "model": recommendation["codex_model"],
        "reasoning_effort": recommendation["codex_effort"],
        "sandbox_mode": recommendation["access"],
        "approval_policy": recommendation["approval"],
    }
    x_agentic["claude"] = {
        "model": recommendation["claude_model"],
        "effort": recommendation["claude_effort"],
        "permissions": {"mode": recommendation["claude_permissions"]},
    }

    managed = [
        f"tools: [{', '.join(quote(tool) for tool in tools)}]",
        *emit_map("x-agentic", x_agentic),
    ]
    updated = "---\n" + base.rstrip() + "\n" + "\n".join(managed) + "\n---\n\n" + body
    if updated != text:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail if metadata is not already synced")
    args = parser.parse_args()

    recommendations = parse_recommendations(RECOMMENDATIONS)
    changed: list[str] = []
    missing: list[str] = []

    for path in sorted(AGENTS_DIR.glob("*.agent.md")):
        agent = path.name.removesuffix(".agent.md")
        recommendation = recommendations.get(agent)
        if recommendation is None:
            missing.append(agent)
            continue
        if sync_agent(path, recommendation):
            changed.append(agent)

    if missing:
        raise SystemExit("Missing recommendations for: " + ", ".join(missing))
    if args.check and changed:
        raise SystemExit("Unsynced agent metadata: " + ", ".join(changed))
    print(f"synced {len(changed)} changed agent(s), {len(list(AGENTS_DIR.glob('*.agent.md')))} checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
