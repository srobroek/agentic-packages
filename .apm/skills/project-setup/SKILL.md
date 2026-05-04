---
name: project-setup
description: Use when bootstrapping a new repo or adding a package. Interactively selects project shape, stacks, APM setup, tooling, and quality gates before running setup scripts.
---

# Project Setup

Interactive orchestrator. Ask for every configurable setup choice that is not
already supplied, then call the setup scripts with explicit flags. Do not
hand-roll scaffold files when a bundled script can create them.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/project-setup.sh` | Universal scaffold, APM install, project shape, orchestration, quality, Spec mode |
| `scripts/setup-ts.sh` | TypeScript overlay |
| `scripts/setup-rust.sh` | Rust overlay |
| `scripts/setup-python.sh` | Python overlay |
| `scripts/setup-go.sh` | Go overlay |
| `scripts/package-add.sh` | Add package to existing monorepo |
| `scripts/speckit/speckit-setup-all.sh` | Install Speckit extensions |

Read `references/interactive-options.md` before asking questions. Read
language-specific references only for selected languages.

## Workflow

### Phase 1: Interactive Choice Collection

Ask the user for every configurable option not already provided by the prompt or
existing repo state. Group questions when the UI supports it, but do not silently
choose configurable values except documented defaults the user accepts.

Collect:

- project identity: name, directory, owner/org, description, visibility, license
- mode: new repo, add package, or retrofit existing repo
- layout: single project or monorepo
- capabilities/targets: app, service, function, worker, lib, package, schema,
  data, infrastructure, tool, docs
- language overlays and target paths
- stack choices for selected languages/domains
- orchestration flags: just, mise, moon
- package manager choices
- Spec mode: none, lightweight, full
- APM behavior: write config, install, compile Codex, patch/audit, compile Claude
- git/GitHub behavior: init repo, create remote, initial commit/push
- quality/security choices: pre-commit, secret scanning, dependency updates,
  conditional scanners

### Phase 2: Run Scripts With Explicit Flags

Run `scripts/project-setup.sh` using the chosen flags. Then run language overlay
scripts for selected targets. If a script lacks a needed flag, patch the script
instead of hand-creating the missing scaffold.

### Phase 3: Fill Generated Skeletons

Fill only content that depends on project facts:

1. `apm.yml` -- dependency, setup scripts, project-local exceptions.
2. `AGENTS.md` -- minimal repo summary if APM compiled steering owns detail.
3. `justfile` -- real commands when `just` is selected.
4. `mise.toml` -- tools and versions when `mise` is selected.
5. `.moon/` -- task graph when `moon` is selected.
6. `.pre-commit-config.yaml` -- universal and conditional hooks.

Do not create a separate hand-written `CLAUDE.md` by default. Claude Code uses
APM-installed `.claude/rules`; compile Claude only when explicitly selected.

### Phase 4: Verify

Run relevant checks:

- `apm install --target claude,codex,agent-skills`
- `apm compile --target codex`
- APM patch/audit scripts
- selected language tests/checks
- shell syntax checks for changed scripts

### Phase 5: Commit

Ask before committing. If approved, commit with `chore: initial project
scaffold` or a similarly specific setup message.
