# Beads store: run state, mapping, audit, coordination

A run's DAG, node state, and audit trail live in the project's beads database
(the `bd` CLI). One database is shared by every worktree automatically, so
agents in isolated worktrees read/write live state with plain `bd` commands —
no shared-path bookkeeping. Artifacts (full briefs/reports) are files under
`<primary>/.orchestration/run-<id>/artifacts/`; bead comments reference them
by absolute path.

## Coordination and policy carriers

| Carrier | Stores | Authority and lifecycle |
|---|---|---|
| Work-bead comment | A choice that affects only that bead and its owned scope | Durable local source of truth. The comment author is the actor. Accepted comments remain; provisional comments name an objective revisit trigger. |
| `decision` bead | A choice that affects more than one bead, agent, or package, or constrains later work | Durable cross-boundary source of truth. It carries an owner, stable key, design, acceptance/verification, status/disposition, and non-blocking links to every affected bead. |
| Message wisp | A question, reply, notification, acknowledgement, or other live coordination | Ephemeral coordination only. A material outcome is promoted to a comment or decision bead before action or closure. Acknowledgement or compaction never deletes the promoted source of truth. |
| Artifact / `output_ref` | A large brief, report, test log, or other inspectable evidence payload | Evidence only. It becomes part of a decision or report when a comment or decision bead cites its absolute path. The file alone is not policy or lifecycle state. |

A material message changes a choice, default, scope, route, ordering,
acceptance evidence, disposition, or human answer. Handle it in this order:

1. Classify its effect as bead-local or cross-boundary.
2. Write the local comment or decision bead and any affected-bead links.
3. Read the durable record back. A decision is effective only after every
   affected link is visible and non-blocking.
4. Act from that record and cite it in later comments or reports.
5. Acknowledge or compact the message only after promotion succeeds.

No promotion means no policy action and no closure based on that message.
Restart recovery reads comments and decision beads before message wisps or
artifacts.

## Local decision comments

Set `BEADS_ACTOR` to the choosing actor. Add the following record to the work
bead, then read it back with `bd comments <bead> --json` before acting:

```text
LOCAL_DECISION
owner: <actor>
scope: <work-bead and owned resource>
decision: <chosen implementation behavior>
rationale: <why this choice fits the brief>
evidence: <file:line, bead id, command result, or searched-none>
status: <accepted|provisional>
revisit: <objective trigger; required when provisional>
```

The comment author and `owner` must match. `accepted` omits `revisit`.
`provisional` requires a nonempty event, dependency transition, exact evidence
change, or RFC3339 deadline. `later`, `if needed`, and elapsed time without an
observable condition are not triggers. Record the operation as `orc.note` in
the audit trail.

A readable comment is the local source of truth. If the audit write fails
after the comment succeeds, retry the audit before closing; do not duplicate
the comment. If the comment write or read-back fails, do not apply the choice.

## Cross-boundary decision beads

Create a first-class decision under the run epic before the choice affects a
second bead, agent, package, shared contract, ordering rule, or later work:

```text
type: decision
decision_key: <stable run-unique policy key>
decision_owner: <one accountable actor>
description: <choice and affected scope>
design: <rationale, known evidence, unknowns, bounds, and alternatives>
acceptance: <objective verification or acceptance evidence>
decision_disposition: <proposed|accepted|rejected|superseded|duplicate|conflict>
status: <open|in_progress|closed>
```

Use `relates-to` for affected work and `validates` for work that supplies or
checks acceptance evidence:

```text
bd dep add <affected-bead> <decision-bead> --type relates-to
bd dep add <validator-bead> <decision-bead> --type validates
```

Both edge types are non-blocking. Never use `blocks` for accepted policy or to
attach an already-running/closed affected bead. Ordering work still uses a
separate task dependency. An accepted, rejected, duplicate, or superseded
decision is closed with a disposition-specific reason; closed means resolved,
not erased.

