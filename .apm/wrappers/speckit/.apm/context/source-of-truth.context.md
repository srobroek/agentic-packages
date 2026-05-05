# Agentic Source Of Truth

Canonical shared asset locations:

- `.apm/agents/*.agent.md`
- `.apm/skills/*/SKILL.md`
- `.apm/hooks/*` and `.apm/hooks/scripts/*`
- `.apm/instructions/*.instructions.md`
- `.apm/context/*.context.md`
- `.apm/mcp/*`
- `.apm/scripts/*`

Global bootstrap exceptions stay in the chezmoi-managed global skill tree
because they must work before project-local APM packages are installed:

- `project-setup`
- `agent-management`
- `chezmoi-editor`
- `find-skills`
- `write-a-skill`
- `catchup`
- `handover`

Generated or legacy runtime locations are not source of truth:

- `.codex/agents`, `.codex/hooks`, `.codex/plugins`, `.codex/skills`
- `.claude/agents`, `.claude/commands`, `.claude/hooks`, `.claude/rules`,
  `.claude/skills`
- `.agents/skills`
- chezmoi mirrors under `dotfiles/dot_codex`, `dotfiles/dot_claude`, and
  `dotfiles/external-managed/config/agentic-tools`, except the global bootstrap
  skills listed above

If a project truly needs local primitives, document the exception in `apm.yml`
before editing the local primitive.
