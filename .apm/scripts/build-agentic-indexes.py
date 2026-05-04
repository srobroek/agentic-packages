#!/usr/bin/env python3
"""Build searchable agent and skill indexes from APM package sources."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "indexes"


def split_frontmatter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    return parse_frontmatter(text[4:end]), text[end + 4 :].lstrip()


def parse_scalar(value: str) -> object:
    value = value.strip()
    if not value:
        return ""
    if value.startswith("[") and value.endswith("]"):
        raw_items = [item.strip() for item in value[1:-1].split(",") if item.strip()]
        return [item.strip('"').strip("'") for item in raw_items]
    return value.strip('"').strip("'")


def parse_frontmatter(frontmatter: str) -> dict[str, object]:
    root: dict[str, object] = {}
    stack: list[tuple[int, dict[str, object]]] = [(-1, root)]

    for raw in frontmatter.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#") or raw.lstrip().startswith("- "):
            continue
        if ":" not in raw:
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        key, value = raw.strip().split(":", 1)
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if value.strip():
            parent[key.strip()] = parse_scalar(value)
        else:
            child: dict[str, object] = {}
            parent[key.strip()] = child
            stack.append((indent, child))
    return root


def keywords(*values: object) -> list[str]:
    text = " ".join(
        value if isinstance(value, str) else " ".join(value) if isinstance(value, list) else ""
        for value in values
    ).lower()
    words = set(re.findall(r"[a-z0-9][a-z0-9+.#-]{1,}", text))
    stop = {
        "agent",
        "agents",
        "skill",
        "skills",
        "task",
        "tasks",
        "when",
        "with",
        "from",
        "that",
        "this",
        "into",
        "use",
        "uses",
        "using",
    }
    return sorted(word for word in words if word not in stop)


def build_agents() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted((ROOT / ".apm" / "agents").glob("*.agent.md")):
        frontmatter, body = split_frontmatter(path.read_text(encoding="utf-8"))
        x_agentic = frontmatter.get("x-agentic", {})
        codex = x_agentic.get("codex", {}) if isinstance(x_agentic, dict) else {}
        source = x_agentic.get("source", {}) if isinstance(x_agentic, dict) else {}
        category = x_agentic.get("category", "") if isinstance(x_agentic, dict) else ""
        rows.append(
            {
                "name": path.name.removesuffix(".agent.md"),
                "description": frontmatter.get("description", ""),
                "category": category,
                "tools": frontmatter.get("tools", []),
                "model": codex.get("model", "") if isinstance(codex, dict) else "",
                "reasoning_effort": codex.get("reasoning_effort", "") if isinstance(codex, dict) else "",
                "workspace_access": codex.get("sandbox_mode", "") if isinstance(codex, dict) else "",
                "approval_policy": codex.get("approval_policy", "") if isinstance(codex, dict) else "",
                "source": source,
                "path": str(path.relative_to(ROOT)),
                "keywords": keywords(
                    path.stem,
                    frontmatter.get("description", ""),
                    frontmatter.get("tools", []),
                    category,
                    body[:1200],
                ),
            }
        )
    return rows


def build_skills() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted((ROOT / ".apm" / "skills").glob("*/SKILL.md")):
        frontmatter, body = split_frontmatter(path.read_text(encoding="utf-8"))
        name = path.parent.name
        rows.append(
            {
                "name": name,
                "description": frontmatter.get("description", ""),
                "path": str(path.parent.relative_to(ROOT)),
                "source": "agentic-packages",
                "install": f"{ROOT}/.apm/skills/{name}",
                "keywords": keywords(name, frontmatter.get("description", ""), body[:1000]),
            }
        )
    return rows


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "agents.json").write_text(json.dumps(build_agents(), indent=2, sort_keys=True) + "\n")
    (OUT / "skills.json").write_text(json.dumps(build_skills(), indent=2, sort_keys=True) + "\n")
    print(f"wrote {OUT / 'agents.json'}")
    print(f"wrote {OUT / 'skills.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
