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
| `approved → merged` | git evidence only: orchestrator sends `APPROVE`; lifecycle events may wake revalidation, but only an exact ready dispatch enters the watcher-backed merge path; gatekeeper acquires the merge slot, probes conflicts, revalidates, merges, stamps `merge_sha`, and closes |
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
3. Run `bd merge-slot check`. Verify and release a slot held by a crashed
   gatekeeper before integration resumes.
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

## Human-in-the-loop

When an agent needs product intent or a decision outside its brief, it sends
`ASK <node> <question>` to `main` and idles. The orchestrator records the
question, sets `waiting_human`, notifies the user, then forwards the answer to
the same agent. Never let an agent guess product intent.

## Durable ambiguity and autonomous defaults

An ambiguity that changes routing, scope, acceptance evidence, ordering, or an
external mutation must survive agent context. Record it before applying a
default:

```
AMBIGUITY owner=<actor> scope=<node/resources> evidence=<refs-or-searched-none>
default=<bounded reversible action> revisit=<event, dependency wake, or RFC3339>
```

Local ambiguity is a comment on the affected bead. Cross-node or contract
ambiguity is a decision bead under the run epic with metadata keys
`ambiguity_owner`, `ambiguity_scope`, `ambiguity_evidence`,
`ambiguity_default`, and `ambiguity_revisit`. Link each affected node with
`bd dep add <node> <decision> --type relates-to`. Product intent that blocks
work also creates a human gate and uses `waiting_human`.

| Situation | Safe default |
|---|---|
| exact assignee conflicts with another route | preserve the assignee; no other worker claims |
| capability, access, or scope compatibility is unknown | do not dispatch or claim; revisit after catalog or owner evidence |
| specialist and generic routes both match | choose the specialist |
| generic queue has several ready beads | atomic priority claim; never cherry-pick |
| tracked-file versus artifact evidence is unclear | tracked mutation → `git`; read-only result → inspectable artifact |
| dead-claim evidence is incomplete | keep the claim and anchors |
| product intent or irreversible external effect is unresolved | `waiting_human`; never infer consent |

At the recorded trigger, the ambiguity owner re-reads the cited evidence,
records `RESOLVED` or an updated default/revisit value, and changes routing only
while the bead is unassigned. Silent adaptation is prohibited.

## Worktree and cleanup

Sweep after fan-in, per the global worktree rule. The artifacts directory and
Beads database are never swept. Stop repository watchers before removing
run-local process state. Non-git nodes have no worktree to sweep.
