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

1. When `--bead` is used, claim it as the exact `--actor` before preparation. PREPARE the checkout:
   `scripts/worktrunk-writer.py prepare --repo <repo> --branch <branch> --base <base> --source <copy-source> --actor <unique-actor> --lease <unique-token> --runtime <claude|codex> --agent <agent> [--bead <id>] [--run <id>] [--node <id>] [--worktree-path <template>]`.
2. Require `status=ready`. Spawn the harness agent with a wait-only brief in the existing path, without harness worktree isolation. Do not authorize tool use yet.
3. Bind the returned unique harness agent ID: `scripts/worktrunk-writer.py bind --repo <repo> --path <path> --actor <actor> --lease <token> --context <agent-id> [--bead <id>]`. Only `status=bound` authorizes the agent brief.
4. Every tool-using agent runs `scripts/worktrunk-writer.py validate --repo <repo> --path <path> --actor <actor> --lease <token> [--bead <id>]` before its first tool call.
5. For fleet or gate evidence, run `scripts/worktrunk-writer.py inventory --repo <repo> [--full]`; consume only output with `schema=2`.
6. LOAD references/lifecycle.md before merge, removal, hook design, or diagnosing a lifecycle failure.

## Rules

MUST `prepare` complete blocking `copy-ignored --require-include` from the explicit source before delegation.
MUST A read-only reviewer use a unique `review/<scope>-<id>` branch based on the exact target SHA; use a separate review Bead or omit `--bead`.
MUST Every tool-using subagent have its own prepared and bound Worktrunk path, including reviewers and auditors.

MUST A human approve project hooks with `wt config approvals add`; agents never pass `--yes`.
MUST Beads remain optional; when active and `--bead` is supplied, durable anchors are stored there and checked for duplicate active leases.
MUST A Beads-backed lease require an active Bead claimed by the exact agent actor before any anchors are written.

MUST Worktrunk vars contain join fields only; task state, model, and effort stay in the task system or brief.
NOT Copy Worktrunk native plugins, activity markers, lifecycle logs, or task state into this package.
NOT Force-remove a dirty or unintegrated worktree.

OUTPUT
L1 JSON with `status=ready|bound|valid|invalid`, exact branch/path anchors, and evidence paths.
CAP 120w when explaining a failure.
