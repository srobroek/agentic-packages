# Lifecycle: states, spawn/dismiss, resume, human-in-the-loop, cleanup

Agent lifecycle and task-node state share one vocabulary, tracked in the DAG with
`graph.py set-state <node> <state>` and mirrored to the ledger.

## State diagram

```
                 ┌────────── ASK (question) ──► waiting_human ──(answer)──┐
                 │                                                         ▼
pending ─ready─► working ─(BLOCKED→orch brokers advisor→ADVICE)─► working ─► reported ─► in_review
   ▲ graph.py                                                               │
   │  ready                                     changes_requested ◄─────────┤ verdict=changes
   │                                                    │                   │ verdict=approve
   └──────────── deps done + scope free ────────────────┘                   ▼
                                                                         approved
                                             (orch: APPROVE → gatekeeper: FCFS + conflict-probe)
                                    CONFLICT ─► working (rebase)          │
                                                                          ▼
                                                                merged ─► dismissed
                                            (any state) ───────────────► failed
```

Blocked coders stay in `working` — `BLOCKED` is a message, not a node state.

## Transitions

| Transition | Trigger |
|---|---|
| `pending → ready` | `graph.py ready`: all deps `merged`/`approved`/`dismissed` AND scope globs disjoint from every in-flight node |
| `reported → in_review` | coder finished; orchestrator spawns a `workflow-reviewer` |
| `working` (blocked) | coder sends `BLOCKED kind:design\|debug` to orchestrator, idles; orchestrator brokers `workflow-advisor`/debugger, relays `ADVICE` back; coder spawns nothing |
| `changes_requested → working` | coder applies exactly the `FIX` items; same reviewer re-reviews the delta |
| `approved → merged` | orchestrator sends `APPROVE`; gatekeeper integrates FCFS after a clean conflict probe |
| `waiting_human` | agent raised `ASK`; goes idle; orchestrator surfaces the question, forwards the answer or lets the user message the agent directly |
| `failed` | unrecoverable; logged with the error, surfaced |

## Persistence classes

| Class | Agents | Rule |
|---|---|---|
| Persistent | Integration Gatekeeper, Ledger Scribe | spawned once, live the whole run, addressed via SendMessage — never polled |
| Task-scoped | Workflow-coder; Workflow-reviewer (per node) | kept alive across fix rounds; reviewer re-reviews deltas with prior context; dismissed only after the node is approved and merged. Never re-spawn a fresh coder for an in-flight node — resume its handle instead. |
| Ephemeral | Researcher (+ fan-out gatherers/synthesizer), Workflow-advisor/debugger (orchestrator-brokered), Tiebreaker | spawn → return → maybe resume for follow-ups |

Stopped background subagents auto-resume on SendMessage. Never re-spawn a fresh
agent for the same node — it loses context and its name may be refused.

## Resume after orchestrator compaction/crash

1. List in-flight nodes: `graph.py --store <store> list --state
   working,reported,in_review,changes_requested`.
2. Recover each node's agent handle from its meta: `assignee`, set at spawn via
   `graph.py --store <store> set-meta <node> --assignee <agentId>`.
3. Cross-check with `ledger.py --store <store> agents`.
4. Re-spawn only nodes whose meta shows no `assignee` (truly orphaned); resume
   everything else by messaging the recovered handle.

## Failure propagation

- `failed` never satisfies a dependency — the ready computation already
  requires deps to be `merged`/`approved`/`dismissed`, so a `failed` upstream
  node permanently blocks its dependents.
- `graph.py --store <store> impact <node>` lists every downstream node stranded
  by a failure. The orchestrator re-plans (new node covering the gap) or
  abandons the stranded subtree — never lets it silently stall as `pending`.

## Recycle persistent infra to shed context

The Gatekeeper and Scribe are restartable at any quiescent point — the DAG,
ledger, and git are the source of truth, not their context. Dismiss the current
one and spawn a fresh replacement with only the store path + run id.

- **Gatekeeper:** recycle at a **quiescent point** — after a merge completes and
  before picking up the next, never mid-conflict-negotiation with a coder. Trigger
  every N merges or when its context grows large.
- **Scribe:** read-only; restartable anytime.
- **Coders are NOT recycled mid-node** — their in-progress reasoning for that node
  is the work. They are short-lived per node anyway; let them finish and dismiss.

## Human-in-the-loop

When an agent needs a decision outside its brief (product intent, ambiguous scope,
during speccing/grilling), it sends `ASK <node> <question>` to `main` and idles.
The orchestrator: (1) notifies the user; (2) holds the agent in `waiting_human`;
(3) either forwards the user's answer (`FIX`/`ASSIGN`/free text) or lets the user
select and message that agent directly. Never let an agent guess product intent.

## Worktree & cleanup

Sweep after fan-in, per the global worktree rule. The run store
(`.orchestration/run-<id>/`) is never swept.
