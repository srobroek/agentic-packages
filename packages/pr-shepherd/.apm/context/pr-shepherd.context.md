# PR Shepherd

MERGE BEADS
MUST Every PR meant to land gets a merge bead at PR creation: labeled
  `agent:integrator`, metadata `{"pr":N,"branch":"...","base_sha":"...",
  "repo":"owner/name"}` plus author `origin_actor`/`origin_bead`, and a gh:pr gate:
  `bd gate create --type=gh:pr --await-id=<N> --blocks <merge-bead>`.
DEFAULT Generic merge beads are shepherd-owned. A live orchestrate PR carries
  `integration_owner=orchestrate`; pr-shepherd refuses all duplicates.
MUST Async waits are gate beads (gh:pr, gh:run) evaluated by `bd gate check`;
  labels, claims, and field taxonomy follow the beads steering — never
  ci:green/pr:merged labels.

AUTHOR LIFECYCLE
MUST Authors push branch/PR, write residual context onto their own bead per
  the beads steering (comments: approach, tricky spots, what to check first
  if CI fails), close it, and exit. The gate plus shepherd own the wait; any
  later session resumes from beads alone.

SHEPHERD PASS (stateless — any session, /loop, or cron)
DEFAULT `bd gate check` → drain `bd ready --label agent:integrator
  --unassigned --json` → per bead: `bd update <id> --claim`, probe (merge-tree
  conflicts, `gh pr view` state/checks/review), then merge, bounce, or
  re-gate + release; comment every probe outcome on the merge bead.

WATCHER WAKE-UP
MUST Resolve read-only watcher records with `resolve-queue-event.py`; persist
  pending/sent/ack on the exact bead and revalidate GitHub before every outcome.
MUST Ack each record before reading the next; restart replays pending/sent.
  Claim refusal or crash stays unacknowledged and recoverable.
MUST Orchestrate resolves first; only unmatched records reach pr-shepherd.
  Never fan one record to both.
DEFAULT Watcher error/exit → surface, run one gate-check/pass, restart or stop; never add polling beyond REST reconciliation and manual/cron passes.

BOUNCE-BACK (problem the shepherd cannot fix)
MUST Dedupe first: an open fix bead with the same failure key (check+repo or
  conflict file set) → `bd dep add <merge-bead> <existing-fix-bead>` +
  correlation comments on both, no duplicate.
MUST Otherwise file `bd create` with `discovered-from:<merge-bead>`, label
  `agent:coder` (or `agent:reviewer`), ALWAYS unassigned; metadata carries
  pr/branch/failure/check + origin_actor/origin_bead; description carries the
  exact error, a reproduction command, "read <origin_bead>'s comments first",
  and — when the same check is red on the base branch — "failure appears
  pre-existing on <base>, not introduced by this branch".
MUST Park and release: `bd dep add <merge-bead> <fix-bead>`, comment the merge
  bead, `bd update <merge-bead> --assignee "" --status open`. The coder
  closing the fix bead re-readies the merge bead — no messaging.
DEFAULT Warm-context routing is the orchestrator's optimization: a live
  orchestrator may claim the fix bead for its origin worker and route it via
  its own channel; the shepherd's contract ends at filing unassigned.
DEFAULT Non-blocking observations (flaky-but-passed test, warnings) become
  `related`-linked beads or comments, never blocking deps.

PICKUP
DEFAULT Workers poll `bd ready --assignee <me> --json` first (orchestrator may
  have pinned work), then `bd ready --label agent:<kind> --unassigned --json`;
  bd prime injection and catchup surface ready work — no messaging needed.

MERGE SLOT
MUST One `bd merge-slot create` per repo (idempotent); `bd merge-slot acquire`
  (`--wait` when held) before `gh pr merge`, `release` on every exit path —
  the slot serializes merging across concurrent shepherd sessions.

DEAD CLAIMS
MUST Claim refusal means a live holder — skip the bead. Force-release
  (`bd update <id> --assignee "" --status open`) only after confirming the
  holder session is dead: its session-id actor shows no bead activity since
  before your session started and no live session matches it.
