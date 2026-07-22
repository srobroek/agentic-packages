# Lifecycle: states, dispatch, review, recovery, ambiguity, cleanup

Agent lifecycle and task-node state share one vocabulary, tracked on the
node's bead: `bd set-state <bead> state=<name> --reason "<why>"` plus bead
status per the mapping table in `references/beads-store.md`.

## State diagram

```
                 ┌────────── ASK (question) ──► waiting_human ──(answer)──┐
                 │                                                         ▼
pending ─ready─► working ─(BLOCKED→orch brokers advisor→ADVICE)─► working ─► reported ─► in_review
   ▲ bd ready +                                                             │
   │ scope/route clean                          changes_requested ◄─────────┤ verdict=changes
   │                                                    │                   │ verdict=approve
   └──────────── deps closed + scope free ──────────────┘                   ▼
                                                                         approved
                                             git: APPROVE → gatekeeper   │ non-git: evidence accepted
                                    CONFLICT ─► working (rebase)          │
                                                 │                        ▼
                                                 └────────► merged ───► dismissed
                                            (any state) ───────────────► failed
```

Blocked workers stay in `working` — `BLOCKED` is a message, not a node state.

## Transitions

| Transition | Trigger |
|---|---|
| `pending → ready` | `bd ready --label orc-node --parent <epic>` reports the node, no gate is open, scope is clean, and routing envelope is complete |
| `ready → working` | directed worker atomically claims its assigned bead with `bd update <bead> --claim`, or generic worker atomically claims the first compatible queue bead with filtered `bd ready --claim` |
| `reported → in_review` | worker reports declared evidence; orchestrator spawns a different compatible reviewer |
| `working` (blocked) | worker sends `BLOCKED kind:design\|debug`, idles, and spawns nothing; orchestrator brokers and relays `ADVICE` |
| `changes_requested → working` | same worker applies exactly the `FIX` items; same reviewer re-reviews the delta |
| `approved → merged` | git evidence only: orchestrator sends `APPROVE`; lifecycle events may wake revalidation, but only an exact ready dispatch enters the watcher-backed merge path; gatekeeper invokes N7's shared landing transaction, which revalidates identity/CI, serializes on the merge slot, proves the final base, releases, and closes |
| `approved → dismissed` | non-git evidence only: orchestrator records accepted evidence, sets `state=dismissed`, closes, then dismisses worker and reviewer |
| `waiting_human` | agent raised `ASK`; orchestrator records the question and holds the node. A node not started also gets `bd gate create --type=human --blocks <bead>` |
| `failed` | unrecoverable; set `state:failed` plus status `blocked`, log the error, and surface it |

## Completion paths

The node's `execution_evidence` selects the terminal path, not whether its
subject sounds technical.

| Evidence | Required completion proof | Terminal owner |
|---|---|---|
| `git` | pushed branch, commit SHAs, scoped verification, independent branch review | gatekeeper closes as `merged` |
| `artifact` | absolute `output_ref`, method, verification, independent evidence review | orchestrator closes as `dismissed` |
| `comment` | bead comment or audit-event ref, verification, independent evidence review | orchestrator closes as `dismissed` |
| `external` | resource identity, read-back or before/after evidence, verification, independent evidence review | orchestrator closes as `dismissed` |

Tracked documentation and configuration changes use `git`. Research, analysis,
read-only review, and external operations may use non-git evidence. Non-git
work follows the same claim, report, independent review, fix, approval, and
closure states. It never creates an empty commit, placeholder branch, or fake
merge requirement.

## Persistence classes

| Class | Agents | Rule |
|---|---|---|
| Persistent | Integration Gatekeeper, Ledger Scribe | spawned once, live the whole run, addressed via SendMessage — never polled |
| Task-scoped | Directed worker or Generic pull worker; independent reviewer | kept alive across fix rounds; reviewer re-reviews deltas; dismissed only after merge or approved non-git closure. Never re-spawn a fresh worker for a live claim |
| Ephemeral | Researcher gatherers/synthesizer, Workflow-advisor/debugger, Tiebreaker | spawn → return → maybe resume for follow-ups |

