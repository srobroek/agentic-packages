---
name: project-hygiene
description: Audit project-local APM agents, skills, hooks, MCP config, generated steering, and package fit. Use when asked for project hygiene, cleanup, installed agent or skill review, stale generated assets, duplicate tooling, or agentic package drift.
---

# Project Hygiene

Audit whether a project has the right agentic assets installed and whether stale
or unmanaged assets should be removed. This is recommendation-only by default.
Remove, archive, or rewrite files only after the user approves a concrete
cleanup action.

## Workflow

1. Inspect project state:
   - `git status --short`
   - `apm.yml`, `apm.lock.yaml`
   - `.agents/skills`, `.codex/agents`, `.claude/agents`
   - `.agents/contexts`, `.agents/instructions`, `.agents/hooks`
   - `.codex/hooks.json`, `.claude/settings.json`
   - root and scoped `AGENTS.md` files
   - generated `.claude/rules` and any legacy `CLAUDE.md`
2. Resolve APM command: `apm`, else `mise exec -- apm`, else
   `uv tool run --from apm-cli apm`. Stop and report if none work.
3. Use APM marketplace commands for inventory. Do not use guessed searches,
   local package checkouts, or raw `marketplace.json` files for the main
   recommendation source.
4. Compare installed dependencies, lockfile entries, and generated runtime
   assets against selected bundles, package metadata, and project shape.
5. Run non-destructive drift checks when available:
   - `apm install --target claude,codex,agent-skills`
   - `apm compile --target codex`
   - `apm compile --target claude` when Claude is in use
   - package patch/audit scripts when present
6. Identify stale global copies, manually copied runtime assets, duplicate
   skills, obsolete packages, missing bundles, missing MCP config, missing
   hooks, and generated files edited by hand.
7. Check bootstrap leakage: global/bootstrap skills normally remain global
   unless the project is intentionally self-bootstrapping.
8. Check source quality: packages should come from registered APM marketplaces
   or explicit `dependencies.apm`; raw copied third-party assets should be
   removed, replaced, or promoted through `find-tools`.
9. Check generated runtime scope: root `AGENTS.md` should stay minimal when APM
   owns detail, scoped `AGENTS.md` files should be path-specific, and Claude
   rules should not duplicate large global content.
10. Recommend package changes as bundles, extra skills, active agents, MCP
    entries, hooks, or guardrails.
11. Provide exact commands for install, uninstall, prune, compile, patch, and
    audit actions.

## Recommendation Rules

- Prefer fewer bundles plus explicit extras over broad overlapping packages.
- Do not recommend individual skills or agents already included by a selected
  bundle.
- Do not search raw GitHub during hygiene. Hand missing capability discovery to
  `find-tools`.
- For obsolete or weak skills, say whether to remove, replace, merge, or keep as
  bootstrap-only.
- Treat registered external marketplaces as valid project sources. Flag raw
  copied files from those sources as unmanaged unless intentionally forked into
  the first-party package repository.
- Do not encode MCP usage in agent metadata during hygiene. Report missing
  invocation guidance as a parent-orchestrator task.

## Output

Lead with findings ordered by risk, then give recommended changes, optional
additions, stale assets, exact commands, and checks that were skipped or need
approval.
