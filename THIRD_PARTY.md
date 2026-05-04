# Third-Party Sources

## VoltAgent awesome-codex-subagents

- Source: https://github.com/VoltAgent/awesome-codex-subagents
- Imported commit: `5f855c11f9117541da31e7274b738cc396d4d3c7`
- License: MIT
- Imported artifacts: Codex subagent TOML files from `categories/*/*.toml`, converted to APM `.agent.md` files under `.apm/agents/`.
- Local changes: model routing, effort metadata, source frontmatter, and steering notes were adapted for current Codex/Claude runtimes.
- License text: `third_party/voltagent-awesome-codex-subagents/LICENSE`

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
  Pocock skills. Do not pin `matt-*` marketplace entries unless a project
  explicitly needs reproducibility for a migration or audit.
- Installation source: upstream `.claude-plugin/plugin.json` marketplace
  plugin, plus upstream `apm.yml`.
- Skills observed during APM verification: `caveman`, `diagnose`, `grill-me`,
  `grill-with-docs`, `improve-codebase-architecture`,
  `setup-matt-pocock-skills`, `tdd`, `to-issues`, `to-prd`, `triage`,
  `write-a-skill`, `zoom-out`.
- Do not add globally by default: several skills overlap local adaptations.
  Let `project-setup` recommend this dependency when the user wants the Matt
  Pocock PRD/issues/TDD workflow set.
- Marketplace exposure: `marketplace.json` includes prefixed `matt-*` entries
  that point to the upstream repository and skill subdirectories. These entries
  reference upstream sources; they do not vendor or copy the skill contents into
  this repository.
