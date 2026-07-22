# Landing contract

`scripts/landing-contract.sh` is the executable boundary shared by standalone
shepherds and orchestration adapters. Callers supply durable identity; the
script owns live GitHub checks, queue order, exact-head merge, proof, and
recovery writes.

## Durable identity

| Key | Meaning |
|---|---|
| `repo` | GitHub `owner/name` |
| `pr` | Pull request number |
| `branch` | Author branch |
| `pr_base` | Current GitHub target branch, including a stack parent |
| `landing_base` | Branch on which final landing must be proved |
| `base_sha` | Recorded landing-base commit used for content proof |
| `head_sha` | Exact reviewed and tested PR head |
| `merge_sha` | GitHub merge commit, stamped immediately after merge |

A `gh:run` gate stores its run id and the same `head_sha`. Gate resolution is
advisory. Validate it with:

```bash
scripts/landing-contract.sh check-run <repo> <run-id> <head-sha>
```

`check-pr` reads current PR state directly. Approval mode is `github` by
default. An orchestrated adapter may pass `external` only after a durable
independent approval names the exact head. Both modes reject requested changes.

## Exit contract

| Exit | Meaning | Caller action |
|---:|---|---|
| 0 | Exact proof passed | Continue or close as reported |
| 2 | Unknown, malformed, or unavailable evidence | Comment, release claim, report |
| 10 | Pending, or stacked merge not yet on final base | Preserve gate/hold, release claim |
| 11 | Stale SHA or PR-base identity | Keep gate open, release claim |
| 12 | Failed check, conflict, or foreign slot owner | Bounce or report contention |
| 75 | Slot not acquired without violating persisted order | Release claim; retry later |

## Landing transaction

```bash
scripts/landing-contract.sh land \
  <merge-bead> <repo> <pr> <pr-base> <landing-base> \
  <base-sha> <head-sha> <merge|rebase|squash> [github|external]
```

The transaction:

1. Creates the repository merge slot and acquires under stable identity
   `pr-shepherd:<repo>#<pr>@<head_sha>` without bypassing earlier waiters.
2. Re-reads PR state, exact head, `pr_base`, checks, and required approval.
3. Fetches and probes the live `pr_base`, not the final landing branch.
4. Calls `gh pr merge --match-head-commit <head_sha>` with the selected method.
   A head change between the read and merge is an atomic rejection.
5. Re-reads GitHub and persists `head_sha`, `merge_sha`, `pr_base`,
   `landing_base`, and `landing_state=merged` before final proof.
6. Proves the merge commit is on the live `landing_base`, or proves every path
   changed from `base_sha` to `head_sha` has exact Git tree content there.
7. Stamps `landing_state=proved`, comments the proof, releases the slot, and
   closes the merge bead only after release succeeds.

For a stacked PR, GitHub may report `MERGED` when only `pr_base` contains it.
The contract persists `landing_state=waiting_base`, returns 10, and leaves the
bead open. A later pass reuses the merge receipt and closes only when ancestry
or exact content proves that the change reached `landing_base`. Content proof
also handles a later squash that replaces the intermediate merge commit.

## Persisted queue and recovery

The contract creates one active deterministic generation for each stable
holder and labels it `gt:slot-waiter`. Metadata binds the slot id, holder,
generation, waiter id, and exact `BEADS_ACTOR`. An explicit `parent-child`
dependency links the waiter to the slot. If creation crashes before linking, a
restart adds and verifies the missing dependency. A wrong parent, duplicate
parent, malformed identity, or unlinked queue record fails closed.

Open and claimed valid records form the queue. Eligibility is the first record
by `created_at`, then id. The leased actor claims the record and rechecks
priority before calling atomic `bd merge-slot acquire`. The native holder token
binds the queue holder, generation, waiter id, and actor lease. A foreign actor
using the same queue holder is rejected before slot entry. The script never
calls `acquire --wait` and never rewrites a shared waiter collection.

Pending, stacked, queued, and exit-10 outcomes release the native slot while
keeping the same generation open and unassigned for its leased actor. Terminal
merged, cancelled, bounced, or dead work closes only that generation. A later
attempt for the same terminal holder must pass `requeue`, which creates the
next deterministic generation. A new head naturally has a new stable holder.

The explicit controls are:

```bash
scripts/landing-contract.sh acquire-slot <holder> [attempts] [seconds] [resume|requeue]
scripts/landing-contract.sh release-slot <holder> [terminal|retryable]
```

Do not delete a quiet receipt. After proving a session dead or a PR cancelled,
cite the evidence and use the matching recovery command:

```bash
scripts/landing-contract.sh recover-claim <merge-bead> <dead-actor> <evidence-ref> [waiter-holder]
scripts/landing-contract.sh recover-slot <merge-bead> <dead-holder> <evidence-ref>
scripts/landing-contract.sh recover-waiter <merge-bead> <dead-waiter> <evidence-ref>
```

Each command refuses unsafe changed ownership and records a comment plus audit
event. With `waiter-holder`, claim recovery releases only the dead generation's
native holder token, closes that generation, and lets one successor atomically
acquire a fresh generation. A delayed competitor cannot release the successor
token or replace its waiter and recovery receipt. Waiter recovery finds and
closes the current open generation and never mutates another queue entry.
If a process died after GitHub merged, rerunning `land` resumes from the remote
merge receipt and repeats final-base proof without another merge attempt.

Recovery itself is restartable. Before changing a claim, holder, or waiter, the
command stores a deterministic `recovery_key` and `recovery_phase=prepared`.
It advances through `mutated`, `commented`, `audited`, and `complete`. Stable
markers in Beads comments and the audit log let a retry finish a partially
written recovery without repeating the mutation, comment, or audit event.
