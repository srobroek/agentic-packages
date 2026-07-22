# PR Shepherd

MERGE BEADS
MUST Every PR meant to land gets an `agent:integrator` merge bead at PR
  creation. Metadata records `repo`, `pr`, `branch`, `pr_base`,
  `landing_base`, `base_sha`, exact reviewed `head_sha`, plus author
  `origin_actor`/`origin_bead`; a GitHub gate owns asynchronous waiting.

MUST `pr_base` is the PR's current target branch. `landing_base` is the branch
  on which final content must be proved, normally the default branch. They may
  differ for stacked PRs.

DEFAULT Generic merge beads are shepherd-owned. A live orchestrate PR carries
  `integration_owner=orchestrate`; pr-shepherd refuses all duplicates.

MUST A `gh:run` gate stores its exact `head_sha`. Successful gate resolution
  is advisory until `landing-contract.sh check-run` confirms the run head.

AUTHOR LIFECYCLE
MUST Authors push branch/PR, write residual context onto their own bead, close
  it, and exit. The gate plus shepherd own the wait; a later session resumes
  from durable Beads and GitHub evidence alone.

SHEPHERD PASS
DEFAULT `bd gate check` -> drain `landing-contract.sh ready-ids` -> atomically
  claim -> validate exact anchors -> call `landing-contract.sh land` -> close,
  hold, bounce, or re-gate and release. Comment every result.

MUST Standalone passes use approval mode `github`. An orchestrated adapter may
  use `external` only after a prior independent approval receipt names the
  exact `head_sha`; requested changes remain a failure in either mode.

WATCHER WAKE-UP
MUST Resolve read-only watcher records with `resolve-queue-event.py`; persist
  pending/sent/ack on the exact bead and revalidate GitHub before every outcome.

MUST Ack each record before reading the next; restart replays pending/sent.
  Claim refusal or crash stays unacknowledged and recoverable.

MUST Orchestrate resolves first; only unmatched records reach pr-shepherd.
  Never fan one record to both.

DEFAULT Watcher error/exit -> surface, run one gate-check/pass, restart or stop;
  never add polling beyond REST reconciliation and manual/cron passes.

EXACT LANDING
MUST The merge transaction re-reads PR state, exact head, PR base, review, and
  checks under the repository merge slot, probes the live PR base, and invokes
  `gh pr merge --match-head-commit <head_sha>`.

MUST Persist the GitHub merge receipt (`head_sha`, `merge_sha`, `pr_base`,
  `landing_base`) before final proof. Close only after the merge slot releases
  successfully and the exact merge commit is an ancestor of `landing_base`, or
  every path changed from `base_sha` to `head_sha` has exact Git tree content
  on its live tip.

MUST A stacked PR merged only into `pr_base` remains open with
  `landing_state=waiting_base`. A later pass re-proves its content on
  `landing_base`; GitHub `MERGED` by itself never closes the bead.

MERGE SLOT
MUST Use stable queue holder `pr-shepherd:<repo>#<pr>@<head_sha>`. Persist one
  active deterministic waiter generation per holder. Its metadata binds
  holder, generation, waiter id, and exact `BEADS_ACTOR`; an explicit
  `parent-child` dependency links it to the slot. Derive the native holder token
  from that generation, waiter id, and actor lease. Reconcile a missing link
  after a partial create, but fail closed on a wrong parent or malformed record.

MUST Only the first open or claimed valid record by `created_at`, then id, may
  claim and recheck priority before atomic slot acquisition. Pending, stacked,
  and exit-10 outcomes release the slot and leave the same generation open for
  its leased actor. Terminal merged, cancelled, bounced, or dead outcomes close
  it. Reusing a terminal holder requires explicit `requeue` and creates the next
  deterministic generation.

MUST Never bypass an earlier open waiter record or rewrite a shared waiter
  collection. A foreign actor with the same queue holder must be rejected
  before slot entry. Evidence-gated dead-claim recovery releases only the exact
  dead native token, closes its generation, and lets one successor create and
  acquire a new generation before recording the recovery receipt.

BOUNCE-BACK
MUST Compute a deterministic failure key and reconcile the oldest open routed
  fix bead before creating another. The fix is unassigned and labeled
  `agent:coder` or `agent:reviewer`.

MUST Persist `bounce_key`, canonical `bounce_fix`, and monotonic
  `bounce_phase` receipts (`preparing`, `fix_ready`, `parked`, `commented`,
  `complete`). On restart, reconcile the oldest canonical bead, close every
  extra duplicate, and restore dependency, marker-bearing comments, and the
  released claim from the last durable phase.

MUST The fix description carries exact diagnosis, reproduction, origin
  pointers, and whether the same failure exists on the landing base.

DEFAULT Warm-context routing is the orchestrator's optimization. The
  standalone contract ends after filing or reusing an unassigned fix bead.

DEAD CLAIMS
MUST Claim refusal means a live holder and is skipped. Force-release a claim,
  slot holder, or queued waiter only after session/audit evidence proves it is
  dead and ownership has not changed.

MUST Evidence-gated recovery stores `recovery_key` and advances `prepared` ->
  `mutated` -> `commented` -> `audited` -> `complete`. Stable comment and audit
  markers make every crash point resumable without repeating the mutation.
