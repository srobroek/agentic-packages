# Release queue watcher handoff

`release-queue-watch` is a read-only readiness sensor for GitHub-backed runs.
It ranks pull requests and emits JSON records. Orchestrate validates those
records, maps them to existing approved node beads, and decides which agent to
wake. The watcher never assigns agents, changes beads, acquires the merge slot,
or mutates GitHub.

## Start and ownership boundary

Resolve the installed `release-queue-watch` skill, follow its setup workflow,
and start one watcher per repository with `--slots=1`. Keep its REST
reconciliation enabled. One watcher slot limits outstanding readiness signals;
it is not the Beads merge lock.

| Concern | Owner |
|---|---|
| Webhook signature verification, event debounce, PR ranking | `release-queue-watch` |
| Dispatch validation and node lookup | orchestrator |
| Node/agent assignment | orchestrator |
| PR and head metadata | integration gatekeeper |
| Exclusive integration lock | `bd merge-slot` held by integration gatekeeper |
| Conflict, CI, and merge revalidation | integration gatekeeper |

The watcher process may stay alive for the run. Stop it during run cleanup. A
watcher crash or malformed record never grants merge permission.

## Dispatch JSON contract

The watcher writes one JSON object per line. Only `type=dispatch` enters the
handoff. Unknown fields are tolerated; the following fields are required:

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

The identity key is `repository#number@headSha`. `draft=false`,
`mergeable=true`, `checks=pass`, and `state=active` are admission facts from
the watcher, not authorization to merge.

## Resolve and assign

1. Snapshot approved nodes from the run:

   ```text
   bd list --label orc-node --parent <epic> --status in_progress --json
   ```

2. Pass the JSON line and snapshot to
   `scripts/resolve-queue-dispatch.py --nodes-file <snapshot>`. The resolver is
   read-only and requires exactly one `state:approved` node whose metadata
   matches `repo`, `pr`, and `head_sha`.
3. `status=resolved` → stamp `queue_dispatch=<identity-key>` on that node, log
   `orc.approve`, then send the persistent gatekeeper:

   ```text
   APPROVE <node>
   branch: <metadata.branch>
   base: <metadata.base_sha>
   source: release-queue-watch
   pr: <number>
   head: <headSha>
   dispatch: <identity-key>
   ```

4. `status=duplicate` or `status=ignored` → do not send another message.
   Invalid, stale, unmatched, or ambiguous records → log `orc.note`, request a
   fresh node snapshot, and assign no agent.

Never create a coder, reviewer, or node from an unmatched pull request. Product
policy enters the run through its bead DAG; the watcher only wakes the
gatekeeper for a node the orchestrator already approved.

## Gatekeeper revalidation

When the gatekeeper first opens a PR, it stamps `repo`, `pr`, and `head_sha` on
the node and releases any held merge slot while CI waits. On a watcher-backed
`APPROVE`, it verifies the dispatch PR/head against that metadata, checks the
GitHub gate, then acquires `bd merge-slot` before the conflict probe and merge.
It releases the slot on wait, conflict, failure, or success.

REST reconciliation belongs to the watcher and remains enabled so missed
webhooks can produce a later dispatch. The GitHub gate and conflict probe remain
authoritative: the gatekeeper rechecks both after every dispatch. If the watcher
reports an error or exits, surface it and use the existing gatekeeper path only
after an explicit GitHub gate check; never infer green state from silence.
