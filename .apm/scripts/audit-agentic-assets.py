#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""Report target-aware agent and shared skill runtime parity."""

from __future__ import annotations

from pathlib import Path

import yaml


def names(path: Path, suffix: str) -> set[str]:
    if not path.is_dir():
        return set()
    return {p.name.removesuffix(suffix) for p in path.glob(f"*{suffix}")}


def source_agent_paths(package: Path) -> list[Path]:
    """Find first-party agent sources in a monorepo or installed package tree."""
    candidates = list((package / ".apm" / "agents").glob("*.agent.md"))
    candidates.extend((package / "packages").glob("*/.apm/agents/*.agent.md"))
    candidates.extend(package.glob("apm_modules/**/.apm/agents/*.agent.md"))
    return sorted({path.resolve() for path in candidates if path.is_file()})


def source_skill_names(package: Path) -> set[str]:
    """Find first-party skill sources without counting generated runtime copies."""
    roots = [package / ".apm" / "skills"]
    roots.extend((package / "packages").glob("*/.apm/skills"))
    roots.extend(package.glob("apm_modules/**/.apm/skills"))
    return {
        path.parent.name
        for root in roots
        if root.is_dir()
        for path in root.glob("*/SKILL.md")
        if path.is_file()
    }


def package_root(root: Path) -> Path | None:
    candidates = [
        root,
        root / "apm_modules" / "_local" / "skills",
        root / "apm_modules" / "srobroek" / "skills",
    ]
    candidates.extend(root.glob("apm_modules/**/skills"))
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


def agent_package_target(path: Path) -> str:
    package_root = path.parents[2]
    manifest = yaml.safe_load((package_root / "apm.yml").read_text(encoding="utf-8")) or {}
    return str(manifest.get("target") or "all")


def agent_model_mapping(path: Path, name: str) -> dict[str, str]:
    mapping_path = path.parents[1] / "agent-models.yml"
    if not mapping_path.is_file():
        return {}
    document = yaml.safe_load(mapping_path.read_text(encoding="utf-8")) or {}
    agents = document.get("agents") or {}
    runtime = agents.get(name) if isinstance(agents, dict) else None
    codex = runtime.get("codex") if isinstance(runtime, dict) else None
    return {key: str(value) for key, value in codex.items()} if isinstance(codex, dict) else {}


def source_priority(package: Path, path: Path) -> tuple[int, str]:
    """Prefer monorepo and direct-local sources over cached remote duplicates."""
    relative = path.relative_to(package)
    parts = relative.parts
    if "apm_modules" not in parts:
        return (0, str(relative))
    modules_index = parts.index("apm_modules")
    if len(parts) > modules_index + 1 and parts[modules_index + 1] == "_local":
        return (1, str(relative))
    return (2, str(relative))


def source_agent_metadata(package: Path) -> dict[str, dict[str, str]]:
    candidates: dict[tuple[str, str], tuple[tuple[int, str], str, dict[str, str]]] = {}
    for path in source_agent_paths(package):
        frontmatter = split_frontmatter(path.read_text(encoding="utf-8"))
        parsed = parse_scalar_map(frontmatter)
        name = str(parsed.get("name") or path.name.removesuffix(".agent.md"))
        mapping = agent_model_mapping(path, name)
        package_manifest = yaml.safe_load((path.parents[2] / "apm.yml").read_text(encoding="utf-8")) or {}
        package_name = str(package_manifest.get("name") or path.parents[2].name)
        relative_path = str(path.relative_to(package))
        actual = {
            "name": name,
            "target": agent_package_target(path),
            "model": str(parsed.get("model", "")),
            "effort": str(parsed.get("effort", "")),
            "model_reasoning_effort": str(parsed.get("model_reasoning_effort", "")),
            "permissionMode": str(parsed.get("permissionMode", "")),
            "tools": str(parsed.get("tools", "")),
            "x-agentic": str(parsed.get("x-agentic", "")),
            "mapped_model": mapping.get("model", ""),
            "mapped_reasoning_effort": mapping.get("reasoning_effort", ""),
        }
        identity = (package_name, name)
        candidate = (source_priority(package, path), relative_path, actual)
        if identity not in candidates or candidate[0] < candidates[identity][0]:
            candidates[identity] = candidate
    return {relative_path: actual for _, relative_path, actual in candidates.values()}


