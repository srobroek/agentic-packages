# Agentic Source Of Truth

Use this context only when the task touches project agent/tooling assets,
generated runtime files, APM package sources, or global bootstrap mirrors. Normal
application code, product docs, specs, infrastructure, and tests use their own
domain context instead.

## Consuming Projects

In a project that consumes this package, `apm.yml` and project-owned `.apm/`
files are the local source of truth for agentic behavior. Runtime files are
generated or installed output:

- `AGENTS.md` and `CLAUDE.md`
- `.codex/agents`, `.codex/hooks`, `.codex/plugins`, `.codex/skills`
- `.claude/agents`, `.claude/commands`, `.claude/hooks`, `.claude/rules`,
  `.claude/skills`
- `.agents/skills`

Change project behavior through `apm.yml`, project-local `.apm/` primitives, or
the upstream package. Do not patch generated runtime files except for an
explicit local emergency repair.

After installing or updating this package in a project, run:

```bash
apm run setup-agentic-tools
```

If that script is missing, use:

```bash
apm install --target claude,codex,agent-skills
apm compile --target codex --no-constitution
apm compile --target claude --no-constitution
python3 apm_modules/_local/agentic-packages/.apm/scripts/patch-runtime-agents.py --all
python3 apm_modules/_local/agentic-packages/.apm/scripts/audit-agentic-assets.py
```

## Package Maintainers

In `srobroek/agentic-packages`, canonical shared asset locations are:

- `.apm/agents/*.agent.md`
- `.apm/skills/*/SKILL.md`
- `.apm/hooks/*` and `.apm/hooks/scripts/*`
- `.apm/instructions/*.instructions.md`
- `.apm/context/*.context.md`
- `.apm/mcp/*`
- `.apm/scripts/*`

Bootstrap skills that must work before project-local APM packages are installed
stay in the chezmoi-managed global skill tree:

- `project-setup`
- `agent-management`
- `chezmoi-editor`
- `find-skills`
- `write-a-skill`
- `catchup`
- `handover`

Chezmoi mirrors under `dotfiles/dot_codex`, `dotfiles/dot_claude`, and
`dotfiles/external-managed/config/agentic-tools` are generated or mirrored
runtime state except for the global bootstrap skills listed above.
