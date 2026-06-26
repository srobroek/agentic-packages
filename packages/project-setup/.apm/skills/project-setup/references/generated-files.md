# Generated Files

Fill in generated files after scripts finish:

- `apm.yml`
  - selected marketplace packages recorded under `x-agentic.selected_packages`
  - APM-resolved dependencies after `apm install <name>@srobroek-agentic`
  - project-local scripts for install, Codex compile, patch, and audit
  - documented project-local primitive exceptions, if any
- `AGENTS.md`
  - minimal repo-wide guidance when APM generated steering is in use
  - architecture notes and path mapping only when not covered by scoped steering
  - build and run commands
- `.claude/rules`
  - installed by APM for Claude Code
- `CLAUDE.md`
  - do not create by default
  - generate only when explicitly requested with Claude compile
- `specs/`
  - always present
  - full `.specify/` only in full SpecKit mode
- `.codex/config.toml`
  - repo or subtree-scoped Codex overrides
  - shared MCP entries belong in APM unless explicitly project-local
- `justfile`
  - real `dev`, `build`, `test`, and `clean` commands when `just` is selected
- `mise.toml`
  - tool versions when `mise` is selected
- `.moon/`
  - task graph when `moon` is selected
- `.pre-commit-config.yaml`
  - universal hooks and conditional language/IaC/security hooks

Do not recreate Claude-era `.claude/settings.json` unless the user explicitly
selects a project-local Claude configuration.
