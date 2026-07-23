# Release queue watcher handoff

`release-queue-watch` is a read-only sensor for GitHub-backed runs. It emits
ranked readiness dispatches and PR lifecycle records. Orchestrate resolves its
own nodes first; a record without an orchestrate owner may route once to
`pr-shepherd`. The watcher never assigns agents, changes Beads, acquires the
merge slot, or mutates GitHub.

## Start and ownership boundary

Resolve the installed watcher skill and start one runtime per repository with
`pnpm --silent start`, `--slots=1`, and REST reconciliation enabled. Consume
stdout NDJSON plus structured stderr errors serially; do not read the next line
until the current receipt is durable. One watcher slot
limits outstanding readiness notifications. It is not the Beads merge lock.

| Concern | Owner |
|---|---|
| Signature verification, debounce, PR ranking, REST repair | `release-queue-watch` |
| Orchestrate node lookup and agent assignment | orchestrator |
| Unmatched generic merge-bead lookup | `pr-shepherd` resolver |
| Orchestrate PR/head revalidation | integration gatekeeper |
| Generic PR/head revalidation | PR shepherd |
| Exclusive integration lock | `bd merge-slot` held by the selected integrator |

An exact active orchestrate node owns its PR. If the run also creates an
`agent:integrator` merge bead, stamp `integration_owner=orchestrate`; the
generic shepherd refuses it. This precedence prevents two merge actors from
racing.

## JSON contracts

A ready dispatch contains a full pull-request snapshot:

```json
{
  "type": "dispatch",
  "pullRequest": {
    "repository": "owner/repo",
    "number": 42,
    "title": "Ready change",
    "headSha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "baseRef": "main",
    "labels": ["priority:high"],
    "priority": 1,
    "draft": false,
    "mergeable": true,
    "checks": "pass",
    "createdAt": "2026-07-21T00:00:00Z",
    "updatedAt": "2026-07-21T01:00:00Z",
    "state": "active",
    "activeSince": "2026-07-21T01:00:01Z"
  }
}
```

Its identity is `repository#number@headSha`. Ready admission facts are not
authorization to merge.

A lifecycle record carries the same `pullRequest` shape plus:

```json
{
  "type": "pr-lifecycle",
  "transition": "failed",
  "source": "webhook",
  "lifecycleKey": "owner/repo#42#opaque-state-fingerprint",
  "pullRequest": {}
}
```

Transitions are `opened`, `updated`, `failed`, `merged`, and `closed`; source
is `webhook` or `reconciliation`. Treat `lifecycleKey` as opaque. Its state
fingerprint includes observed CI attempts, including changes for which GitHub
does not advance `pull_request.updated_at`.

## Deterministic routing

For every line:

1. Snapshot active run nodes:

   ```text
   bd list --label orc-node --parent <epic> --status in_progress --json
   ```

2. Call `resolve-queue-dispatch.py --nodes-file <snapshot>`. Despite its stable
   filename, the resolver validates both dispatch and lifecycle records.
3. An exact orchestrate match owns the record. Resolver exit 2 means no
   orchestrate owner; offer the unchanged line once to pr-shepherd's
   `resolve-queue-event.py` with an active merge-bead snapshot.
4. Exit 3 means ambiguous or invalid orchestrate ownership and must not fall
   through. Control records are ignored. Malformed, stale, or ambiguous records
   produce `orc.note` and no assignment. Never fan one line to both consumers.

## Ready dispatch receipts

The resolver requires exactly one `state:approved` node matching `repo`, `pr`,
and `head_sha`.

1. Apply all `requiredMetadata` in one `bd update`. A new dispatch atomically
   stamps `queue_dispatch` and `queue_dispatch_pending`.
2. Send the persistent gatekeeper:

   ```text
   APPROVE <node>
   branch: <metadata.branch>
   base: <metadata.base_sha>
   source: release-queue-watch
   repo: <repository>
   pr: <number>
   head: <headSha>
   dispatch: <identity-key>
   ```

3. After SendMessage accepts the handoff, stamp
   `queue_dispatch_sent=<identity-key>`. The gatekeeper validates the matching
   pending or sent receipt and stamps `queue_dispatch_ack=<identity-key>` before
   authoritative revalidation.
4. `status=replay` reuses pending or sent receipts. Apply an emitted legacy
   normalization first. `status=duplicate` has a matching ack and is not sent.

Pending, sent, and ack are monotonic receipts. A late sent update must not erase
an ack. Every receipt present for the current dispatch must contain its exact
identity key. Do not replace an unacknowledged dispatch with a later record;
the resolver exits 3 on crossed or mismatched receipts. Acknowledgment records
delivery, not merge permission.

## Lifecycle receipts

Lifecycle resolution matches one active orchestrate node by `repo` and `pr`.
A head mismatch is reported as `headChanged`; it is never trusted as the new
anchor until the gatekeeper confirms GitHub.

- Approved nodes and `failed`, `merged`, or `closed` transitions set
  `wakeGatekeeper=true`. Persist `queue_lifecycle`,
  `queue_lifecycle_transition`, `queue_lifecycle_head`, and
  `queue_lifecycle_pending` atomically, then send:

  ```text
  APPROVE <node>
  branch: <metadata.branch>
  base: <metadata.base_sha>
  source: release-queue-watch-lifecycle
  repo: <repository>
  pr: <number>
  head: <headSha>
  transition: <transition>
  lifecycle: <lifecycleKey>
  ```

  Stamp `queue_lifecycle_sent` after SendMessage. The gatekeeper stamps
  `queue_lifecycle_ack` only after it revalidates and records the outcome.
- `opened` or `updated` on an unapproved node is informational. Persist the
  resolver's atomic `queue_lifecycle_ack`; do not wake a merge actor.
- A stale failure is a no-op after revalidation. Confirmed failure routes back
  to the coder. For a confirmed external merge, the approved head must still
  equal GitHub's head; the gatekeeper passes the actual merge SHA to N7's
  `verify-landed` transaction and closes only after final-base ancestry or
  exact-content proof. Confirmed close-without-merge is reported to the
  orchestrator; it is not silently treated as merged.
- A lifecycle wake-up never acquires the merge slot or merges. A separate valid
  dispatch is required to enter the watcher-backed merge path. Even when the
  node already stores an older dispatch, finish and acknowledge the lifecycle
  handling without entering `land`; resume the dispatch in its own pass.

## Crash recovery and fallback

Before reading new watcher output on start or resume, run:

```text
resolve-queue-dispatch.py --nodes-file <snapshot> --replay-unacknowledged
```

Replay the returned `dispatches` and `lifecycles` after applying any non-empty
`requiredMetadata`. Invalid persisted identity stops that replay; log it rather
than guessing. A current key with a receipt for another key, or a new record
arriving before the current key is acknowledged, is invalid ownership state.
Gatekeeper startup also resumes acknowledged approved nodes that have not
merged.

REST reconciliation belongs to the watcher. Initial reconciliation may emit
records before `watcher-active`. On `webhook-error`, `reconcile-error`, malformed
output, or watcher exit, surface the error and run one explicit `bd gate check`
plus the existing gatekeeper/shepherd pass. Restart or stop the watcher; never
start a duplicate CI polling loop and never infer green or merged state from
silence.

Stop the watcher during run cleanup.
