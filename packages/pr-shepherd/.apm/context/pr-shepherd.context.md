# PR Shepherd

MERGE BEADS
MUST Before `gh pr create`, create exactly one open, unassigned merge task
  labeled `pr:merge` and `agent:integrator`; store `branch`, `repo`, `origin_actor`,
  `tracks_beads`, and `closes_beads` metadata, then stamp pr/base/head
  immediately after creation.
  The PR body carries the exact `Merge-Bead` id; dedupe on repo+PR.
MUST For every `Closes-Bead: <work>` add `bd dep add <work> <merge-bead>`.
  One work bead may depend on many PR merge beads; one merge bead may block
  many work beads. `Tracks-Bead` adds no blocking edge.
NOT A gh:pr gate blocking a merge bead — it resolves only after merge and
  deadlocks the integrator queue. A gh:run gate may block merge work for CI.
DEFAULT Use `bd graph` to inspect fan-in/fan-out, `bd ready` to decide when
  all merge dependencies are satisfied, and `bd swarm validate <epic>` for
  structural validation of an orchestrated graph.
MUST `state:approved` freezes closing edges. A new `Closes-Bead` must already
  have its dependency before approval; never add a late edge to approved or
  closed work automatically — record the mismatch for human resolution.

AUTHOR LIFECYCLE
MUST Authors create PRs with `gh pr create --draft`; promote with `gh pr
  ready` only after implementation, local validation, and required agent
  review complete with no known blocker.
MUST In a Beads repository, append a `## Beads` body section with repeatable
  `Tracks-Bead: <id>` lines, one `Merge-Bead: <id>`, and `Closes-Bead: <id>`
  only for dependency edges already present in the Beads DAG.
MUST Authors push branch/PR, write residual context onto their own bead per
  the beads steering (comments: approach, tricky spots, what to check first
  if CI fails), set it to reported/approved, release their claim, and exit.
  Do not close work that still depends on an unmerged PR and never stay alive
  waiting for CI or merge — the merge bead plus shepherd own the wait.

SHEPHERD PASS (stateless — any session, /loop, or cron)
DEFAULT `bd gate check` → drain `bd ready --label agent:integrator
  --unassigned --json` → per bead: probe PR eligibility before claiming;
  ignore drafts and automated release PRs, otherwise claim with `bd update
  <id> --claim`, probe merge-tree conflicts/checks/review, then merge, bounce,
  or re-gate + release; comment every claimed probe outcome on the merge bead.

ELIGIBILITY
MUST Ignore a PR while `isDraft=true`: do not claim, gate, bounce, merge, or
  close its merge/work beads.
MUST Ignore automated release PRs when either the head branch starts
  `release-please--branches--` or label `autorelease: pending` is present.
  Do not infer release ownership from title text alone.
MUST A merged release PR remains excluded; release classification precedes
  open/merged lifecycle classification.
MUST A closed-unmerged PR marks its merge bead blocked/failed and leaves every
  dependent work bead blocked; never close it as successful landing.
MUST Treat `Tracks-Bead` as a backlink only. Closing a verified PR closes its
  merge bead; native dependency readiness performs the many-PR fan-in.
MUST Close a `Closes-Bead` work item only when `bd ready` reports it after all
  merge beads close, it has the exact `state:approved` label, its
  children/gates are resolved, and every closing PR targets the repository
  default branch with its merge commit proven there. A stacked merge is not
  final delivery.

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
  without `--wait` before `gh pr merge`, `release --holder <same-id>` on every
  exit path — the slot serializes merging across concurrent shepherd sessions.
  A held slot ends this pass for that PR; Beads 1.1 waiters are advisory, not
  a FIFO queue.

DEAD CLAIMS
MUST Claim refusal means a live holder — skip the bead. Force-release
  (`bd update <id> --assignee "" --status open`) only after confirming the
  holder session is dead: its session-id actor shows no bead activity since
  before your session started and no live session matches it.
