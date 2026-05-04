#!/usr/bin/env python3
"""Generate the APM marketplace block from local skills and curated packages."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APM_YML = ROOT / "apm.yml"


CORE_PACKAGE = {
    "name": "agentic-core",
    "description": "Full shared package: agents, skills, hooks, instructions, contexts, and scripts.",
    "source": "srobroek/agentic-packages",
    "ref": "main",
}


MATT_SKILLS = [
    ("matt-caveman", "Ultra-compressed communication mode.", "skills/productivity/caveman"),
    ("matt-diagnose", "Disciplined diagnosis loop for hard bugs and regressions.", "skills/engineering/diagnose"),
    ("matt-grill-me", "Planning grill without project docs.", "skills/productivity/grill-me"),
    ("matt-grill-with-docs", "Planning grill using domain docs and ADRs.", "skills/engineering/grill-with-docs"),
    ("matt-improve-codebase-architecture", "Find architecture deepening opportunities.", "skills/engineering/improve-codebase-architecture"),
    ("matt-setup-skills", "Scaffold repo-local docs consumed by Matt Pocock skills.", "skills/engineering/setup-matt-pocock-skills"),
    ("matt-tdd", "Test-driven development loop.", "skills/engineering/tdd"),
    ("matt-to-issues", "Break plans and specs into independently grabbable issues.", "skills/engineering/to-issues"),
    ("matt-to-prd", "Turn current conversation context into a PRD.", "skills/engineering/to-prd"),
    ("matt-triage", "Triage issues through a role/state machine.", "skills/engineering/triage"),
    ("matt-write-a-skill", "Create new agent skills.", "skills/productivity/write-a-skill"),
    ("matt-zoom-out", "Ask for broader codebase context.", "skills/engineering/zoom-out"),
]


def description_for_skill(skill_dir: Path) -> str:
    skill = skill_dir / "SKILL.md"
    for line in skill.read_text(encoding="utf-8").splitlines():
        if line.startswith("description: "):
            return line.removeprefix("description: ").strip().strip('"')
    return f"{skill_dir.name} skill from agentic-packages."


def package_yaml(package: dict[str, str]) -> str:
    lines = [
        f"    - name: {package['name']}",
        f"      description: \"{package['description'].replace(chr(34), chr(39))}\"",
        f"      source: {package['source']}",
    ]
    if subdir := package.get("subdir"):
        lines.append(f"      subdir: {subdir}")
    if ref := package.get("ref"):
        lines.append(f"      ref: {ref}")
    return "\n".join(lines)


def build_marketplace_block() -> str:
    packages: list[dict[str, str]] = [CORE_PACKAGE]
    for skill_dir in sorted((ROOT / ".apm" / "skills").iterdir()):
        if not (skill_dir / "SKILL.md").is_file():
            continue
        packages.append(
            {
                "name": f"agentic-skill-{skill_dir.name}",
                "description": description_for_skill(skill_dir),
                "source": "srobroek/agentic-packages",
                "subdir": f".apm/skills/{skill_dir.name}",
                "ref": "main",
            }
        )
    packages.append(
        {
            "name": "matt-skills",
            "description": "Full Matt Pocock skills package.",
            "source": "mattpocock/skills",
        }
    )
    for name, description, subdir in MATT_SKILLS:
        packages.append(
            {
                "name": name,
                "description": description,
                "source": "mattpocock/skills",
                "subdir": subdir,
            }
        )

    body = [
        "marketplace:",
        "  owner:",
        "    name: srobroek",
        "    url: https://github.com/srobroek",
        "  build:",
        "    tagPattern: \"v{version}\"",
        "  packages:",
    ]
    body.extend(package_yaml(package) for package in packages)
    return "\n".join(body) + "\n"


def main() -> int:
    text = APM_YML.read_text(encoding="utf-8")
    marker = "\nmarketplace:\n"
    if marker in text:
        text = text[: text.index(marker)].rstrip() + "\n\n"
    APM_YML.write_text(text.rstrip() + "\n\n" + build_marketplace_block(), encoding="utf-8")
    print(f"updated {APM_YML}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
