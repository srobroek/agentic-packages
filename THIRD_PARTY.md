# Third-Party Sources

## VoltAgent sources

- Claude subagents marketplace:
  https://github.com/VoltAgent/awesome-claude-code-subagents
- Agent skills list: https://github.com/VoltAgent/awesome-agent-skills
- Codex subagents list: https://github.com/VoltAgent/awesome-codex-subagents
- License: MIT where declared by the upstream repository.
- APM status: `awesome-claude-code-subagents` is a directly registerable APM
  marketplace as `voltagent-subagents`. `awesome-agent-skills` is a discovery
  source for skill repositories. `awesome-codex-subagents` is a fallback
  discovery source only; expect overlap with `voltagent-subagents`.
- Local policy: do not vendor the VoltAgent agent catalogs into this
  repository. Project setup should register and browse `voltagent-subagents`
  directly when the user wants upstream VoltAgent agents. Curate only narrow
  wrappers or first-party forks when a project needs local model/effort
  metadata, source patches, or an APM-native package for a non-marketplace
  VoltAgent source.
- Design sources: use https://getdesign.md/ instead of the VoltAgent
  `awesome-design-md` list for normal DESIGN.md discovery.

## Matt Pocock skills

- Source: https://github.com/mattpocock/skills
- License: MIT
- APM status: compatible as a direct whole-package `dependencies.apm` entry and
  as individual skill virtual-package dependencies.
- Whole-package form:
  ```yaml
  dependencies:
    apm:
      - mattpocock/skills
  ```
- Individual-skill form:
  ```yaml
  dependencies:
    apm:
      - mattpocock/skills/skills/engineering/tdd
      - mattpocock/skills/skills/engineering/to-issues
  ```
- Version policy: always track the latest upstream default branch for Matt
  Pocock skills with `ref: main`. Do not pin `matt-*` marketplace entries to a
  commit unless a project explicitly needs reproducibility for a migration or
  audit.
- Installation source: upstream `.claude-plugin/plugin.json` marketplace
  plugin, plus upstream `apm.yml`.
- Skills observed during APM verification: `caveman`, `diagnose`, `grill-me`,
  `grill-with-docs`, `improve-codebase-architecture`,
  `setup-matt-pocock-skills`, `tdd`, `to-issues`, `to-prd`, `triage`,
  upstream `write-a-skill`, `zoom-out`.
- Local policy: Matt Pocock skills are the leading source for the observed
  duplicate engineering/productivity skills except skill authoring. Use the
  first-party `write-a-skill` package from this marketplace for skill creation
  and maintenance; do not recommend or expose the upstream Matt write-a-skill as
  an individual package.
- Let `project-setup` recommend this dependency when the user wants the Matt
  Pocock PRD/issues/TDD workflow set.
- Marketplace exposure: `marketplace.json` includes prefixed `matt-*` entries
  that point to the upstream repository and skill subdirectories. These entries
  reference upstream sources; they do not vendor or copy the skill contents into
  this repository.

## Google Stitch skills

- Source: https://github.com/google-labs-code/stitch-skills
- License: Apache-2.0
- APM status: compatible as a direct whole-package `dependencies.apm` entry.
- Whole-package form:
  ```yaml
  dependencies:
    apm:
      - google-labs-code/stitch-skills#main
  ```
- Version policy: always track the latest upstream default branch with
  `ref: main`.
- Skills observed during APM verification: `stitch-design`, `stitch-loop`,
  `design-md`, `enhance-prompt`, `react:components`, `remotion`, `shadcn-ui`,
  and `taste-design`.
- Marketplace exposure: `marketplace.json` includes a single `stitch-skills`
  bundle entry that points to the upstream repository. Individual Stitch skills
  are not re-exposed as separate `srobroek-agentic` packages.
- Local policy: do not vendor or copy Google Stitch skills into this repository
  unless a future project needs a maintained fork with documented local
  modifications.

## Presentation skills

- `ppt-creator`
  - Source: https://github.com/daymade/claude-code-skills
  - Subdir: `daymade-docs/ppt-creator`
  - License: MIT
  - Role: default general-purpose deck creation skill for persuasive,
    data-driven presentations with speaker notes and PPTX output.
- `marp-slide`
  - Source: https://github.com/softaworks/agent-toolkit
  - Subdir: `skills/marp-slide`
  - License: MIT
  - Role: lightweight Marp-specific slide generation with reusable themes and
    image layout guidance.
- `pptx-from-layouts`
  - Source: https://github.com/tristan-mcinnis/pptx-from-layouts-skill
  - Subdir: `.claude/skills/pptx-from-layouts`
  - License: MIT
  - Role: editable PowerPoint generation from markdown using real template
    slide-master layouts and placeholders.
- APM status: exposed as individual marketplace packages and through the local
  `presentation` wrapper bundle.
