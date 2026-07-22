---
name: pr-shepherd
description: Drains the beads merge queue — checks gates, probes PRs, merges or bounces back. Triggers on /pr-shepherd, shepherd PRs, drain merge queue, land ready PRs.
---

# PR Shepherd

Stateless cross-session pass over merge work stored in beads. Safe to run from
any session, a /loop, or cron; a killed run leaves only claims the next pass
skips or recovers per steering.

TRIGGER
+ /pr-shepherd, "shepherd the PRs", "drain the merge queue", "land ready PRs"
+ Stop-hook reminder reports ready merge beads or open GitHub gates
+ A `release-queue-watch` dispatch or PR lifecycle record targets merge work
- Reviewing PR code quality → pr-reviewer agent
- Creating merge beads for a new PR → the PR author, per pr-shepherd steering

## Workflow

1. Gate: `bd where` and `command -v gh` both succeed, else report which is
   missing and stop. Export
   `BEADS_ACTOR="<runtime>/pr-shepherd/<session-id>"` using the active harness
   name (`codex` or `claude`), plus `BD_NO_PAGER=1 BD_NON_INTERACTIVE=1`.
2. Event-driven invocation → LOAD `references/queue-watcher.md`, resolve the
   record with `scripts/resolve-queue-event.py`, and target its exact merge bead
   first. On start/restart, replay unacknowledged receipts before new records.
   Manual, cron, and fallback invocations skip this targeting step.
3. `bd gate check` — evaluates gh:pr/gh:run gates via gh, closes satisfied
   ones, unblocks their dependents.
4. `bd merge-slot create` (idempotent) so the repo's slot exists.
5. Claim the targeted bead first when present, then drain
   `bd ready --label agent:integrator --unassigned --json`; for
   each bead `bd update <id> --claim`; on "already claimed" skip it.
6. Probe from the bead's metadata anchors `{pr, branch, base_sha, repo}`
   after `git fetch`:
   - `scripts/merge-probe.sh pr <N>` → state, mergeable, reviewDecision,
     statusCheckRollup
   - `scripts/merge-probe.sh conflicts origin/<base> origin/<branch>` →
     predicted conflict paths (exit 1 = conflicts)
7. Decide (LOAD references/bounce-back.md before any bounce):

| probe result | action |
|---|---|
| clean + checks green + approved | `bd merge-slot acquire` (`--wait` if held) → `gh pr merge <N>` per repo convention → `bd merge-slot release` → `bd close <id> --reason "PR #N merged <sha>"` |
| merge conflicts | bounce → agent:coder with the conflict file list |
| CI red | dedupe-check, then bounce → agent:coder with failing check names + `gh run view --log-failed` excerpt |
| changes requested | bounce → agent:coder with the review summary |
| not approved / draft / checks pending | verify a gh:pr gate blocks the bead (`bd gate create --type=gh:pr --await-id=<N> --blocks <id>` if missing), release the claim, continue |
| already merged | revalidate GitHub → close the merge bead with the merge SHA |
| closed without merge | revalidate GitHub → close the merge bead as cancelled |

8. After EVERY probe, `bd comments add <id>` the outcome: what was checked,
   what was found, disposition (merged / bounced / waiting-on-gate / skipped).
   The merge bead is the audit trail of every shepherd pass. An event-driven
   pass stamps `shepherd_event_ack` only after this durable outcome.
9. Repeat step 5 until nothing is claimable, then report; `bd dolt push` per
   beads steering when beads changed.

## Rules

MUST Hold the merge slot across acquire → merge → release; release on every
  exit path, including a failed `gh pr merge`.
MUST Release the claim (`bd update <id> --assignee "" --status open`) whenever
  the bead is not closed this pass — a parked claim starves other sessions.
MUST Never fix code, rebase, or resolve conflicts — file a fix bead and bounce
  (references/bounce-back.md); gates own the wait, not your session.
MUST Comment the pass outcome on the merge bead even when no action was taken.
MUST Treat watcher records only as wake-ups; revalidate GitHub and acquire
  `bd merge-slot` before every merge.
MUST Route an orchestrator-owned PR to orchestrate, never both consumers.
DEFAULT Merge method: repo convention (branch protection, CONTRIBUTING);
  squash when unstated.
NOT Claiming a bead assigned to another actor — claim refusal IS the
  coordination; dead-claim recovery rules live in the pr-shepherd steering.
NOT Waiting in-session for CI or re-polling a pending PR — release and let the
  next pass (or `bd gate check`) pick it up.
DEFAULT A watcher failure triggers one explicit `bd gate check` plus stateless
  pass; REST reconciliation and manual/cron passes are the recovery paths.

OUTPUT
L1 SHEPHERD PASS: merged M / bounced B / waiting W / skipped S — then one line
   per bead: id, PR#, disposition, fix-bead id if filed.
CAP 150w clean · 300w with bounces