Stopped background subagents auto-resume on SendMessage. Never re-spawn a fresh
agent for the same live claim — it loses context and may create a second writer.

## Resume after orchestrator compaction or crash

1. Find the run epic: `bd list --type epic --json` and match metadata `run_id`.
2. Read in-flight nodes with `bd list --label orc-node --parent <epic>
   --status in_progress --json`. Each recovery record carries exact actor in
   `assignee`, directed or generic mode in `execution_dispatch`, branch/worktree
   or non-git resource scope, and the fine-grained `state:` label.
3. Run `bd merge-slot check`. Never infer a dead holder from age or a recycled
   gatekeeper. Resume the N7 landing transaction, or use its evidence-gated
   recovery command after proving the exact actor lease is dead.
4. Resume every live assignee by messaging its recovered handle. Never route an
   assigned bead to a generic queue. Treat an unassigned `in_progress` bead as
   inconsistent and run dead-claim recovery before redispatch.
5. Restart each GitHub repository watcher with `--slots=1`. Replay every node
   whose current `queue_dispatch` or `queue_lifecycle` lacks its matching ack;
   pending or sent receipts identify the last completed delivery step. Only a
   matching ack suppresses replay. Normalize key-only migration records before
   SendMessage by stamping a pending receipt. Route records unmatched to the
   run once through pr-shepherd. The gatekeeper resumes acknowledged, approved,
   unmerged nodes from its startup scan; see
   `references/queue-watcher.md`.

## Dead-claim recovery

Age is a diagnostic, not proof of death. `bd stale --status in_progress` may
identify candidates, but there is no automatic lease expiry and no daemon is
required. Never steal a claim because a timestamp is old.

1. Read the bead, comments, audit trail, actor handle, branch/worktree or
   non-git resource scope, and last verification evidence.
2. Try to resume the actor. Clear ownership only when the platform reports the
   handle stopped or absent, the actor explicitly releases it, or the user
   confirms the session is dead. Record that evidence before mutation.
3. Preserve the worktree, pushed branch, artifacts, comments, and external
   resource references. Do not sweep them during recovery.
4. Record recovery with a bead comment and `orc.recover` audit event. Beads
   1.1.0 has no `bd unclaim`; release and reopen with:

```
bd update <bead> --assignee "" --status open
bd set-state <bead> state=pending --reason "dead claim verified; redispatch"
```

5. For directed recovery, assign the replacement actor before sending its
   recovery brief. For generic recovery, restore one compatible
   `agent:<queue>` and leave the bead unassigned. The replacement claims
   atomically and receives every preserved anchor.

If holder death is uncertain, keep the assignment and record a revisit trigger.
That safe default prevents two workers from mutating the same scope.

## Failure propagation

- `failed` never satisfies a dependency. A failed node's bead is `blocked`,
  never `closed`, so dependents stay out of `bd ready`.
- `bd dep tree <bead>` shows every downstream node stranded by a failure. The
  orchestrator replans with a replacement node or abandons the subtree; it does
  not leave the graph silently stalled.

## Recycle persistent infra to shed context

The Gatekeeper and Scribe are restartable at a quiescent point because Beads
and git are the source of truth.

- **Gatekeeper:** recycle after a merge completes and the slot is released,
  never during conflict negotiation.
- **Scribe:** read-only; restartable anytime.
- **Task workers:** never recycle mid-node. Their in-progress reasoning belongs
  to the claimed node. Dismiss after its terminal path.

## Human-in-the-loop and safe autonomy

An agent may choose a default autonomously only when every condition is true:

- the action and its effects are reversible;
- the effect is local to one bead and its owned resources;
- the downside and rollback boundary are explicit and bounded;
- the choice is compatible with accepted policy and recorded evidence; and
- the choice preserves user intent rather than selecting or changing it.

Record the ambiguity before applying the default. A cross-boundary choice that
existing evidence fully resolves uses a decision bead. Cross-boundary
uncertainty, irreversible action, external mutation, security/financial/legal
risk, or missing user intent is not an autonomous default. It enters
`waiting_human` with one exact question and its impact.

The orchestrator adds this comment to the affected bead:

