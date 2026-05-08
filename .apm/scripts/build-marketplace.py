#!/usr/bin/env python3
"""Generate the APM marketplace block from first-party skills and curated packages."""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APM_YML = ROOT / "apm.yml"
MARKETPLACE_JSON = ROOT / "marketplace.json"
LOCAL_SOURCE = "srobroek/agentic-packages"


CORE_PACKAGE = {
    "name": "core",
    "description": "Deterministic shared project baseline with core agents, code intelligence, project lifecycle, agentic maintenance, first-party skill writing, and Matt grill/diagnose workflows.",
    "source": LOCAL_SOURCE,
    "subdir": "packages/core",
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
    ("matt-zoom-out", "Ask for broader codebase context.", "skills/engineering/zoom-out"),
]


EXTERNAL_BUNDLES = [
    {
        "name": "diagrams",
        "description": "Diagram generation bundle that installs draw.io, Excalidraw, and D2 diagram skills for editable architecture, workflow, flowchart, and visual explanation diagrams.",
        "source": LOCAL_SOURCE,
        "subdir": "packages/diagrams",
        "ref": "main",
    },
    {
        "name": "drawio-skill",
        "description": "Third-party draw.io diagram skill for editable architecture, UML, ERD, sequence, flowchart, and process diagrams with local PNG/SVG/PDF export.",
        "source": "Agents365-ai/drawio-skill",
        "ref": "main",
    },
    {
        "name": "excalidraw-diagram-skill",
        "description": "Third-party Excalidraw diagram skill for visual argument diagrams, architecture explanations, and workflow sketches with render validation.",
        "source": "coleam00/excalidraw-diagram-skill",
        "ref": "main",
    },
    {
        "name": "d2-diagram",
        "description": "Third-party D2 diagram skill for text-based architecture, flowchart, data-flow, database, and topology diagrams.",
        "source": "neuro-synapse/network-topology-agent",
        "subdir": ".claude/skills/d2-diagram",
        "ref": "master",
    },
    {
        "name": "resume",
        "description": "Resume bundle that installs the preferred advanced resume-tailoring workflow plus the broader ResumeSkills career-support bundle.",
        "source": LOCAL_SOURCE,
        "subdir": "packages/resume",
        "ref": "main",
    },
    {
        "name": "presentation",
        "description": "Presentation bundle that installs ppt-creator, marp-slide, and pptx-from-layouts for general decks, Marp slides, and PowerPoint template workflows.",
        "source": LOCAL_SOURCE,
        "subdir": "packages/presentation",
        "ref": "main",
    },
    {
        "name": "ppt-creator",
        "description": "Third-party general-purpose presentation skill for persuasive, data-driven slide decks with speaker notes and PPTX output.",
        "source": "daymade/claude-code-skills",
        "subdir": "daymade-docs/ppt-creator",
        "ref": "main",
    },
    {
        "name": "marp-slide",
        "description": "Third-party Marp slide skill with multiple themes, image layouts, and slide design improvements.",
        "source": "softaworks/agent-toolkit",
        "subdir": "skills/marp-slide",
        "ref": "main",
    },
    {
        "name": "pptx-from-layouts",
        "description": "Third-party PowerPoint skill that generates editable PPTX decks from markdown using real slide-master layouts and placeholders.",
        "source": "tristan-mcinnis/pptx-from-layouts-skill",
        "subdir": ".claude/skills/pptx-from-layouts",
        "ref": "main",
    },
    {
        "name": "resume-tailoring",
        "description": "Third-party advanced resume tailoring skill with company research, branching experience discovery, matching strategies, and multi-format output.",
        "source": "varunr89/resume-tailoring-skill",
        "subdir": "skills/resume-tailoring",
        "ref": "master",
    },
    {
        "name": "tailored-resume-generator",
        "description": "Third-party focused resume tailoring skill that maps job descriptions to candidate experience and ATS-friendly resume output.",
        "source": "ComposioHQ/awesome-claude-skills",
        "subdir": "tailored-resume-generator",
        "ref": "master",
    },
    {
        "name": "resumeskills",
        "description": "Third-party career skills bundle for ATS optimization, resume bullets, job-description analysis, tailoring, interview prep, and job-search support.",
        "source": "Paramchoudhary/ResumeSkills",
        "ref": "main",
    },
    {
        "name": "hyperresearch",
        "description": "Third-party HyperResearch deep research harness package. Uses upstream HyperResearch's Python installer for runtime Claude assets.",
        "source": LOCAL_SOURCE,
        "subdir": "packages/hyperresearch",
        "ref": "main",
    },
    {
        "name": "impeccable",
        "description": "Third-party Impeccable frontend design skill bundle.",
        "source": "pbakaus/impeccable",
        "subdir": ".agents/skills/impeccable",
        "ref": "main",
    },
    {
        "name": "interface-design",
        "description": "Third-party Interface Design skill for dashboards, admin panels, SaaS apps, tools, and product interfaces.",
        "source": "Dammyjay93/interface-design",
        "subdir": ".claude/skills/interface-design",
        "ref": "main",
    },
    {
        "name": "stitch-skills",
        "description": "Full Google Stitch Agent Skills bundle for Stitch MCP design, DESIGN.md, React, Remotion, shadcn/ui, and taste-design workflows.",
        "source": "google-labs-code/stitch-skills",
        "ref": "main",
    },
]


