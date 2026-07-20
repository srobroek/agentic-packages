# Beads store: run state, mapping, audit, coordination

A run's DAG, node state, and audit trail live in the project's beads database
(the `bd` CLI). One database is shared by every worktree automatically, so
agents in isolated worktrees read/write live state with plain `bd` commands —
no shared-path bookkeeping. Artifacts (full briefs/reports) are files under
`<primary>/.orchestration/run-<id>/artifacts/`; bead comments reference them
by absolute path.

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
| Run | one **epic** bead; metadata `run_id`, `primary_branch`, `base_sha`, `artifacts` (abs dir) |
| DAG node | **task** bead, `--parent <epic>`, label `orc-node`, metadata `node` (short id), `scope` (JSON array of globs) |
| Node dep | `bd dep add <dependent> <dependency>` (`blocks` type), one per edge |
| Git anchors | node metadata, stamped per the contract below |

```
EPIC=$(bd create "orchestrate run-<id>" --type epic --silent \
  --metadata '{"run_id":"run-<id>","primary_branch":"main","base_sha":"<sha>","artifacts":"<abs>/.orchestration/run-<id>/artifacts"}')
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

- **Mutual exclusion:** `bd merge-slot create` once per run (idempotent);
  `bd merge-slot acquire` before integrating, `release` after. A second
  acquirer fails, or queues with `--wait` — FCFS order comes from the waiters
  queue. On restart, `bd merge-slot check`: held by your own actor name → a
  previous incarnation crashed mid-merge; verify the tree, then `release`.
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
