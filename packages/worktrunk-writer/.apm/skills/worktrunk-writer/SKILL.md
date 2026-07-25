---
name: worktrunk-writer
description: Use when delegating a tool-using agent, reviewer, or repository worker into an isolated Worktrunk lease.
---

# Worktrunk Writer

TRIGGER
+ delegate a tool-using repository agent in its own worktree
+ run a read-only reviewer or auditor against a repository
+ validate an agent lease or inspect agent worktrees
+ merge or remove a delegated agent checkout
- navigate to an ordinary worktree interactively → use Worktrunk directly

## Workflow

1. PREPARE without `--bead` when the parent must create the checkout before the agent claims:
   `scripts/worktrunk-writer.py prepare --repo <repo> --branch <branch> --base <base> --source <copy-source> --actor <unique-actor> --lease <unique-token> --runtime <claude|codex> --agent <agent> [--run <id>] [--node <id>] [--worktree-path <template>]`. A self-managed actor may pass `--bead` only after claiming it.
2. Require `status=ready`. Store the returned branch/path/base anchors on the unclaimed Bead, then spawn the harness agent with a wait-only brief in that path and without harness isolation.
3. Bind the returned agent ID without `--bead`: `scripts/worktrunk-writer.py bind --repo <repo> --path <path> --actor <actor> --lease <token> --context <agent-id>`. `status=bound` authorizes the T0 claim and validation only.
4. The agent claims its Bead as the exact actor, then runs `scripts/worktrunk-writer.py validate --repo <repo> --path <path> --actor <actor> --lease <token> --bead <id>`. Require `status=valid` before repository tools. A no-Bead reviewer validates without `--bead`.
5. A claim-holder may spawn a wait-only implementation child in its own path, then bind the returned child ID with the same path/actor/lease before releasing it. The child never receives `--bead`.
6. For fleet or gate evidence, run `scripts/worktrunk-writer.py inventory --repo <repo> [--full]`; consume only a Worktrunk 0.62 JSON array with top-level `branch` and `path`.
7. LOAD references/lifecycle.md before merge, removal, hook design, or diagnosing a lifecycle failure.

## Rules

MUST `prepare` complete blocking `copy-ignored --require-include` from the explicit source before delegation.
MUST Roll back the newly created checkout when blocking copy or lease setup fails.
MUST A read-only reviewer use a unique `review/<scope>-<id>` branch based on the exact target SHA; use a separate review Bead or omit `--bead`.
MUST Every independently dispatched tool user have its own prepared path; a claim-holder's explicitly bound child may share that parent's path and lease.

MUST A human approve project hooks with `wt config approvals add`; agents never pass `--yes`.
MUST Beads remain optional; parent-prepared flows stamp checkout anchors before spawn, then validate the agent's atomic claim against them.
MUST A self-managed `prepare --bead` require an active Bead claimed by the exact actor.

MUST Worktrunk vars contain join fields only; task state, model, and effort stay in the task system or brief.
NOT Copy Worktrunk native plugins, activity markers, lifecycle logs, or task state into this package.
NOT Force-remove a dirty or unintegrated worktree.

OUTPUT
L1 JSON with `status=ready|bound|valid|invalid`, exact branch/path anchors, and evidence paths.
CAP 120w when explaining a failure.
