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


def unquote_yaml_scalar(value: str) -> str:
    return value.strip().strip('"').strip("'")


def core_package() -> dict[str, str]:
    return {
        "name": "core",
        "description": description_for_package(ROOT / "packages" / "core"),
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
        "subdir": "plugins/stitch-design",
        "ref": "main",
    },
]


# Third-party agents from msitarzewski/agency-agents (MIT, AgentLand Contributors).
# Opt-in only; not auto-installed. See THIRD_PARTY.md.
AGENCY_AGENTS = [
    # engineering → data-ai
    ("agency-database-optimizer", "Database schema, query, indexing, and partitioning specialist for Postgres, MySQL, and managed Postgres/MySQL platforms.", "engineering/engineering-database-optimizer.md"),
    ("agency-data-engineer", "ETL/ELT, lakehouse, Spark, dbt, and streaming pipeline design and implementation.", "engineering/engineering-data-engineer.md"),
    ("agency-ai-engineer", "ML model development, deployment, and AI-powered feature integration.", "engineering/engineering-ai-engineer.md"),
    ("agency-ai-data-remediation", "Self-healing data pipelines that detect and repair upstream data quality issues via local SLMs.", "engineering/engineering-ai-data-remediation-engineer.md"),
    ("agency-voice-ai", "Whisper/ASR pipelines, diarization, transcription, and subtitle generation for voice AI.", "engineering/engineering-voice-ai-integration-engineer.md"),
    # engineering → infrastructure
    ("agency-devops-automator", "Infrastructure as code, CI/CD pipeline, and cloud ops automation.", "engineering/engineering-devops-automator.md"),
    ("agency-sre", "Site reliability engineering with SLOs, error budgets, observability, and chaos engineering.", "engineering/engineering-sre.md"),
    # engineering → security
    ("agency-security-engineer", "Application security, threat modeling, and secure code review specialist.", "engineering/engineering-security-engineer.md"),
    ("agency-threat-detection", "SIEM rule authoring, MITRE ATT&CK coverage, and detection-as-code workflows.", "engineering/engineering-threat-detection-engineer.md"),
    # engineering → docs-architecture
    ("agency-technical-writer", "Developer documentation, API references, READMEs, and tutorial authoring.", "engineering/engineering-technical-writer.md"),
    ("agency-software-architect", "System design, domain-driven design, and architectural pattern selection.", "engineering/engineering-software-architect.md"),
    ("agency-backend-architect", "Scalable backend systems, database architecture, API surface, and cloud topology design.", "engineering/engineering-backend-architect.md"),
    # engineering → frontend
    ("agency-frontend-developer", "React, Vue, and Angular frontend implementation, modern web performance, and bundling.", "engineering/engineering-frontend-developer.md"),
    # engineering → language-arm-cortex
    ("agency-embedded-firmware", "Embedded firmware for ESP32, STM32, Nordic, FreeRTOS, and Zephyr targets.", "engineering/engineering-embedded-firmware-engineer.md"),
    # engineering → planning-product
    ("agency-rapid-prototyper", "Fast proof-of-concept and MVP development to validate ideas before production investment.", "engineering/engineering-rapid-prototyper.md"),
    # testing → frontend
    ("agency-accessibility-auditor", "WCAG and screen-reader accessibility auditor; defaults to declaring UIs not accessible until proven otherwise.", "testing/testing-accessibility-auditor.md"),
    # testing → quality
    ("agency-api-tester", "API validation, performance, and quality assurance testing.", "testing/testing-api-tester.md"),
    ("agency-performance-benchmarker", "Performance measurement, benchmarking, and optimization analysis.", "testing/testing-performance-benchmarker.md"),
    ("agency-test-results-analyzer", "Quality metrics analysis and trend detection from accumulated test runs.", "testing/testing-test-results-analyzer.md"),
    ("agency-evidence-collector", "Screenshot-obsessed QA verifier; requires visual proof before accepting that a feature works.", "testing/testing-evidence-collector.md"),
    # testing → planning-product
    ("agency-workflow-optimizer", "Process improvement and automation opportunity analysis for engineering and ops workflows.", "testing/testing-workflow-optimizer.md"),
    # design (new bundle)
    ("agency-brand-guardian", "Brand identity consistency review and strategic brand positioning.", "design/design-brand-guardian.md"),
    ("agency-ui-designer", "Visual design system, component library, and UI surface composition.", "design/design-ui-designer.md"),
    ("agency-ux-architect", "Technical UX architecture, foundational CSS system, and design-to-code translation.", "design/design-ux-architect.md"),
    ("agency-ux-researcher", "User research, usability testing planning, and data-driven UX insights.", "design/design-ux-researcher.md"),
    ("agency-image-prompt-engineer", "Crafts precise, evocative prompts for AI image generation tools.", "design/design-image-prompt-engineer.md"),
    ("agency-inclusive-visuals", "Defeats AI image bias for representative, inclusive imagery and video.", "design/design-inclusive-visuals-specialist.md"),
    ("agency-visual-storyteller", "Visual narrative construction and multimedia content design.", "design/design-visual-storyteller.md"),
    ("agency-whimsy-injector", "Adds personality, delight, and playful brand moments to product surfaces.", "design/design-whimsy-injector.md"),
    # product → planning-product
    ("agency-product-manager", "End-to-end product lifecycle management and roadmap ownership.", "product/product-manager.md"),
    ("agency-sprint-prioritizer", "Agile sprint prioritization and velocity management.", "product/product-sprint-prioritizer.md"),
    ("agency-trend-researcher", "Market intelligence and opportunity assessment for product strategy.", "product/product-trend-researcher.md"),
    ("agency-feedback-synthesizer", "Multi-channel feedback aggregation and conversion into actionable product insights.", "product/product-feedback-synthesizer.md"),
    ("agency-behavioral-nudge", "Behavioral psychology specialist for adaptive interaction cadences and engagement design.", "product/product-behavioral-nudge-engine.md"),
    # project-management (new bundle)
    ("agency-senior-pm", "Senior project manager translating specs to tasks, tracking project memory, and reality-checking scope.", "project-management/project-manager-senior.md"),
    ("agency-project-shepherd", "Cross-functional project coordination and stakeholder alignment.", "project-management/project-management-project-shepherd.md"),
    ("agency-studio-producer", "Senior creative and technical portfolio orchestration across studio projects.", "project-management/project-management-studio-producer.md"),
    ("agency-studio-operations", "Day-to-day studio operations and efficiency management.", "project-management/project-management-studio-operations.md"),
    ("agency-experiment-tracker", "A/B test design, tracking, and result interpretation.", "project-management/project-management-experiment-tracker.md"),
    ("agency-jira-steward", "Enforces Jira-linked Git workflows, ticket hygiene, and traceability.", "project-management/project-management-jira-workflow-steward.md"),
    # marketing (new bundle, Western/global only)
    ("agency-content-creator", "Multi-platform editorial content creator across blogs, social, and long-form.", "marketing/marketing-content-creator.md"),
    ("agency-growth-hacker", "Viral loop design, funnel optimization, and growth experiment execution.", "marketing/marketing-growth-hacker.md"),
    ("agency-seo-specialist", "Technical SEO, content optimization, and link strategy.", "marketing/marketing-seo-specialist.md"),
    ("agency-social-media-strategist", "Cross-platform professional social campaign strategy.", "marketing/marketing-social-media-strategist.md"),
    ("agency-linkedin-creator", "LinkedIn thought leadership and personal brand content.", "marketing/marketing-linkedin-content-creator.md"),
    ("agency-reddit-builder", "Authentic Reddit community engagement and culture-aware moderation.", "marketing/marketing-reddit-community-builder.md"),
    ("agency-instagram-curator", "Instagram visual storytelling, community, and multi-format content strategy.", "marketing/marketing-instagram-curator.md"),
    ("agency-tiktok-strategist", "TikTok viral content, algorithm, and community growth strategy.", "marketing/marketing-tiktok-strategist.md"),
    ("agency-twitter-engager", "Real-time Twitter/X engagement and viral thread authoring.", "marketing/marketing-twitter-engager.md"),
    ("agency-podcast-strategist", "Podcast positioning, distribution, and monetization strategy.", "marketing/marketing-podcast-strategist.md"),
    ("agency-app-store-optimizer", "App Store Optimization and mobile app discoverability.", "marketing/marketing-app-store-optimizer.md"),
    ("agency-ai-citation", "Answer-engine and generative-engine optimization for visibility in ChatGPT, Claude, Gemini, and Perplexity.", "marketing/marketing-ai-citation-strategist.md"),
    ("agency-agentic-search", "WebMCP readiness audits and AI agent task-completion optimization for web surfaces.", "marketing/marketing-agentic-search-optimizer.md"),
    ("agency-book-co-author", "Thought-leadership book chapter co-authoring for founders and executives.", "marketing/marketing-book-co-author.md"),
    ("agency-carousel-growth", "Autonomous TikTok and Instagram carousel generation with analytics feedback loop.", "marketing/marketing-carousel-growth-engine.md"),
    ("agency-video-optimization", "YouTube algorithm, retention, and thumbnail optimization.", "marketing/marketing-video-optimization-specialist.md"),
    ("agency-short-video-editor", "Short-video post-production coaching for CapCut Pro, Premiere, DaVinci, and FCP.", "marketing/marketing-short-video-editing-coach.md"),
    # finance (new bundle)
    ("agency-bookkeeper", "Daily accounting, month-end close, GAAP discipline, and audit readiness.", "finance/finance-bookkeeper-controller.md"),
    ("agency-financial-analyst", "Financial modeling, forecasting, and scenario analysis.", "finance/finance-financial-analyst.md"),
    ("agency-fpa-analyst", "Budgeting, variance analysis, and rolling forecasts for FP&A.", "finance/finance-fpa-analyst.md"),
    ("agency-investment-researcher", "Market research, due diligence, and valuation work for investments.", "finance/finance-investment-researcher.md"),
    ("agency-tax-strategist", "Multi-jurisdictional tax planning and transfer pricing strategy.", "finance/finance-tax-strategist.md"),
    ("agency-finance-tracker", "Financial planning, budget tracking, and cash flow oversight.", "support/support-finance-tracker.md"),
    ("agency-accounts-payable", "Autonomous vendor payment processing across fiat, crypto, and stablecoins.", "specialized/accounts-payable-agent.md"),
    # game-development (new bundle)
    ("agency-game-designer", "Game design document authoring, economy design, and gameplay loop planning.", "game-development/game-designer.md"),
    ("agency-game-audio", "Game audio engineering with FMOD, Wwise, and adaptive music systems.", "game-development/game-audio-engineer.md"),
    ("agency-level-designer", "Level layout, pacing, and encounter design for games.", "game-development/level-designer.md"),
    ("agency-narrative-designer", "Branching dialogue, lore, and narrative system design.", "game-development/narrative-designer.md"),
    ("agency-technical-artist", "Game art-to-engine pipeline, tooling, and shader integration.", "game-development/technical-artist.md"),
    ("agency-blender-addon", "Blender Python add-on engineering, exporters, and tooling.", "game-development/blender/blender-addon-engineer.md"),
    ("agency-godot-gameplay", "Godot GDScript 2.0 gameplay scripting and signals architecture.", "game-development/godot/godot-gameplay-scripter.md"),
    ("agency-godot-multiplayer", "Godot MultiplayerAPI, ENet, and WebRTC multiplayer engineering.", "game-development/godot/godot-multiplayer-engineer.md"),
    ("agency-godot-shader", "Godot CanvasItem and Spatial shader development.", "game-development/godot/godot-shader-developer.md"),
    ("agency-roblox-avatar", "Roblox UGC avatar creation pipeline.", "game-development/roblox-studio/roblox-avatar-creator.md"),
    ("agency-roblox-experience", "Roblox experience design with engagement and monetization focus.", "game-development/roblox-studio/roblox-experience-designer.md"),
    ("agency-roblox-systems", "Roblox Luau systems scripting with RemoteEvents and DataStore.", "game-development/roblox-studio/roblox-systems-scripter.md"),
    ("agency-unity-architect", "Unity ScriptableObject-driven modular architecture design.", "game-development/unity/unity-architect.md"),
    ("agency-unity-editor", "Unity EditorWindow, PropertyDrawer, and editor tooling development.", "game-development/unity/unity-editor-tool-developer.md"),
    ("agency-unity-multiplayer", "Unity Netcode for GameObjects and UGS multiplayer engineering.", "game-development/unity/unity-multiplayer-engineer.md"),
    ("agency-unity-shader", "Unity Shader Graph and HLSL authoring for URP and HDRP.", "game-development/unity/unity-shader-graph-artist.md"),
    ("agency-unreal-multiplayer", "Unreal replication, GameMode, and GameState multiplayer architecture.", "game-development/unreal-engine/unreal-multiplayer-architect.md"),
    ("agency-unreal-systems", "Unreal C++ and Blueprint systems engineering with Nanite, Lumen, and GAS.", "game-development/unreal-engine/unreal-systems-engineer.md"),
    ("agency-unreal-tech-art", "Unreal Material Editor, Niagara VFX, and PCG technical art.", "game-development/unreal-engine/unreal-technical-artist.md"),
    ("agency-unreal-world-builder", "Unreal World Partition, Landscape, and HLOD world construction.", "game-development/unreal-engine/unreal-world-builder.md"),
    # worldbuilding (new bundle)
    ("agency-anthropologist", "Cultural systems, rituals, kinship, and ethnographic method for worldbuilding.", "academic/academic-anthropologist.md"),
    ("agency-geographer", "Physical and human geography, climate, cartography, and spatial analysis for worldbuilding.", "academic/academic-geographer.md"),
    ("agency-historian", "Historical analysis, periodization, material culture, and historiography for worldbuilding.", "academic/academic-historian.md"),
    ("agency-narratologist", "Narrative theory, story structure, and character arc analysis from Propp to Campbell.", "academic/academic-narratologist.md"),
    ("agency-psychologist", "Personality theory, motivation, and cognitive patterns for psychologically credible characters.", "academic/academic-psychologist.md"),
    # support → planning-product, security, infrastructure
    ("agency-analytics-reporter", "Dashboard authoring, KPI definition, and statistical analysis.", "support/support-analytics-reporter.md"),
    ("agency-exec-summary", "Executive summaries in McKinsey SCQA, BCG Pyramid, and Bain frameworks for C-suite consumption.", "support/support-executive-summary-generator.md"),
    ("agency-legal-compliance", "Multi-jurisdiction regulatory compliance review.", "support/support-legal-compliance-checker.md"),
    ("agency-infra-maintainer", "Reliability, performance optimization, and ops maintenance for infrastructure.", "support/support-infrastructure-maintainer.md"),
    # specialized → agentic-maintenance
    ("agency-mcp-builder", "Designs, builds, and tests Model Context Protocol servers.", "specialized/specialized-mcp-builder.md"),
    ("agency-workflow-architect", "Maps complete workflow trees and produces build-ready automation specifications.", "specialized/specialized-workflow-architect.md"),
    ("agency-agents-orchestrator", "Autonomous pipeline manager that orchestrates multi-agent development workflows.", "specialized/agents-orchestrator.md"),
    ("agency-automation-governance", "n8n-first automation governance, audit trails, and policy enforcement.", "specialized/automation-governance-architect.md"),
    ("agency-identity-graph", "Canonical entity resolution and identity graph operation across multi-agent systems.", "specialized/identity-graph-operator.md"),
    ("agency-agentic-identity", "Identity, authentication, and trust architecture for autonomous agents.", "specialized/agentic-identity-trust.md"),
    # specialized → docs-architecture
    ("agency-zk-steward", "Zettelkasten knowledge-base steward operating in Luhmann, Feynman, Munger, or Ogilvy mode.", "specialized/zk-steward.md"),
    ("agency-developer-advocate", "Developer relations, developer experience, and platform adoption advocacy.", "specialized/specialized-developer-advocate.md"),
    ("agency-document-generator", "Code-based PDF, PPTX, DOCX, and XLSX generation with charts and tables.", "specialized/specialized-document-generator.md"),
    # specialized → security
    ("agency-compliance-auditor", "SOC2, ISO 27001, HIPAA, and PCI-DSS compliance auditing.", "specialized/compliance-auditor.md"),
    # specialized → data-ai
    ("agency-model-qa", "Independent ML and statistical model audit, replication, and validation.", "specialized/specialized-model-qa.md"),
    ("agency-data-consolidation", "Consolidates sales and operational data into reporting dashboards.", "specialized/data-consolidation-agent.md"),
    ("agency-report-distribution", "Automates territorial and segmented report distribution to stakeholders.", "specialized/report-distribution-agent.md"),
    ("agency-sales-data-extraction", "Monitors Excel files and extracts MTD, YTD, and Year-End sales metrics.", "specialized/sales-data-extraction-agent.md"),
]


def description_for_skill(skill_dir: Path) -> str:
    skill = skill_dir / "SKILL.md"
    for line in skill.read_text(encoding="utf-8").splitlines():
        if line.startswith("description: "):
            return unquote_yaml_scalar(line.removeprefix("description: "))
    return f"{skill_dir.name} skill from agentic-packages."


def description_for_package(package_dir: Path) -> str:
    skill = package_dir / "SKILL.md"
    if skill.is_file():
        for line in skill.read_text(encoding="utf-8").splitlines():
            if line.startswith("description: "):
                return unquote_yaml_scalar(line.removeprefix("description: "))

    manifest = package_dir / "apm.yml"
    if manifest.is_file():
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if line.startswith("description: "):
                return unquote_yaml_scalar(line.removeprefix("description: "))

    return f"{package_dir.name} package from agentic-packages."


def description_for_agent(agent_path: Path) -> str:
    for line in agent_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("description: "):
            return unquote_yaml_scalar(line.removeprefix("description: "))
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
    packages: list[dict[str, str]] = [core_package()]
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
    for name, description, subdir in AGENCY_AGENTS:
        packages.append(
            {
                "name": name,
                "description": description,
                "source": "msitarzewski/agency-agents",
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
