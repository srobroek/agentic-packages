# Bootstrap Skills

Bootstrap skills are the small set of globally available skills that must work
before a project has installed `agentic-packages` through APM. Everything else
should be installed project-locally by APM unless it is a Codex system skill.

## Keep Global

- `project-setup`: creates or retrofits projects, writes `apm.yml`, runs
  `apm install`, runs `apm compile`, and patches/audits runtime agents.
- `agent-management`: manages APM package discovery, bundle selection,
  `apm.yml` dependency edits, installs, compiles, patches, and audits for new
  or unmanaged projects.
- `brownfield-project`: ingests an existing repository into APM-managed project
  tooling without broad scaffolding.
- `chezmoi-editor`: edits the chezmoi-managed source for global bootstrap
  assets and user dotfiles. It is needed even outside an APM-managed project.
- `find-tools`: finds bootstrap or APM package sources for skills, agents, MCP
  servers, connectors, and reusable tools before project-local skills exist.
- `project-hygiene`: audits installed project-local agents, skills, hooks, MCP
  config, generated steering, and recommended missing packages.
- `write-a-skill`: creates or repairs bootstrap/APM package skills before
  project-local skills exist. Normal project skill authoring should route to
  the APM package repository.
- `catchup`: restores context in unmanaged directories and before project-local
  skills are installed.
- `handover`: saves recovery context regardless of whether the current directory
  is APM-managed.

## Usually Project-Local Through APM

- code exploration, code review, quality, design, diagramming, research,
  GitHub, SpecKit, prompt, UI, and language-specific skills.
- lifecycle helpers such as commit, verify, triage, diagnose, sniff, and
  architecture review once a project is APM-managed.

## Pruned

- `memory-prune`: removed from the bootstrap set and package set.
- `setup-matt-pocock-skills`: keep as a tracked external-source candidate in
  the APM package repository, not as a global bootstrap skill.
