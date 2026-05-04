#!/usr/bin/env python3
"""Report runtime parity and known external-source candidates."""

from __future__ import annotations

import re
from pathlib import Path


def names(path: Path, suffix: str) -> set[str]:
    if not path.is_dir():
        return set()
    return {p.name.removesuffix(suffix) for p in path.glob(f"*{suffix}")}


def package_root(root: Path) -> Path | None:
    candidates = [
        root,
        root / "apm_modules" / "_local" / "agentic-packages",
        root / "apm_modules" / "srobroek" / "agentic-packages",
    ]
    candidates.extend(root.glob("apm_modules/**/agentic-packages"))
    for candidate in candidates:
        if (candidate / ".apm").is_dir():
            return candidate
    return None


def split_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return ""
    end = text.find("\n---", 4)
    if end == -1:
        return ""
    return text[4:end]


def parse_scalar_map(frontmatter: str) -> dict:
    root: dict = {}
    stack: list[tuple[int, dict]] = [(-1, root)]

    for raw in frontmatter.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#") or raw.lstrip().startswith("- "):
            continue
        if ":" not in raw:
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        key, value = raw.strip().split(":", 1)
        value = value.strip().strip('"').strip("'")
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if value:
            parent[key.strip()] = value
        else:
            child: dict = {}
            parent[key.strip()] = child
            stack.append((indent, child))
    return root


def parse_recommendations(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    recommendations: dict[str, dict[str, str]] = {}
    row_pattern = re.compile(r"^\| `([^`]+)` \|")
    for line in path.read_text(encoding="utf-8").splitlines():
        if not row_pattern.match(line):
            continue
        columns = [column.strip() for column in line.strip("|").split("|")]
        if len(columns) < 10:
            continue
        codex_model_effort = re.findall(r"`([^`]+)`", columns[2])
        if len(codex_model_effort) < 2:
            continue
        recommendations[columns[0].strip("`")] = {
            "model": codex_model_effort[0],
            "effort": codex_model_effort[1],
            "access": columns[3].strip("`"),
            "approval": columns[4].strip("`"),
        }
    return recommendations


def source_agent_metadata(package: Path) -> dict[str, dict[str, str]]:
    metadata: dict[str, dict[str, str]] = {}
    for path in sorted((package / ".apm" / "agents").glob("*.agent.md")):
        frontmatter = split_frontmatter(path.read_text(encoding="utf-8"))
        parsed = parse_scalar_map(frontmatter)
        codex = parsed.get("x-agentic", {}).get("codex", {}) if isinstance(parsed.get("x-agentic"), dict) else {}
        metadata[path.name.removesuffix(".agent.md")] = {
            "model": str(codex.get("model", "")) if isinstance(codex, dict) else "",
            "effort": str(codex.get("reasoning_effort", "")) if isinstance(codex, dict) else "",
            "access": str(codex.get("sandbox_mode", "")) if isinstance(codex, dict) else "",
            "approval": str(codex.get("approval_policy", "")) if isinstance(codex, dict) else "",
        }
    return metadata


def main() -> int:
    root = Path.cwd()
    package = package_root(root) or root
    source = names(package / ".apm" / "agents", ".agent.md")
    skills = {
        path.name
        for path in (package / ".apm" / "skills").iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    } if (package / ".apm" / "skills").is_dir() else set()
    codex = names(root / ".codex" / "agents", ".toml")
    claude = names(root / ".claude" / "agents", ".md")
    agent_skills = {
        path.name
        for path in (root / ".agents" / "skills").iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    } if (root / ".agents" / "skills").is_dir() else set()
    claude_skills = {
        path.name
        for path in (root / ".claude" / "skills").iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    } if (root / ".claude" / "skills").is_dir() else set()

    print("Agent parity")
    print(f"- source: {len(source)}")
    print(f"- codex: {len(codex)}")
    print(f"- claude: {len(claude)}")
    if source:
        if missing := sorted(source - codex):
            print("- missing in codex: " + ", ".join(missing))
        if missing := sorted(source - claude):
            print("- missing in claude: " + ", ".join(missing))
        if extra := sorted(codex - source):
            print("- codex-only: " + ", ".join(extra))
        if extra := sorted(claude - source):
            print("- claude-only: " + ", ".join(extra))

    print("\nSkill parity")
    print(f"- source: {len(skills)}")
    print(f"- .agents/skills: {len(agent_skills)}")
    print(f"- .claude/skills: {len(claude_skills)}")
    if skills:
        if missing := sorted(skills - agent_skills):
            print("- missing in .agents/skills: " + ", ".join(missing))
        if missing := sorted(skills - claude_skills):
            print("- missing in .claude/skills: " + ", ".join(missing))
        if extra := sorted(agent_skills - skills):
            print("- .agents/skills-only: " + ", ".join(extra))
        if extra := sorted(claude_skills - skills):
            print("- .claude/skills-only: " + ", ".join(extra))

    print("\nExternal-source candidates to review before dependency replacement")
    for candidate in [
        "mattpocock/skills",
        "mattpocock/skills:caveman",
        "mattpocock/skills:diagnose",
        "mattpocock/skills:grill-me",
        "mattpocock/skills:grill-with-docs",
        "mattpocock/skills:improve-codebase-architecture",
        "mattpocock/skills:setup-matt-pocock-skills",
        "mattpocock/skills:tdd",
        "mattpocock/skills:to-issues",
        "mattpocock/skills:to-prd",
        "mattpocock/skills:triage",
        "mattpocock/skills:write-a-skill",
        "mattpocock/skills:zoom-out",
        "remotion",
        "interface-design",
        "impeccable",
        "stitch-design",
        "stitch-loop",
        "react-components",
        "shadcn-ui",
    ]:
        print(f"- {candidate}")

    recommendations = parse_recommendations(package / "reviews" / "voltagent-agent-metadata-recommendations.md")
    metadata = source_agent_metadata(package)
    print("\nAgent metadata")
    mismatches = []
    for agent, actual in sorted(metadata.items()):
        expected = recommendations.get(agent)
        if expected is None:
            mismatches.append(f"{agent}: no recommendation")
            continue
        for key in ("model", "effort", "access", "approval"):
            if actual.get(key) != expected.get(key):
                mismatches.append(f"{agent}: {key} expected {expected.get(key)} got {actual.get(key)}")
    print(f"- checked: {len(metadata)}")
    print(f"- mismatches: {len(mismatches)}")
    for mismatch in mismatches[:30]:
        print(f"  - {mismatch}")
    if len(mismatches) > 30:
        print(f"  - ... {len(mismatches) - 30} more")
    if mismatches:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