```text
WAITING_HUMAN
owner: <actor responsible for resumption>
scope: <bead and affected resource>
question: <one exact choice the human must make>
impact: <what remains stopped and what each answer changes>
resume: <exact state transition, gate action, and actor to wake>
```

Every field is nonempty. The question cannot delegate discovery back to the
human or ask for general approval. The orchestrator records `orc.ask`, runs
`bd set-state <bead> state=waiting_human --reason "<question summary>"`, and
keeps status `in_progress`. The resulting `state:waiting_human` label is the
durable hold. A node that had not started also receives
`bd gate create --type=human --blocks <bead> --reason "<question>"`.

The orchestrator does not poll the human or the held worker. It continues
unrelated nodes returned by `bd ready`. On an answer, it promotes any message
into a work-bead comment or decision bead, resolves the human gate when one
exists, and follows the stored `resume` instruction. A started node returns to
`state=working`, status `in_progress`, and the same agent. An unstarted node
returns to `state=pending`, status `open`, and normal dispatch.

## Durable ambiguity and autonomous defaults

Every unresolved choice uses this complete record before action:

```text
AMBIGUITY
owner: <one actor accountable for review>
scope: <work bead and exact resources>
evidence: <known file:line, bead, command result, or searched-none>
unknown: <fact or intent that remains unresolved>
default: <chosen reversible local action>
bounds: <downside, rollback point, and prohibited effects>
revisit: <objective event, evidence change, dependency transition, or RFC3339>
```

Empty fields are invalid. `revisit` is objective: `later`, `if needed`, and
elapsed time without a named deadline are invalid. The default cannot exceed
the autonomy conditions above.

Local ambiguity is a comment on the affected bead. Cross-bead, cross-agent,
cross-package, shared-contract, ordering, or later-work impact is a decision
bead under the run epic with metadata keys `ambiguity_owner`,
`ambiguity_scope`, `ambiguity_evidence`, `ambiguity_unknown`,
`ambiguity_default`, `ambiguity_bounds`, and `ambiguity_revisit`. Link affected
and validating work with non-blocking `relates-to` and `validates` edges as
defined in `references/beads-store.md`.

| Situation | Safe recorded result |
|---|---|
| exact assignee conflicts with another route | preserve the assignee; no other worker claims |
| capability, access, or scope compatibility is unknown | do not dispatch or claim; revisit on named catalog or owner evidence |
| specialist and generic routes both match | choose the compatible specialist |
| generic queue has several ready beads | atomic priority claim; never cherry-pick |
| tracked-file versus artifact evidence is unclear | tracked mutation → `git`; read-only result → inspectable artifact |
| dead-claim evidence is incomplete | keep the claim and anchors |
| a local reversible implementation detail lacks evidence | record the bounded default and its evidence-triggered revisit |
| product intent, cross-boundary uncertainty, or unsafe effect is unresolved | `waiting_human`; never infer consent |

## Revisit, conflict, and late evidence

At the recorded trigger, the owner re-reads the cited evidence before any
further use of the default. A fired trigger makes the default stale until the
owner adds an `AMBIGUITY_RESOLVED` comment with the prior record id, new
evidence, disposition, and resulting action. Routing changes only while the
bead is unassigned.

A local choice that changes gets a new comment referencing the old comment; no
comment is edited or erased. A cross-boundary change gets a replacement
decision bead and explicit supersession. Duplicate, conflicting, superseded,
and partially linked decisions follow the deterministic rules in
`references/beads-store.md`; chronology alone never selects policy.

Restart recovery reads work-bead comments, decision beads, their dispositions
and links, and `state:waiting_human` before resuming any agent. Message wisps
and artifacts supply coordination/evidence only. An unpromoted material
message is not replay authority.

Late evidence follows the same revisit flow. If the affected bead is closed,
append the evidence and disposition to that closed bead or its decision bead.
When behavior must change, create follow-up work with a `discovered-from` link;
do not reopen the completed bead or rewrite its terminal evidence.

## Worktree and cleanup

Sweep after fan-in, per the global worktree rule. The artifacts directory and
Beads database are never swept. Stop repository watchers before removing
run-local process state. Non-git nodes have no worktree to sweep.
