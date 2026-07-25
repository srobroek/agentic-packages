# Worktrunk lifecycle contract

## Product ownership

Worktrunk owns creation, lifecycle hooks, ignored-file copying, branch
variables, activity markers, JSON inventory, merge, removal, and logs.
Install its native Claude and Codex plugins through Worktrunk. This package
validates product state; it does not copy plugin hooks.

## Agent allocation

`prepare` performs this blocking sequence:

1. `wt switch --create <branch> --base <base> --no-cd --format=json`.
2. Read the exact branch and absolute path from the switch result, then confirm
   the same top-level `branch`/`path` pair in Worktrunk inventory.
3. Confirm the path is writable and checks out the requested branch.
4. `wt step copy-ignored --from <source> --to <branch> --require-include --format=json`.
5. Store `lease`, `actor`, `runtime`, `agent`, and optional `bead`, `run`, and
   `node` as Worktrunk branch vars.
6. When Beads is active and a Bead was supplied, store durable anchors on it.
7. Reject another active Bead that references the same branch or path.

If any blocking copy, Worktrunk-variable, or self-managed Beads anchor step
fails after creation, `prepare` removes that new checkout with
`wt remove --foreground --force-delete`. It reports the original error plus
any rollback error.

Parent-prepared Beads flows omit `--bead`. The parent stamps the returned
branch/path/base anchors before spawn, binds the runtime, and authorizes only
the agent's T0 claim plus validation. After claiming, the agent validates its
actor and lease against Worktrunk and its branch/path against the Bead. A
self-managed caller may supply `--bead` only after the exact actor claims it.
If the parent's anchor stamp fails, it removes the prepared checkout before
retrying or spawning.

The repository owns `.worktreeinclude`. Its absence is a safe no-op because
`--require-include` prevents an unbounded copy. Secret-bearing files require a
separate owner decision.

A global background `post-start` may run the same allowlisted copy for
interactive checkouts. Writer readiness never depends on that hook:
`prepare` repeats the idempotent step synchronously and waits for its result.

## Runtime contract

| Runtime | Agent launch |
|---|---|
| Claude | Give the agent the existing absolute path. Do not request harness-managed worktree isolation. Bind its returned agent ID before releasing the wait-only brief. |
| Codex | Give the agent the existing absolute path. Bind its returned agent ID, then set each command workdir and every write target beneath the path. |

Every tool-using agent gets a unique actor, lease, and Worktrunk path, including
read-only reviewers and auditors. A reviewer uses a short-lived unique
`review/<scope>-<id>` branch based on the exact target SHA, then removes it after
reporting evidence. It uses a separate review Bead when durable tracking is
needed; it never reuses the writer's Bead. A subagent that never invokes a tool
needs no worktree.

Preparation and explicit validation reject duplicate active Beads. The parent
spawns a wait-only harness agent and binds its returned ID. The bound agent may
claim and validate; repository tools remain blocked by protocol until
validation passes. The `PreToolUse` lease hook joins `agent_id` or
`subagent_id` to the Worktrunk `context`/`contexts` vars, so it rejects a
missing lease, wrong checkout, reused context, or mismatched lease. A
claim-holder may bind wait-only implementation children to its own path and
lease; those children do not receive a Bead or lifecycle authority.
External launchers set
`WORKTRUNK_WRITER_LEASE` and `WORKTRUNK_WRITER_ACTOR`. Primary human operations
in an unleased checkout remain outside the contract.

## Inventory contract

`inventory` runs `wt list --format=json --branches`. Worktrunk 0.62 returns a
top-level array; each checked-out item carries top-level `branch` and `path`.
`--full` adds forge and CI data and may use the network. Consumers must reject
any other shape and join a task to exactly one item by both branch and absolute
path. Activity markers are advisory presence only.

## Merge and removal

Before `wt merge`, confirm task approval, clean worktree state, no active Git
operation, intended head and target, and non-stale required CI. Let Worktrunk
run its merge pipeline. Use `--format=json` and retain the result.

After a remote or squash merge, verify target ancestry or equivalent integrated
content. Run `wt remove --foreground --format=json <branch-or-path>`. Never use
`--force` or `-D` in automation. Fleet cleanup starts with `wt step prune
--dry-run`, cross-checks task references, and removes candidates individually.

## Hooks and approval

Project hooks in `.config/wt.toml` require the user to run `wt config approvals
add`. Agents stop when approval is missing. They never pass `--yes`.

| Hook | Suitable use |
|---|---|
| `pre-switch` / `post-switch` | Personal terminal or IDE routing; navigation notices. |
| `pre-start` / `post-start` | Blocking dependency setup; opt-in servers, watchers, or warm builds. |
| `pre-commit` / `post-commit` | Fast formatting and linting; notifications or CI triggers. |
| `pre-merge` / `post-merge` | Full local quality gate; target-local install or notification. |
| `pre-remove` / `post-remove` | Read-only safety checks or export; external cleanup and notification. |

Hooks prepare, validate, notify, or refuse. They do not claim or close tasks,
acquire merge locks, push task databases, create nested worktrees, or infer
task state from activity markers.

## Logs

- `.git/wt/logs/commands.jsonl` records hook and LLM commands, exits, and duration.
- Branch hook logs diagnose background lifecycle commands.
- `-vv` writes one detailed trace for a failing or slow invocation.

Keep raw Worktrunk logs local. Task comments or audit records store the command
outcome, failure summary, and relevant log path.
