#!/usr/bin/env python3
"""Build searchable indexes from APM package sources."""

from __future__ import annotations

import json
import os
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


def first_heading(body: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line.removeprefix("# ").strip()
    return ""


def first_text(body: str, limit: int = 220) -> str:
    chunks: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("---"):
            continue
        chunks.append(stripped)
        text = " ".join(chunks)
        if len(text) >= limit:
            return text[:limit].rstrip()
    return " ".join(chunks)[:limit].rstrip()


def parse_simple_yaml(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if ":" not in raw or raw.lstrip().startswith("#"):
            continue
        key, value = raw.split(":", 1)
        if key.startswith(" "):
            continue
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def script_metadata(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8", errors="replace")
    first_line = text.splitlines()[0] if text.splitlines() else ""
    return {
        "name": path.name,
        "path": str(path.relative_to(ROOT)),
        "shebang": first_line if first_line.startswith("#!") else "",
        "executable": bool(os.access(path, os.X_OK)),
        "keywords": keywords(path.name, text[:1200]),
    }


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


def skill_scripts(skill_dir: Path) -> list[str]:
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.is_dir():
        return []
    return [str(path.relative_to(ROOT)) for path in sorted(scripts_dir.glob("*")) if path.is_file()]


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
                "scripts": skill_scripts(path.parent),
                "keywords": keywords(name, frontmatter.get("description", ""), body[:1000]),
            }
        )
    return rows


def build_hooks() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    hooks_dir = ROOT / ".apm" / "hooks"

    for path in sorted(hooks_dir.glob("*.json")):
        text = path.read_text(encoding="utf-8")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = {}
        hooks = parsed.get("hooks", {}) if isinstance(parsed, dict) else {}
        events = sorted(hooks) if isinstance(hooks, dict) else []
        commands = sorted(set(re.findall(r"\.apm/hooks/scripts/[A-Za-z0-9._/-]+", text)))
        rows.append(
            {
                "name": path.stem,
                "type": "hook-config",
                "path": str(path.relative_to(ROOT)),
                "events": events,
                "scripts": commands,
                "keywords": keywords(path.stem, events, commands, text[:1200]),
            }
        )

    for path in sorted((hooks_dir / "scripts").glob("*")):
        if path.is_file():
            row = script_metadata(path)
            row["type"] = "hook-script"
            rows.append(row)

    return rows


def build_markdown_index(directory: Path, suffix: str, asset_type: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if not directory.is_dir():
        return rows
    for path in sorted(directory.rglob(f"*{suffix}")):
        text = path.read_text(encoding="utf-8")
        frontmatter, body = split_frontmatter(text)
        rows.append(
            {
                "name": path.name.removesuffix(suffix),
                "title": first_heading(body),
                "description": str(frontmatter.get("description", "")) or first_text(body),
                "path": str(path.relative_to(ROOT)),
                "type": asset_type,
                "keywords": keywords(path.stem, frontmatter.get("description", ""), body[:1200]),
            }
        )
    return rows


def build_mcp() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    mcp_dir = ROOT / ".apm" / "mcp"
    if not mcp_dir.is_dir():
        return rows
    for path in sorted(p for p in mcp_dir.rglob("*") if p.is_file()):
        text = path.read_text(encoding="utf-8", errors="replace")
        rows.append(
            {
                "name": path.stem,
                "path": str(path.relative_to(ROOT)),
                "type": "mcp",
                "keywords": keywords(path.name, text[:1200]),
            }
        )
    return rows


def build_scripts() -> list[dict[str, object]]:
    scripts_dir = ROOT / ".apm" / "scripts"
    return [
        script_metadata(path) | {"type": "script"}
        for path in sorted(scripts_dir.glob("*"))
        if path.is_file()
    ]


def build_wrappers() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    wrappers_dir = ROOT / ".apm" / "wrappers"
    if not wrappers_dir.is_dir():
        return rows

    for wrapper_dir in sorted(path for path in wrappers_dir.iterdir() if path.is_dir()):
        skill = wrapper_dir / "SKILL.md"
        manifest = wrapper_dir / "apm.yml"
        description = ""
        keywords_source = ""
        if skill.is_file():
            frontmatter, body = split_frontmatter(skill.read_text(encoding="utf-8"))
            description = str(frontmatter.get("description", "")) or first_text(body)
            keywords_source = body[:1200]
        elif manifest.is_file():
            parsed = parse_simple_yaml(manifest)
            description = parsed.get("description", "")
            keywords_source = manifest.read_text(encoding="utf-8")[:1200]

        rows.append(
            {
                "name": wrapper_dir.name,
                "description": description,
                "path": str(wrapper_dir.relative_to(ROOT)),
                "type": "wrapper",
                "keywords": keywords(wrapper_dir.name, description, keywords_source),
            }
        )
    return rows


def asset_rows(indexes: dict[str, list[dict[str, object]]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    singular = {
        "agents": "agent",
        "skills": "skill",
        "hooks": "hook",
        "contexts": "context",
        "instructions": "instruction",
        "mcp": "mcp",
        "scripts": "script",
        "wrappers": "wrapper",
    }
    for group, items in indexes.items():
        for item in items:
            rows.append(
                {
                    "group": group,
                    "type": item.get("type", singular.get(group, group)),
                    "name": item.get("name", ""),
                    "path": item.get("path", ""),
                    "description": item.get("description", ""),
                    "keywords": item.get("keywords", []),
                }
            )
    return sorted(rows, key=lambda row: (str(row["group"]), str(row["name"]), str(row["path"])))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    indexes = {
        "agents": build_agents(),
        "skills": build_skills(),
        "hooks": build_hooks(),
        "contexts": build_markdown_index(ROOT / ".apm" / "context", ".context.md", "context"),
        "instructions": build_markdown_index(
            ROOT / ".apm" / "instructions",
            ".instructions.md",
            "instruction",
        ),
        "mcp": build_mcp(),
        "scripts": build_scripts(),
        "wrappers": build_wrappers(),
    }
    indexes["assets"] = asset_rows(indexes)

    for name, rows in indexes.items():
        path = OUT / f"{name}.json"
        path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n")
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
