---
name: agent-management
description: Manage APM-backed project agents, skills, hooks, steering, bundles, and package dependencies. Use when a repo already has or is about to get apm.yml and the task is to add, update, remove, install, compile, patch, or audit agentic assets.
---

# Agent Management

Low-level bootstrap workflow for APM package operations. Use this after a setup
or retrofit path has selected APM as the source of truth.

## Scope

- Owns: `apm.yml` dependency edits, installs, compiles, runtime finalizers, and
  drift/audit reporting for APM-backed assets.
- Routes new repositories to `project-setup`.
- Routes existing repository ingestion to `brownfield-project`.
- Routes missing capability discovery to `find-tools`.
- Routes stale or duplicated asset review to `project-hygiene`.

## Workflow

1. Inspect `git status --short`, `apm.yml`, `apm.lock.yaml`, generated runtime
   folders, hook config, and root/scoped `AGENTS.md` files.
2. Resolve APM in order: `apm`, `mise exec -- apm`,
   `uv tool run --from apm-cli apm`. Stop and report if none work.
3. Confirm the source of truth before editing. Prefer APM marketplace packages
   over copied runtime assets.
4. Add, update, or remove selected packages through APM commands when possible;
   edit `apm.yml` only for project-local metadata or explicit dependency forms.
5. Run the relevant install/compile/finalizer checks:
   - `apm install --target claude,codex,agent-skills`
   - `apm compile --target codex`
   - `apm compile --target claude` only when Claude Code is in use
   - package patch/audit scripts when present
6. Report changed source files, generated outputs, warnings, skipped checks, and
   any follow-up hygiene work.

## Rules

- Do not edit generated runtime copies such as `.codex/agents`,
  `.claude/agents`, `.agents/skills`, `.claude/rules`, or compiled `AGENTS.md`
  unless repairing a broken install with explicit approval.
- Do not create global agents. Agents are project-explicit through APM.
- Keep bootstrap skills global only when they are needed before project-local
  APM skills exist.
- For coding/development agents, do not bake MCP usage into agent metadata.
  Tell the parent orchestrator to pass task-specific guidance at invocation.
