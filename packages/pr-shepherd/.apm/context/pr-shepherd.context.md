# PR Shepherd

MERGE BEADS
MUST Before `gh pr create`, create one open, unassigned merge bead labeled
  `pr:merge` + `agent:integrator`; store `branch`, `repo`, `origin_actor`,
  `tracks_beads`, `closes_beads` metadata; stamp pr/base/head after creation.
  PR body carries the exact `Merge-Bead` id; dedupe on repo+PR.
MUST For every `Closes-Bead: <work>` add `bd dep add <work> <merge-bead>`.
  One work bead may depend on many merge beads; one merge bead may block many.
  `Tracks-Bead` adds no blocking edge.
NOT A gh:pr gate blocking a merge bead -- deadlocks integrator queue.
  A gh:run gate may block merge work for CI.
DEFAULT `bd graph` for fan-in/fan-out; `bd ready` for dependency satisfaction;
  `bd swarm validate <epic>` for structural validation.
MUST `state:approved` freezes closing edges -- never add a late edge to approved
  or closed work automatically; record the mismatch for human resolution.

AUTHOR LIFECYCLE
MUST PR authorship rules (draft creation, promotion criteria, Beads body
  section format) follow git-workflow steering (GW section "Shipping" and
  "Beads linkage").
MUST Authors push branch/PR, write residual context onto their bead per beads
  SESSION CLOSE, set to reported/approved, release claim, and exit. Never stay
  alive waiting for CI or merge -- the merge bead plus shepherd own the wait.

SHEPHERD PASS (stateless -- any session, /loop, or cron)
MUST Skip a bead whose `metadata.integration_owner` names another actor
  (`orchestrate`) while that run is live; its own shepherd is mid-flight. Take it
  only once the run is terminal -- that recovery is this actor's job, stealing an
  active merge is not. The drain query filters by label alone, so this check is
  what separates the two actors.
DEFAULT `bd gate check` then drain `bd ready --label agent:integrator
  --unassigned --json`; per bead: probe PR eligibility before claiming;
  ignore drafts and automated release PRs, otherwise claim, probe
  merge-tree/checks/review, then merge, bounce, or re-gate + release;
  comment every probe outcome on the merge bead.

ELIGIBILITY
MUST Ignore while `isDraft=true`: do not claim, gate, bounce, merge, or close.
MUST Ignore automated release PRs (head branch `release-please--branches--` or
  label `autorelease: pending`). Merged release PRs remain excluded.
MUST Closed-unmerged PR marks its merge bead blocked/failed; dependent work
  beads stay blocked; never close as successful.
MUST `Tracks-Bead` is a backlink only. Closing a verified PR closes its merge
  bead; native dependency readiness performs fan-in.
MUST Close a `Closes-Bead` work item only when: `bd ready` reports it, it has
  `state:approved`, children/gates resolved, and every closing PR targets the
  default branch with its merge commit proven there.

BOUNCE-BACK (problem the shepherd cannot fix)
MUST Dedupe first: open fix bead with same failure key → `bd dep add` +
  correlation comments, no duplicate.
MUST Otherwise file `bd create --discovered-from:<merge-bead>`, label
  `agent:coder`, ALWAYS unassigned; metadata carries pr/branch/failure/check +
  origin_actor/origin_bead; description carries the exact error, reproduction
  command, and "read <origin_bead>'s comments first". Note pre-existing base
  failures when detected.
MUST Park: `bd dep add <merge-bead> <fix-bead>`, comment merge bead, release
  claim (`--assignee "" --status open`). Coder closing fix re-readies merge.
DEFAULT Warm-context routing: a live orchestrator may claim the fix bead for
  its origin worker; the shepherd's contract ends at filing unassigned.
DEFAULT Non-blocking observations (flaky-but-passed, warnings) become
  `related`-linked beads or comments, not blocking deps.

PICKUP
DEFAULT Workers poll `bd ready --assignee <me> --json` first, then
  `bd ready --label agent:<kind> --unassigned --json`.

MERGE SLOT
MUST One `bd merge-slot create` per repo (idempotent); `acquire` without
  `--wait` before `gh pr merge`; `release --holder <same-id>` on every exit
  path. A held slot ends this pass for that PR.

DEAD CLAIMS
MUST Treat a claim refusal as a live holder and skip that PR this pass.
  Dead-claim recovery is the `beads` steering's rule; follow it there instead of
  a local restatement.