Before creation, after restart, and before action, list every decision under the
epic with `bd list --type decision --parent <epic> --all --json`. Decisions
compete only when their nonempty `decision_key` values match.

Resolve each competing key deterministically:

1. Read every candidate and its `supersedes` edges. Reject an edge that crosses
   a `decision_key`, targets a missing bead, or creates a cycle.
2. When accepted candidates contain a valid explicit `supersedes` chain,
   canonical is the newest accepted unsuperseded head by `created_at`, then
   bead ID. Every older candidate in that key becomes `superseded`.
3. When no explicit supersession exists, canonical is the earliest candidate
   by `created_at`, then bead ID. Every other candidate becomes `duplicate`.
4. Read canonical again. Its `decision_disposition` must be `accepted`. Never
   update canonical while marking noncanonical beads.

Persist every noncanonical disposition as a resumable transaction. Read before
each command and skip a step whose exact result already exists:

```text
# Mark the noncanonical bead first.
bd update <noncanonical> \
  --set-metadata decision_disposition=<duplicate|superseded> \
  --set-metadata canonical_decision=<canonical>

# Duplicate: loser points to canonical without blocking it.
bd dep add <loser> <canonical> --type relates-to
bd close <loser> --reason "duplicate of <canonical>"

# Superseded: canonical explicitly supersedes the older decision.
bd dep add <canonical> <older> --type supersedes
bd close <older> --reason "superseded by <canonical>"
```

After every write, read both beads back. A noncanonical bead is resolved only
when its metadata, required edge, closed status, and close reason all match,
and canonical still has `decision_disposition=accepted`. If metadata, edge, or
close writes stop partway, record the failure and leave the observed partial
state. Restart repeats the same keyed reads, completes only missing steps, and
produces the same result without changing canonical.

`bd close` does not replace the close reason of an already-closed bead. When a
loser is closed with any reason other than the canonical duplicate or
superseded reason, repair it only after the loser metadata and required edge
have passed read-back:

```text
bd label add <loser> decision-repair
bd label add <loser> non-work
bd reopen <loser> --reason "repair stale decision close reason"
bd close <loser> --reason "<duplicate of|superseded by> <canonical>"
```

- Add both labels before reopening. Generic ready and claim selectors exclude
  `non-work`.
- Read back both labels and confirm canonical is still accepted. Run reopen and
  close consecutively.
- A restart between those commands recognizes `decision-repair` plus
  `non-work`, verifies the durable loser metadata and edge, skips reopen, and
  closes the loser with the canonical reason.
- Success requires a final read of both beads showing `status=closed`, the
  canonical close reason, the expected loser disposition and
  `canonical_decision`, and unchanged canonical metadata.

An invalid explicit chain remains `decision_disposition=conflict`; no candidate
is applied until the owner repairs the chain from evidence or enters
`waiting_human`. Never infer resolution from a message or artifact.

## Prerequisite (checked once, at run start)

```
command -v bd >/dev/null || { echo "orchestrate requires the beads CLI (bd)"; }
bd info >/dev/null 2>&1 || bd init --stealth --prefix orc
```

- No `bd` on PATH → stop and tell the user to install beads. There is no
  fallback store.
- `bd` present, no database → `bd init --stealth --prefix orc` (git-invisible:
  writes `.git/info/exclude`, leaves `git status` clean).

## Run and node beads

| Object | Beads representation |
|---|---|
| Run | one **epic** bead; metadata `run_id`, `primary_branch`, `base_sha`, `artifacts` (abs dir), optional `swarm` handle |
| DAG node | **task** bead, `--parent <epic>`, label `orc-node`, metadata `node` (short id), `scope` (JSON array of globs) |
| Node dep | `bd dep add <dependent> <dependency>` (`blocks` type), one per edge |
| Git anchors | node metadata, stamped per the contract below |