def main() -> int:
    root = Path.cwd()
    package = package_root(root) or root
    metadata = source_agent_metadata(package)
    source = {actual["name"] for actual in metadata.values()}
    expected_claude = {
        actual["name"] for actual in metadata.values() if actual["target"] in {"all", "claude"}
    }
    expected_codex = {
        actual["name"] for actual in metadata.values() if actual["target"] in {"all", "codex"}
    }
    skills = source_skill_names(package)
    codex = names(root / ".codex" / "agents", ".toml")
    claude = names(root / ".claude" / "agents", ".md")
    agent_skills = (
        {
            path.name
            for path in (root / ".agents" / "skills").iterdir()
            if path.is_dir() and (path / "SKILL.md").is_file()
        }
        if (root / ".agents" / "skills").is_dir()
        else set()
    )
    claude_skills = (
        {
            path.name
            for path in (root / ".claude" / "skills").iterdir()
            if path.is_dir() and (path / "SKILL.md").is_file()
        }
        if (root / ".claude" / "skills").is_dir()
        else set()
    )

    print("Agent parity")
    print(f"- source definitions: {len(metadata)}")
    print(f"- unique roles: {len(source)}")
    print(f"- expected claude: {len(expected_claude)}")
    print(f"- expected codex: {len(expected_codex)}")
    print(f"- claude: {len(claude)}")
    print(f"- codex: {len(codex)}")
    parity_errors: list[str] = []
    if source:
        if missing := sorted(expected_claude - claude):
            print("- missing in claude: " + ", ".join(missing))
            parity_errors.append(f"{len(missing)} Claude agents missing")
        if missing := sorted(expected_codex - codex):
            print("- missing in codex: " + ", ".join(missing))
            parity_errors.append(f"{len(missing)} Codex agents missing")
        if extra := sorted(claude - expected_claude):
            print("- claude-only: " + ", ".join(extra))
        if extra := sorted(codex - expected_codex):
            print("- codex-only: " + ", ".join(extra))
        if leaked := sorted(expected_claude & (codex - expected_codex)):
            print("- Claude-targeted agents leaked into codex: " + ", ".join(leaked))
            parity_errors.append(f"{len(leaked)} Claude-targeted agents leaked into Codex")
        if leaked := sorted(expected_codex & (claude - expected_claude)):
            print("- Codex-targeted agents leaked into claude: " + ", ".join(leaked))
            parity_errors.append(f"{len(leaked)} Codex-targeted agents leaked into Claude")

    print("\nSkill parity")
    print(f"- source: {len(skills)}")
    print(f"- .agents/skills: {len(agent_skills)}")
    print(f"- .claude/skills: {len(claude_skills)}")
    if skills:
        if missing := sorted(skills - agent_skills):
            print("- missing in .agents/skills: " + ", ".join(missing))
            parity_errors.append(f"{len(missing)} source skills missing in .agents/skills")
        if missing := sorted(skills - claude_skills):
            print("- missing in .claude/skills: " + ", ".join(missing))
            parity_errors.append(f"{len(missing)} source skills missing in .claude/skills")
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

    print("\nAgent metadata")
    missing = []
    if (package / "packages").is_dir() and not source:
        missing.append("no source agents discovered in package monorepo")
    if (package / "packages").is_dir() and not skills:
        missing.append("no source skills discovered in package monorepo")
    for source_path, actual in sorted(metadata.items()):
        required = []
        if actual["target"] in {"all", "claude"}:
            required.extend(("model", "effort", "permissionMode"))
        for key in required:
            if not actual.get(key):
                missing.append(f"{source_path}: missing {key}")
        if actual["target"] in {"all", "codex"}:
            for key in ("mapped_model", "mapped_reasoning_effort"):
                if not actual.get(key):
                    missing.append(f"{source_path}: missing package-local {key}")
        if actual.get("x-agentic"):
            missing.append(f"{source_path}: legacy x-agentic block remains")
        if actual["target"] in {"all", "codex"} and actual.get("tools"):
            missing.append(f"{source_path}: Codex profile declares unsupported tools")
    print(f"- checked: {len(metadata)}")
    print(f"- missing fields: {len(missing)}")
    for item in missing[:30]:
        print(f"  - {item}")
    if len(missing) > 30:
        print(f"  - ... {len(missing) - 30} more")
    if parity_errors:
        print("\nParity failures")
        for error in parity_errors:
            print(f"- {error}")
    if missing or parity_errors:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
