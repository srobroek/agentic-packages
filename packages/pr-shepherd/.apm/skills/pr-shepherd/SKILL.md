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
- Reviewing PR code quality → pr-reviewer agent
- Authoring or editing a PR → git-workflow steering; this skill discovers only
  ready, non-release PRs whose bodies carry Beads backlinks

## Workflow

1. Gate: `bd where` and `command -v gh` both succeed, else report which is
   missing and stop. Export `BEADS_ACTOR="pr-shepherd/<runtime>/<session-id>"`,
   `BD_NO_PAGER=1 BD_NON_INTERACTIVE=1`.
2. Load durable PR nodes with `bd list --label pr:merge --status all --json`.
   Each open node must remain unassigned, have repo+PR metadata, and its PR
   body must name that exact `Merge-Bead`. Ignore drafts for merge processing and ignore automated
   release PRs. Missing anchors or body/DAG mismatches are author-contract
   failures, not reasons to scan a bounded GitHub history.
3. Before creation/approval, authors add `bd dep add <work> <merge-bead>` for
   each `Closes-Bead`; one merge bead may block many work beads and one work
   bead may depend on many merge beads. `state:approved` freezes these edges;
   never mutate approved/closed work for a late closing trailer.
4. `bd gate check` evaluates CI gates. Never attach a gh:pr gate to the merge
   bead: that gate resolves only after the merge this bead must perform.
5. `bd merge-slot create` (idempotent) so the repo's slot exists.
6. Drain loop: `bd ready --label agent:integrator --unassigned --json`; probe
   eligibility before claiming with `scripts/merge-probe.sh eligibility`.
   Draft/release → ignore without mutation.
   Otherwise `bd update <id> --claim`; on "already claimed" skip it.
7. Probe from the bead's metadata anchors `{pr, branch, base_sha, repo}`
   after `git fetch`:
   - `scripts/merge-probe.sh pr <N>` → state, mergeable, reviewDecision,
     statusCheckRollup
   - `scripts/merge-probe.sh conflicts origin/<base> origin/<branch>` →
     predicted conflict paths (exit 1 = conflicts)
8. Decide (LOAD references/bounce-back.md before any bounce):

| probe result | action |
|---|---|
| draft | ignore: no claim, gate, bounce, merge, or bead closure |
| automated release PR | ignore by branch/label product anchors; title is not an anchor |
| already merged | verify terminal-branch landing, close merge bead, then reconcile ready closing work |
| closed without merge | set merge bead `state:failed`, status blocked, comment; dependent work remains blocked |
| clean + checks green + approved | `bd merge-slot acquire --holder <stable-id>` without `--wait` → `gh pr merge <N>` per repo convention → verify landing → holder-verified release → close merge bead |
| merge conflicts | bounce → agent:coder with the conflict file list |
| CI red | dedupe-check, then bounce → agent:coder with failing check names + `gh run view --log-failed` excerpt |
| changes requested | bounce → agent:coder with the review summary |
| not approved | comment once per observed state, release the claim, continue |
| checks pending | attach a gh:run gate only when a concrete run id exists; otherwise comment, release, continue |

9. After every claimed probe, `bd comments add <id>` the outcome: what was checked,
   what was found, disposition (merged / bounced / waiting-on-gate / skipped).
   The merge bead is the audit trail of every shepherd pass.
10. After closing a merge bead, query closing work through Beads dependencies,
   not manual PR counts. A work bead may close only when `bd ready` reports it,
   it has the exact `state:approved` label, children/gates are resolved, and
   every closing PR was verified on the repository default branch.
   `Tracks-Bead:` never closes.
11. Repeat step 6 until nothing is claimable, then report; `bd dolt push` per
   beads steering when beads changed.

## Rules

MUST Hold the merge slot across acquire → merge → release; release on every
  exit path, including a failed `gh pr merge`; use one stable holder and pass
  it to both acquire and release. Beads 1.1 waiters are advisory, not FIFO.
MUST Ignore draft and automated release PRs before claim or merge-slot
  acquisition. Release detection uses branch prefix or autorelease label,
  never title text.
MUST Never close a work bead from `Tracks-Bead:` alone; only a matching
  `Closes-Bead:` dependency graph plus native readiness, the exact
  `state:approved` label, and verified terminal landing authorizes closure.
NOT A gh:pr gate on a merge bead; use dependency edges for landing fan-in and
  a concrete gh:run gate only for CI.
MUST Release the claim (`bd update <id> --assignee "" --status open`) whenever
  the bead is not closed this pass — a parked claim starves other sessions.
MUST Never fix code, rebase, or resolve conflicts — file a fix bead and bounce
  (references/bounce-back.md); gates own the wait, not your session.
MUST Comment the pass outcome on the merge bead even when no action was taken.
DEFAULT Merge method: repo convention (branch protection, CONTRIBUTING);
  squash when unstated.
NOT Claiming a bead assigned to another actor — claim refusal IS the
  coordination; dead-claim recovery rules live in the pr-shepherd steering.
NOT Waiting in-session for CI or re-polling a pending PR — release and let the
  next pass (or `bd gate check`) pick it up.

OUTPUT
L1 SHEPHERD PASS: merged M / bounced B / waiting W / skipped S — then one line
   per bead: id, PR#, disposition, fix-bead id if filed.
CAP 150w clean · 300w with bounces