- Version policy: track latest upstream default branches.
- Local policy: do not keep a first-party presentation skill while these
  upstream packages cover the generic, Marp-specific, and PowerPoint-template
  workflows.

## Diagram skills

- `drawio-skill`
  - Source: https://github.com/Agents365-ai/drawio-skill
  - License: MIT declared in `SKILL.md`.
  - Role: recommended editable/professional diagram workflow for architecture,
    flowcharts, UML, ERD, sequence diagrams, and process diagrams.
  - Quality signal: active as of 2026-04-29, broad platform metadata, examples,
    style presets, and export guidance.
- `excalidraw-diagram-skill`
  - Source: https://github.com/coleam00/excalidraw-diagram-skill
  - License: no repository license file observed during verification.
  - Role: visual explanation and whiteboard-style diagrams where the diagram
    should teach or make an argument.
  - Quality signal: popular small package with render pipeline, references,
    and Playwright-based visual validation; active as of 2026-03-01.
- `d2-diagram`
  - Source: https://github.com/neuro-synapse/network-topology-agent
  - Subdir: `.claude/skills/d2-diagram`
  - License: MIT at repository root.
  - Role: direct D2 replacement for text-authored architecture, flowchart,
    data-flow, database, and topology diagrams.
  - Quality signal: clear D2 references and examples, but weak maintenance
    signal: bundled in a one-commit network-topology repo last committed on
    2025-10-21. Keep it as the D2 option, not the primary diagram package.
- APM status: exposed through the local `diagrams` wrapper bundle and as
  individual marketplace packages.
- Local policy: remove first-party `diagram` and `flowchart` skills. Prefer
  the external packages above; keep D2 validation hooks because they guard any
  `.d2` file regardless of which skill created it.

## Resume and career skills

- `resume-tailoring`
  - Source: https://github.com/varunr89/resume-tailoring-skill
  - Subdir: `skills/resume-tailoring`
  - License: MIT
  - Role: recommended focused resume tailoring workflow, with company research,
    branching experience discovery, matching strategies, and multi-format
    output.
- `tailored-resume-generator`
  - Source: https://github.com/ComposioHQ/awesome-claude-skills
  - Subdir: `tailored-resume-generator`
  - License: upstream repository currently does not declare a GitHub license.
  - Role: popular simple single-skill resume tailoring playbook.
- `resumeskills`
  - Source: https://github.com/Paramchoudhary/ResumeSkills
  - License: MIT
  - Role: broad career-support bundle covering ATS optimization, bullet
    writing, job-description analysis, tailoring, interview prep, negotiation,
    and related workflows.
- APM status: exposed as external marketplace packages. The first-party
  `resume` wrapper bundle installs `resume-tailoring` plus `resumeskills`;
  `tailored-resume-generator` remains individually installable for projects
  that want the simpler popular single-skill prompt.
- Version policy: track latest upstream default branches.
- Local policy: do not keep the previous first-party resume skill because it
  encoded personal/local data sources and paths. Prefer `resume-tailoring` for
  focused resume creation and tailoring; use `resumeskills` when the project
  needs the broader job-search skill set.

## HyperResearch

- Source: https://github.com/jordan-gibbs/hyperresearch
- License: MIT
- APM status: exposed as a third-party bundle entry. The upstream repository is
  primarily a Python package and Claude Code installer, so projects may still
  need `pip install hyperresearch && hyperresearch install` for the full runtime
  assets until an APM-native package shape is provided upstream.
- Version policy: track the latest upstream default branch with `ref: main`.
- Marketplace exposure: `marketplace.json` includes `hyperresearch` pointing to
  the upstream repository.
- Local policy: do not vendor HyperResearch skills, agents, or installer output
  into this repository. If APM install validation shows no runtime assets are
  deployed, create a thin wrapper package only after documenting why direct
  upstream installation is insufficient.

## Impeccable

- Source: https://github.com/pbakaus/impeccable
- License: Apache-2.0
- APM status: exposed as a third-party skill bundle from upstream
  `.agents/skills/impeccable`.
- Version policy: track the latest upstream default branch with `ref: main`.
- Marketplace exposure: `marketplace.json` includes `impeccable` pointing to the
  upstream skill directory.
- Local policy: do not vendor or copy Impeccable into this repository unless a
  future fork is intentionally maintained and documented.

## Interface Design

- Source: https://github.com/Dammyjay93/interface-design
- License: MIT
- APM status: exposed as a third-party skill bundle from upstream
  `.claude/skills/interface-design`.
- Version policy: track the latest upstream default branch with `ref: main`.
- Marketplace exposure: `marketplace.json` includes `interface-design` pointing
  to the upstream skill directory.
- Local policy: do not vendor or copy Interface Design into this repository
  unless a future fork is intentionally maintained and documented.
