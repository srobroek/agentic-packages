---
name: pr-shepherd
description: Drains the beads merge queue with exact-head landing proof and durable bounce recovery. Triggers on /pr-shepherd, shepherd PRs, drain merge queue, land ready PRs.
---

# PR Shepherd

Run a stateless pass over merge work stored in Beads. A fresh session can
resume every wait, remote merge, or bounce from durable state.

TRIGGER
+ /pr-shepherd, "shepherd the PRs", "drain the merge queue", "land ready PRs"
+ Stop-hook reminder reports ready merge beads or open GitHub gates
+ A `release-queue-watch` dispatch or PR lifecycle record targets merge work
- Reviewing PR code quality -> pr-reviewer agent
- Creating merge beads for a new PR -> the PR author, per steering

## Workflow

1. Confirm `bd where` and `command -v gh`. Export
   `BEADS_ACTOR="<runtime>/pr-shepherd/<session-id>"` using the active harness,
   plus `BD_NO_PAGER=1 BD_NON_INTERACTIVE=1`.
2. Event-driven invocation -> LOAD `references/queue-watcher.md`, resolve the
   record with `scripts/resolve-queue-event.py`, and target its exact merge bead
   first. Replay unacknowledged receipts before reading new records.
3. Run `bd gate check`, then `bd merge-slot create` (idempotent).
4. Claim the target first when present, then drain
   `scripts/landing-contract.sh ready-ids`. Claim each id with
   `bd update <id> --claim`; skip refusals. Never claim
   `integration_owner=orchestrate`.
5. Read the durable anchors: `repo`, `pr`, `pr_base`, `landing_base`,
   `base_sha`, and exact reviewed `head_sha`. Validate any `gh:run` gate with
   `scripts/landing-contract.sh check-run`; gate resolution alone is not proof.
6. Select approval mode. Use `github` by default. Use `external` only when an
   orchestrated adapter supplies a durable independent-approval receipt for
   this exact `head_sha`; explicit GitHub requested changes still fail.
7. Run `scripts/landing-contract.sh land <merge-bead> <repo> <pr> <pr-base>
   <landing-base> <base-sha> <head-sha> <merge|rebase|squash>
   [github|external]`. LOAD `references/landing-contract.md` for exit handling.
8. Decide (LOAD `references/bounce-back.md` before any bounce):

| Result | Action |
|---|---|
| `LANDING_COMPLETE` | Record merged disposition; the contract already proved the landing and closed the bead |
| exit 10, open/draft/pending | Ensure the appropriate GitHub gate, comment, release the claim |
| exit 10, `LANDING_HOLD` | The stacked PR merged into `pr_base`; leave the bead open until its exact content reaches `landing_base`, comment, release the claim |
| exit 11 | Comment stale head/base identity, keep the gate open, release the claim |
| CI red, conflict, requested changes | Create or reconcile a durable bounce receipt and routed fix bead |
| exit 2 or foreign slot | Comment observable uncertainty/contention, release the claim, report |
| closed without merge | Revalidate GitHub, comment cancellation, close the merge bead |

9. After every probe, comment the evidence and disposition. An event-driven
   pass stamps `shepherd_event_ack` only after that durable outcome.
10. Repeat until nothing is claimable; run `bd dolt push` per Beads steering
    when Beads changed, then report.

## Rules

MUST Use `landing-contract.sh` for merge-slot acquisition, GitHub merge, and
  landing proof. It carries `--match-head-commit` and releases on every exit.
MUST Respect durable per-holder waiter generations. Only the first open or
  claimed valid record by `created_at`, then id, may attempt atomic merge-slot
  acquisition, and its exact actor lease plus slot parent-child link must match.
MUST Release every merge-bead claim not closed this pass. A persisted stable
  waiter may survive retryable exit 10, pending, or stacked work. Keep that
  generation open for the same actor. Close it only for a terminal disposition;
  use explicit requeue for a later generation or evidence-gated recovery to
  replace a dead actor's generation.
MUST Keep `pr_base` separate from `landing_base`. A stacked GitHub `MERGED`
  state is a hold, not landing proof, until commit ancestry or exact content is
  visible on `landing_base`.
MUST Treat watcher records only as wake-ups; revalidate GitHub and acquire the
  merge slot before every merge.
MUST Route an orchestrator-owned PR to orchestrate, never both consumers.
MUST Never edit code, rebase, or resolve conflicts. Bounce with durable
  receipts; gates own async waits, not this session.
DEFAULT Merge method follows repository convention; squash when unstated.
NOT Re-polling pending CI or waiting in-session for approval.
DEFAULT Watcher failure triggers one explicit gate check plus a stateless pass;
  REST reconciliation and manual/cron passes remain recovery paths.

OUTPUT
L1 SHEPHERD PASS: merged M / bounced B / waiting W / skipped S - then one line
   per bead: id, PR#, disposition, fix-bead id if filed.
CAP 150w clean - 300w with bounces