```
EPIC=$(bd create "orchestrate run-<id>" --type epic --silent \
  --metadata '{"run_id":"run-<id>","primary_branch":"main","base_sha":"<sha>","artifacts":"<abs>/.orchestration/run-<id>/artifacts"}')
# For multi-node runs, persist the returned handle from `bd swarm create "$EPIC"`
# as metadata key `swarm`; later status/validation reads that handle.
T1=$(bd create "t1: <desc>" --parent "$EPIC" --labels orc-node --silent \
  --metadata '{"node":"t1","scope":["src/auth/**"]}')
bd dep add "$T3" "$T1"        # t3 depends on t1
bd dep cycles                 # must stay clean
```

The label MUST be `orc-node` (hyphen, plain label). `bd set-state` owns the
`state:` label dimension: each transition deletes the previous `state:<value>`
label, adds the new one, and emits an event bead — the transition record.

## State mapping — 11-state enum → bead status + `state:` label

Beads statuses are coarse and drive `bd ready`; the `state:` label carries the
review-round sub-state. Both are set in one place per transition:

```
bd set-state <bead> state=<name> --reason "<why>"     # label + event bead
bd update <bead> --status <status>                    # only where status changes
```

| Enum state | Bead status | `state:` label | Set by / how |
|---|---|---|---|
| `pending` | `open` | `state:pending` | orchestrator at `bd create` |
| `ready` | `open` | — (derived, never stored) | `bd ready --label orc-node --parent <epic>` + clean `scope-check.py` |
| `working` | `in_progress` | `state:working` | coder: `bd update <bead> --claim` (atomic, first-wins, sets assignee) then `set-state` |
| `reported` | `in_progress` | `state:reported` | coder, after push |
| `in_review` | `in_progress` | `state:in_review` | orchestrator at reviewer spawn |
| `changes_requested` | `in_progress` | `state:changes_requested` | orchestrator on `REVIEW verdict=changes` |
| `approved` | `in_progress` | `state:approved` | orchestrator on `REVIEW verdict=approve` |
| `merged` | `closed` | `state:merged` | gatekeeper: `set-state` then `bd close <bead> --reason merged` |
| `dismissed` | `closed` | `state:dismissed` | orchestrator: `set-state` then `bd close <bead> --reason dismissed` |
| `failed` | `blocked` | `state:failed` | orchestrator: `set-state` then `bd update <bead> --status blocked` |
| `waiting_human` | `in_progress` | `state:waiting_human` | orchestrator on `ASK`; add `bd gate create --type=human --blocks <bead>` when the node has not started yet |

Semantics that fall out of the status column:

- **Deps clear on `closed`.** A dependent becomes ready only once its
  upstreams are `merged`/`dismissed` — it always starts from a base containing
  the upstream's merged code.
- **`failed` = `blocked` status** → never satisfies a dependency, never
  reappears in `bd ready`. Stranded downstream = `bd dep tree <bead>`.
- **`bd ready` excludes** `in_progress`, `blocked`, `deferred`, and gated
  beads, so the ready front is dep-correct by construction.

## Git-anchor metadata contract

Every node bead carries git anchors in metadata so any session can find where
the work physically lives. Two stamping points, no exceptions:

| When | Who | Stamp |
|---|---|---|
| Claim (immediately after `--claim`) | coder | `bd update <bead> --metadata '{"branch":"<branch>","worktree":"<abs path>","base_sha":"<sha>"}'` |
| Report (after push) | coder | `--set-metadata pushed=origin/<branch>` (+ refresh `branch` if renamed) |
| Merge | gatekeeper | `bd update <bead> --metadata '{"pr":<n>,"merge_sha":"<sha>"}'` |

Add a `repo` key when the node's work lands in a different repository than the
run epic's. `--metadata` merges with existing keys (verified on bd 1.1.0), so
stamps never clobber `node`/`scope`. `worktree` is an ephemeral pointer, valid
while the node is in flight; `branch`/`pushed`/`pr`/`merge_sha` are the durable
anchors that survive worktree teardown.

