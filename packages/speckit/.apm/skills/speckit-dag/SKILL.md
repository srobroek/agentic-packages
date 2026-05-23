---
name: speckit-dag
description: Delivery skill for the SpecKit per-command DAG hook dispatcher and node library. Not invoked directly by the agent — the dispatcher fires automatically via Claude Code / Codex hooks declared in packages/speckit/.apm/hooks/.
---

# SpecKit DAG

This skill exists to ship the per-command DAG infrastructure to consumer
projects via APM. It is not invoked directly through Claude's Skill
tool; activation happens through the hook layer.

## What ships

- `scripts/dispatcher.sh` — Claude Code / Codex hook handler. Reads a
  node markdown corresponding to the current `/speckit.<id>` invocation
  and either injects context (soft steering) or returns a block decision
  (hard steering).
- `nodes/_index.md` — overview of the node format and the conventions
  the dispatcher reads (`HARD-MISSING:`, `HARD-EXISTS:`,
  `HARD-DEPRECATED:`, `<feat>` placeholder, class-based predecessors).
- `nodes/<id>.pre.md` (~75 files) — pre-tool phase: predecessors +
  preconditions for `/speckit.<id>`. Hard blocks live here.
- `nodes/<id>.post.md` (~75 files) — post-tool phase: successors +
  postconditions + conditional branching for `/speckit.<id>`.

## Wiring

Hook entries in `packages/speckit/.apm/hooks/speckit-claude-hooks.json`
and `speckit-codex-hooks.json` point at `dispatcher.sh` via relative
paths. APM rewrites those paths to the deployed location during
`apm install`. The dispatcher resolves `nodes/` as a sibling of its own
`scripts/` directory at runtime.

## Why a skill (and not a free-standing hooks directory)

APM ships full skill subtrees end-to-end (mirrors the package layout
into `.claude/skills/<name>/`). A hook JSON in `.apm/hooks/` only ships
the specific files referenced as `command` targets — sibling
directories like `nodes/` are skipped. Packaging the dispatcher and the
node library as a skill is the cleanest way to guarantee both the
script and its data files reach the consumer project together.
