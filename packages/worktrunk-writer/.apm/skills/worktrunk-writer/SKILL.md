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
   `scripts/worktrunk-writer.py prepare --repo <repo> --branch <branch> --base <base> --source <copy-source> --actor <unique-actor> --lease <unique-token> --runtime <claude|codex> --agent <agent> [--run <id>] [--node <id>] [--worktree-path <template>]`. `prepare` is parent-managed and rejects `--bead`; the activation resource stays unassigned until the worker claims it.
2. Require `status=ready`. Allocate an ordinary tool user with exactly:
   ```text
   WAIT checkout={path}
   Do not invoke tools or start work.
   The controlling parent will send your task after binding your Worktrunk lease.
   ```
   A protocol-owning package may extend this canonical WAIT with its resource identity and release verb. The pre-spawn hook rejects task-bearing first spawns and unprepared paths.
3. Record the parent-visible spawn handle. The waiting actor replies exactly `WAIT context={hook-visible-id}` through the `SubagentStart` handshake without invoking a tool. Bind both identities without `--bead`: `scripts/worktrunk-writer.py bind --repo {repo} --path {path} --actor {actor} --lease {token} --handle {runtime-handle} --ack 'WAIT context={hook-visible-id}'`. Require `status=bound`.
4. Store `runtime_handle` and `runtime_context` on a Beads activation resource and read both back. Resume an ordinary agent with its task, or send exactly `CLAIM {id}` for bead-as-brief activation. An Agent resume is admitted only for a bound handle; bead-as-brief SendMessage is guarded by its orchestration package.
5. The agent validates with `scripts/worktrunk-writer.py validate --repo {repo} --path {path} --actor {actor} --lease {token} [--bead {id}]` before repository tools. When the harness has no `cwd` field, every Bash call starts with `cd -- {path}`; file tools use absolute paths beneath it. Artifact nodes also require an absolute `artifacts_dir` outside the leased checkout. File writes and Bash output redirections outside the checkout and stamped artifact directory are denied.
6. A claim-holder may spawn a wait-only implementation child in its own path, then bind the child's handle and hook context with the same actor and lease. The child never receives `--bead`.
7. For fleet or gate evidence, run `scripts/worktrunk-writer.py inventory --repo <repo> [--full]`; it pins `list.json-schema=2` and reads `branch` plus `worktree.path`.
8. LOAD references/lifecycle.md before merge, removal, hook design, or diagnosing a lifecycle failure.

## Rules

MUST `prepare` complete blocking `copy-ignored --require-include` from the explicit source before delegation.
MUST Roll back the newly created checkout when blocking copy or lease setup fails.
MUST A read-only reviewer use a unique `review/<scope>-<id>` branch based on the exact target SHA; use a separate review Bead or omit `--bead`.
MUST Every independently dispatched tool user have its own prepared path; a claim-holder's explicitly bound child may share that parent's path and lease.
MUST Treat `runtime_handle` as the parent's routing identity and `runtime_context` as the hook identity; never infer one from the other.

MUST A human approve project hooks with `wt config approvals add`; agents never pass `--yes`.
MUST `prepare` and `bind` reject `--bead`; pass the unclaimed `--resource` to `bind` instead.

MUST Worktrunk vars contain join fields only; task state, model, and effort stay in the task system or brief.
NOT Copy Worktrunk native plugins, activity markers, lifecycle logs, or task state into this package.
NOT Force-remove a dirty or unintegrated worktree.

OUTPUT
L1 JSON with `status=ready|bound|valid|invalid`, exact branch/path anchors, and evidence paths.
CAP 120w when explaining a failure.
