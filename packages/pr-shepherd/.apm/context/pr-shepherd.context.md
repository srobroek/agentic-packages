# PR Shepherd

MERGE BEADS
MUST Before `gh pr create`, create one open, unassigned merge bead labeled
  `pr:merge` + `agent:integrator`; store `branch`, `repo`, `origin_actor`,
  metadata; stamp pr/base/head after creation. Dedupe on repo+PR.
MUST For every work bead the PR completes, add `bd dep add <work> <merge-bead>`.
  One work bead may depend on many merge beads; one merge bead may block many.
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

REVIEW BOTS
MUST Treat a configured review bot (`$PR_REVIEW_BOTS`, default `coderabbitai`)
  as part of merge readiness: probe `merge-probe.sh bot-review` at the exact head
  before every merge. Only `absent` or `clean` clears; `pending`, `stale`, and
  unknown are waits. Silence is not approval.
MUST Treat `declined` (13) as a re-trigger rather than a wait: the bot refused
  the round under its quota, so no further round arrives unprompted. Act on the
  probe's `wait=` reopen instant. `wait=UNKNOWN` means re-check the PR before
  re-triggering, because a wrong "window reopened" burns quota for no review.
MUST Read actionability from the bot's own summary review body through its
  adapter (CodeRabbit: `Actionable comments posted: N`) at the current head,
  taking the LATEST round rather than the highest count -- every fix suggestion
  hangs under that summary, and a max keeps a resolved round blocking forever.
DEFAULT A new bot is a slug in `$PR_REVIEW_BOTS` plus an optional `ADAPTERS`
  entry in `bot-review-probe.py`; without an adapter its count is unknown, so a
  COMMENTED round reads `pending` instead of clearing.
MUST Park an actionable round behind one unassigned `agent:coder` fix bead keyed
  `review bot:<slug>@<head>`, exactly like CI-red. A durable bead, not a wisp:
  the blocking dependency edge dies with a burned wisp.
MUST Carry pointers -- summary URL, comment `path:line` + URL, `bot_review_head`
  -- never a copy of the findings. The bot thread is live and its diff
  suggestions render only on the PR.
NOT Shepherd judgement on which findings are right; the claiming coder decides
  what is correct and appropriate and replies on the PR to what it rejects.
NOT Polling a bot round in-session; comment once per state@head, release, and
  let the gate plus the next pass own the wait.

ELIGIBILITY
MUST Ignore while `isDraft=true`: do not claim, gate, bounce, merge, or close.
MUST Ignore automated release PRs (head branch `release-please--branches--` or
  label `autorelease: pending`). Merged release PRs remain excluded.
MUST Closed-unmerged PR marks its merge bead blocked/failed; dependent work
  beads stay blocked; never close as successful.
MUST Prove a merge bead's pr/repo/branch anchors against the live PR with
  `landing-contract.py check-anchors` before merging; the PR body is not
  evidence. Closing a verified PR closes its merge bead; native dependency
  readiness performs fan-in.
MUST Close a dependent work item only when: `bd ready` reports it, it has
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