def description_for_skill(skill_dir: Path) -> str:
    skill = skill_dir / "SKILL.md"
    for line in skill.read_text(encoding="utf-8").splitlines():
        if line.startswith("description: "):
            return line.removeprefix("description: ").strip().strip('"')
    return f"{skill_dir.name} skill from agentic-packages."


def description_for_package(package_dir: Path) -> str:
    skill = package_dir / "SKILL.md"
    if skill.is_file():
        for line in skill.read_text(encoding="utf-8").splitlines():
            if line.startswith("description: "):
                return line.removeprefix("description: ").strip().strip('"')

    manifest = package_dir / "apm.yml"
    if manifest.is_file():
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if line.startswith("description: "):
                return line.removeprefix("description: ").strip().strip('"')

    return f"{package_dir.name} package from agentic-packages."


def description_for_agent(agent_path: Path) -> str:
    for line in agent_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("description: "):
            return line.removeprefix("description: ").strip().strip('"')
    return f"{agent_path.stem.removesuffix('.agent')} agent from agentic-packages."


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


def build_packages() -> list[dict[str, str]]:
    packages: list[dict[str, str]] = [CORE_PACKAGE]
    for skill_dir in sorted((ROOT / ".apm" / "skills").iterdir()):
        if not (skill_dir / "SKILL.md").is_file():
            continue
        packages.append(
            {
                "name": skill_dir.name,
                "description": description_for_skill(skill_dir),
                "source": LOCAL_SOURCE,
                "subdir": f".apm/skills/{skill_dir.name}",
                "ref": "main",
            }
        )
    for agent_path in sorted((ROOT / ".apm" / "agents").glob("*.agent.md")):
        name = agent_path.name.removesuffix(".agent.md")
        packages.append(
            {
                "name": f"agent-{name}",
                "description": description_for_agent(agent_path),
                "source": LOCAL_SOURCE,
                "subdir": f".apm/agents/{agent_path.name}",
                "ref": "main",
            }
        )
    packages.extend(EXTERNAL_BUNDLES)
    published = {package["name"] for package in packages}
    for package_dir in sorted((ROOT / "packages").iterdir()):
        if not package_dir.is_dir() or package_dir.name in published:
            continue
        packages.append(
            {
                "name": package_dir.name,
                "description": description_for_package(package_dir),
                "source": LOCAL_SOURCE,
                "subdir": f"packages/{package_dir.name}",
                "ref": "main",
            }
        )
        published.add(package_dir.name)
    packages.append(
        {
            "name": "matt-skills",
            "description": "Full Matt Pocock skills package.",
            "source": "mattpocock/skills",
            "ref": "main",
        }
    )
    for name, description, subdir in MATT_SKILLS:
        packages.append(
            {
                "name": name,
                "description": description,
                "source": "mattpocock/skills",
                "subdir": subdir,
                "ref": "main",
            }
        )
    return packages


def build_marketplace_block() -> str:
    packages = build_packages()

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


def source_json(package: dict[str, str]) -> OrderedDict[str, str]:
    source = OrderedDict()
    if subdir := package.get("subdir"):
        source["source"] = "git-subdir"
        source["repo"] = package["source"]
        source["subdir"] = subdir
    else:
        source["source"] = "github"
        source["repo"] = package["source"]
    if ref := package.get("ref"):
        source["ref"] = ref
    return source


def build_marketplace_json() -> dict:
    doc = OrderedDict()
    doc["name"] = "srobroek-agentic"
    doc["owner"] = OrderedDict(
        [
            ("name", "srobroek"),
            ("url", "https://github.com/srobroek"),
        ]
    )
    doc["plugins"] = []
    for package in build_packages():
        plugin = OrderedDict()
        plugin["name"] = package["name"]
        plugin["description"] = package["description"]
        plugin["source"] = source_json(package)
        doc["plugins"].append(plugin)
    return doc


def main() -> int:
    text = APM_YML.read_text(encoding="utf-8")
    marker = "\nmarketplace:\n"
    if marker in text:
        text = text[: text.index(marker)].rstrip() + "\n\n"
    APM_YML.write_text(text.rstrip() + "\n\n" + build_marketplace_block(), encoding="utf-8")
    MARKETPLACE_JSON.write_text(
        json.dumps(build_marketplace_json(), indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"updated {APM_YML}")
    print(f"updated {MARKETPLACE_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
