---
description: Source-of-truth rule for agentic assets.
applyTo: "{.apm/**,.codex/**,.claude/**,.agents/**,dotfiles/**,chezmoi/**,.chezmoi/**}"
---

# Agentic Source Of Truth

Shared agents, skills, hooks, MCP server definitions, instructions, contexts,
and project-local setup scripts belong in `agentic-packages/.apm/`. Do not
author shared assets in generated runtime folders or chezmoi-managed mirrors.

Bootstrap skills that must work before APM exists in a project are the only
shared exception. They stay global/chezmoi-managed and should remain a small
allowlist: `project-setup`, `agent-management`, `chezmoi-editor`,
`find-skills`, `write-a-skill`, `catchup`, and `handover`.

Project-local exceptions must be intentional and documented in `apm.yml`.
