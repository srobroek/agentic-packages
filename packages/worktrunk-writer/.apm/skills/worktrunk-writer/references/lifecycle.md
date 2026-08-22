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
branch, canonical `worktree`, base, stable actor, and lease before spawn,
waits for the tool-free `WAIT context=<id>` acknowledgement, and binds that
hook-visible context together with the parent-visible routing handle. It
stamps `runtime_handle` and `runtime_context`, then releases the actor with
only `CLAIM {id}`. After claiming under `metadata.actor`, the agent validates its
actor and lease against Worktrunk and its branch/path against the Bead. A
`prepare` and `bind` reject `--bead` outright: activation state reaches
Worktrunk only through `bind --resource`, which requires an unclaimed resource.
For `execution_kind=artifact`, validation also requires an absolute
`artifacts_dir` outside the leased checkout. Disposable checkouts never own
durable run evidence.
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
| Claude | Allocate the existing absolute path. Record the routing handle and wait for `WAIT context=<id>`, then bind both identities. Every Bash call starts with `cd -- <path>` because Agent has no checkout `cwd` field. |
| Codex | Allocate the existing absolute path, bind the routing handle and hook context, then set each command workdir and every write target beneath the path. |

Every tool-using agent gets a unique actor, lease, and Worktrunk path, including
read-only reviewers and auditors. A reviewer uses a short-lived unique
`review/<scope>-<id>` branch based on the exact target SHA, then removes it after
reporting evidence. It uses a separate review Bead when durable tracking is
needed; it never reuses the writer's Bead. A subagent that never invokes a tool
needs no worktree.

Preparation and explicit validation reject duplicate active Beads. The
PreToolUse spawn hook rejects a first task-bearing spawn and names this skill,
so a non-orchestrate parent cannot accidentally create an unleased tool user.
The parent spawns a wait-only harness agent whose bootstrap names its
post-bind release authority. The SubagentStart hook exposes the hook-visible
context without a tool call. The parent binds it with the returned routing
handle, stamps both identities on any activation resource, and only then
resumes the agent.
The bound agent may claim and validate; repository tools remain blocked by
protocol until validation passes. The `PreToolUse` lease hook joins `agent_id` or
`subagent_id` through the context binding; parent resume and message calls
join through the routing handle. It rejects a missing lease, wrong checkout,
reused identity, or mismatched lease. A
Claude Bash call from the inherited parent directory must begin with an
explicit `cd -- <leased-path>`; the hook validates that leading target.
For a claimed `execution_kind=artifact` resource, direct file tools may also
write beneath its exact external `artifacts_dir`. Bash output redirections
are parsed as mutation targets and must remain beneath the leased checkout or
that artifact directory. Other external paths remain denied. A
claim-holder may bind wait-only implementation children to its own path and
lease; those children do not receive a Bead or lifecycle authority.
The routing handle and hook context may be equal, but equality is never
assumed.
External launchers set
`WORKTRUNK_WRITER_LEASE` and `WORKTRUNK_WRITER_ACTOR`. Primary human operations
in an unleased checkout remain outside the contract.

## Inventory contract

`inventory` pins `list.json-schema=2` and runs
`wt list --format=json --branches`. Worktrunk returns an envelope whose `items`
array carries `branch` and, for each checked-out item, `worktree.path`. The
schema-1 top-level array is still accepted as compatibility residue.
`--full` adds forge and CI data and may use the network. Consumers must reject
any other shape and join a task to exactly one item by both branch and absolute
path. Activity markers are advisory presence only.

## State repo resolution

Leases live in the Worktrunk vars of one repository, and an agent's working
directory may sit in another. `bind` records the state repo twice:

- `metadata.repo` on the activation bead. This is the authority.
- an entry in `${XDG_STATE_HOME:-~/.local/state}/worktrunk-writer/contexts.json`,
  keyed by both the runtime context and the routing handle, holding that repo path
  and the bead id.

`hook` and `subagent-exit` resolve the state repo through the index, then read
`metadata.repo` from the named bead. A disagreement between the two, or an
unreadable bead, refuses the call. An identifier with no entry resolves the
repository that owns the caller's working directory, and so does an entry whose
repo path no longer exists: that entry names a deleted checkout rather than a
redirect, so the resolver drops it. `release`, and a `subagent-exit` whose
activation resource is already resolved, delete the entry.

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

### Lease lifecycle hooks

`worktrunk-writer.py lifecycle` is this package's own hook entry point. Add it to
`.config/wt.toml`, then approve it once with `wt config approvals add`:

```toml
[[pre-switch]]
lease-branch-guard = "python3 <skill>/scripts/worktrunk-writer.py lifecycle --event pre-switch --repo {{ primary_worktree_path }} --path {{ worktree_path }} --target {{ branch }}"

[[pre-start]]
lease-stale-release = "python3 <skill>/scripts/worktrunk-writer.py lifecycle --event pre-start --repo {{ primary_worktree_path }} --path {{ worktree_path }}"

[[pre-remove]]
lease-unbind = "python3 <skill>/scripts/worktrunk-writer.py lifecycle --event pre-remove --repo {{ primary_worktree_path }} --path {{ worktree_path }}"
```

| Event | On a leased checkout | Otherwise |
|---|---|---|
| `pre-switch` | Refuses the switch; the stamped `branch` is the lease identity. | Allows |
| `pre-start` | Releases the binding when the activation resource proves the actor finished. | No-op |
| `pre-remove` | Clears the binding so teardown strands nothing. | No-op |

On every event:

- An unleased checkout is a silent no-op. The test is the checkout's own
  `actor`/`lease` vars; `pr-shepherd`, standalone reviewers, and humans all hold
  leases without a run marker.
- Any internal error fails open. Lease bookkeeping must never stop a worktree
  from starting.

`pre-switch` only sees `wt switch`. A raw `git switch` bypasses Worktrunk, so the
PreToolUse guard stays the backstop for agents.

Releasing on `pre-start` never guesses liveness, because a slow actor and a dead
one look identical from inventory. It asks the task system instead:

- Resource closed, or unassigned and not in progress: release.
- Missing resource, missing `bd`, or any error: leave the binding alone.
- Actor died without unassigning: an explicit `release` call.

## Logs

- `.git/wt/logs/commands.jsonl` records hook and LLM commands, exits, and duration.
- Branch hook logs diagnose background lifecycle commands.
- `-vv` writes one detailed trace for a failing or slow invocation.

Keep raw Worktrunk logs local. Task comments or audit records store the command
outcome, failure summary, and relevant log path.
