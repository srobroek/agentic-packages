# Message grammar

The canonical envelope, proof rule, and spawning boundary live in
`references/comms-block.md`. This reference defines activation and P2P message
fields.

## Activation

| Target | Entire activation message |
|---|---|
| Directed node | `CLAIM {node-bead-id}` |
| Generic queue | `CLAIM queue:{label-filter}` |
| Review | `CLAIM {review-wisp-id}` |
| Advice or bounded research question | `CLAIM {escalation-wisp-id}` |
| Ledger drain | `CLAIM {query-wisp-id}` |
| Fix or conflict recovery | `CLAIM {same-node-id}` |

Runtime-only wait and checkout binding happen before activation. No task field,
command, role assignment, review item, or question appears in the activation.

## Verbs

| Verb | Direct route | Carries |
|---|---|---|
| `BLOCKED` | specialist -> escalation wisp | node, kind, exact question, minimal refs |
| `ADVICE` | advisor -> escalation wisp | one recommendation, reason, refs |
| `REPORTED` | claim-holder -> work bead | evidence ref, verification, next route |
| `REVIEW` | reviewer -> node + review wisp | dimension, round, verdict, item count |
| `FIX` | reviewer -> review wisp | numbered required actions with refs |
| `CONFLICT` | shepherd -> merge/fix bead | PR/head, files, required outcome |
| `APPROVE` | reviewer/queue sensor -> merge bead | approved head and readiness identity |
| `MERGED` | shepherd -> merge bead | PR, merge SHA, final-base proof |
| `DISMISS` | lifecycle owner -> work bead | terminal disposition and cleanup ref |
| `ASK` | any actor -> escalation wisp | one product-intent question and impact |
| `NO_WORK` | generic actor -> run epic | queue and `reason:no-compatible-work` |

The orchestrator may wake the destination actor after one of these writes. It
does not copy the content into the harness message.

## Thread identity

`scripts/thread-message.py` stores:

| Field | Meaning |
|---|---|
| `actor` | stable sender identity and Beads mutation actor |
| `assignee` | stable recipient identity |
| `run` | run epic id |
| `bead` | affected work bead |
| `protocol` | `replies-to` |

A root message links to the work bead. A reply links to one open message in the
same run and work bead. Replies may branch. Inbox discovery validates the
actor, run, resource, and parent before exposing a message.

Harness delivery remains advisory. Inbox, show, thread rendering, and
acknowledgement remain available after the work bead closes. Send and reply
require an open run and active work bead.

## Material outcomes

A message is material when it changes scope, route, ordering, acceptance
evidence, disposition, policy, or a human answer. Before acting:

1. Promote a bead-local result to an actor-attributed work-bead comment.
2. Promote a cross-bead or shared-contract result to a linked decision bead.
3. Read the promoted record and links back.
4. Cite that record in the action or terminal report.

An artifact is evidence only until a durable record cites it.
A material message not promoted has no policy effect.
The threading path does not require Gas Town, a daemon, or a polling loop.

## Evidence shapes

`REPORTED` accepts exactly one:

- Git: branch, pushed SHA, draft PR/merge bead, and verification.
- Artifact: absolute `output_ref` under `artifacts_dir` and verification.
- Comment: exact comment or audit-event reference and verification.
- External: resource identity, read-back evidence, and verification.

An empty generic activation reports:

```text
NO_WORK queue:{queue-name}
epic: {run-epic-id}
queue: agent:{queue-name}
reason: no-compatible-work
```

## Worked flow

The orchestrator first writes the node metadata and `BRIEF`, prepares and
binds its checkout, then sends:

```text
CLAIM orc-run.3
```

The specialist reads the bead and linked domain context. When blocked, it
creates an escalation wisp and writes:

```text
BLOCKED orc-run.3 kind:design
question: choose the safe refresh serialization strategy
refs: src/auth/refresh.rs:40
```

The orchestrator wakes an advisor with only:

```text
CLAIM orc-wisp-advice
```

The advisor answers on that wisp:

```text
ADVICE orc-run.3
answer: use single-flight keyed by token id
because: the service has multiple processes
refs: src/auth/refresh.rs:40
```

The specialist reads the answer from the wisp, finishes, and reports on the
node. The orchestrator creates all review wisps, binds reviewers, and activates
each by wisp id. A reviewer requesting changes writes `REVIEW` on the node and
`FIX` items on its wisp. The specialist is woken with `CLAIM orc-run.3`, reads
the open review wisps, fixes the union, and reports again. The final reviewer
closes its wisp, swaps the review label, and makes the draft PR ready. The
unblocked merge bead is then claimed by the shepherd.