## Ready front + scope disjointness

Beads does not know about file scopes. Ready therefore has two steps:

```
bd ready --label orc-node --parent "$EPIC" --json     # dep-cleared front
scope-check.py --candidate <bead-id> --epic "$EPIC"   # exit 0 disjoint, 1 conflict
```

`scope-check.py` (bundled, stdlib-only) reads the candidate's `scope` and
every `in_progress` node bead's `scope` via `bd list --json`, and applies a
conservative glob-overlap rule (prefix containment either direction; bare `**`
conflicts with everything). Run it **before** `bd update --claim`; a conflict
means: leave the node unclaimed, pick another.

## Events: audit records + comments

Every protocol verb (`assign blocked advice reported review fix conflict
approve merged dismiss ask` + `failed`/`note`) is recorded by the acting agent
(identity via `BEADS_ACTOR=<actor>`) as two writes:

```
bd audit record --actor <actor> --kind tool_call --tool-name orc.<verb> \
  --issue-id <bead> --exit-code 0                    # append-only .beads/interactions.jsonl
bd comment <bead> "<VERB> <node> field=… output_ref=<abs artifact path>"
```

- **Audit record** = machine-parsable, append-only trail; `--tool-name
  orc.<verb>` carries the verb; `--exit-code 1` + `--error` for failures.
- **Comment** = human-readable payload (the message fields), citing artifact
  paths instead of inlining long text.
- **Artifacts**: full briefs/reports go to
  `<artifacts>/<node>-<verb>-<n>.md`; the comment carries the absolute path.
- State-carrying verbs additionally flip status/label per the mapping table;
  `bd set-state` emits its own event bead, so transitions are double-anchored.

## Gatekeeper primitives

- **Mutual exclusion:** `bd merge-slot create` once per run (idempotent), with
  a stable holder such as `run-<id>-gatekeeper`. Acquire without `--wait`;
  contention is advisory, so report the current holder and retry after release.
  Always release on success, conflict, CI wait, and failure. On restart,
  `bd merge-slot check` and verify remote state before releasing a slot held by
  the same stable actor.
- **Async waits:** `bd gate create --type=gh:pr --blocks <bead> --await-id <pr#>`
  (PR merge) or `--type=gh:run --await-id <run-id>` (CI); `bd gate check`
  evaluates and closes resolved gates. A gated bead stays out of `bd ready`.
- `conflict-probe.sh` is the merge-safety probe primitive (`conflicts`,
  `pairwise`, `ci`).

## Reading the run (scribe / resume / close-out)

| Question | Command |
|---|---|
| run status | `bd list --label orc-node --parent <epic> --all --json` (status + `state:` label + metadata) |
| one node's story | `bd show <bead> --json` + `bd comments <bead>` |
| audit trail | filter `.beads/interactions.jsonl` by `issue_id`/`actor` (append-only JSONL; jq or stdlib) |
| dep structure / impact | `bd dep tree <bead>`, `bd graph` |
| open waits | `bd gate list`, `bd merge-slot check` |
| resume after crash | in-flight = `bd list --label orc-node --parent <epic> --status in_progress --json`; agent handle = bead `assignee`, location = metadata `worktree`/`branch` |
| close-out gate | `bd dep cycles` clean AND `bd list --label orc-node --parent <epic> --status in_progress,blocked --json` empty (blocked = surfaced `failed` nodes) |

## SpecKit / external frameworks

A beads-managed SpecKit molecule (`bd swarm create <epic>`, `bd ready --mol`)
already IS a dependency-aware run DAG. When such a molecule drives the work,
use its step beads as the run's node beads — do not build a second graph on
top. Add the `orc-node` label + `scope` metadata to the step beads so
`scope-check.py`, the state mapping, and the anchor contract apply unchanged.
