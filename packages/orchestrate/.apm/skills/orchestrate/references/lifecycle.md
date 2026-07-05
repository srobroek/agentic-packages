# Lifecycle: states, spawn/dismiss, human-in-the-loop, cleanup

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
                                             (gatekeeper: FCFS + conflict-probe)
                                    CONFLICT ─► working (rebase)          │
                                                                          ▼
                                                                merged ─► dismissed
                                            (any state) ───────────────► failed
```

- `pending → ready`: computed by `graph.py ready` (all deps `merged`/`approved`/
  `dismissed` **and** scope globs disjoint from every in-flight node).
- `reported → in_review`: coder finished; orchestrator spawns a `workflow-reviewer`.
- `working (blocked)`: coder sends `BLOCKED` to the orchestrator and idles; the
  orchestrator brokers a `workflow-advisor` and relays `ADVICE` back — the coder
  spawns nothing.
- `changes_requested → working`: coder applies exactly the `FIX` items; the **same**
  reviewer re-reviews the delta.
- `approved → merged`: gatekeeper integrates FCFS after a clean conflict probe.
- `waiting_human`: an agent raised `ASK`; it goes idle, the orchestrator surfaces
  the question, then forwards the answer or lets the user message the agent.
- `failed`: unrecoverable; logged with the error and surfaced.

## Persistence classes

- **Persistent** (spawned once, live the whole run, addressed on demand via
  SendMessage — never polled): **Integration Gatekeeper**, **Ledger Scribe**.
- **Task-scoped, kept alive across fix rounds** (dismissed only after the node is
  approved and merged): **Workflow-coder**; and the **Workflow-reviewer** for that
  node (re-reviews deltas with prior context, dismissed on approval).
- **Ephemeral** (spawn → return → maybe resume for follow-ups): **Researcher**
  (incl. fan-out gatherers + synthesizer), **Workflow-advisor**
  (orchestrator-brokered), **Tiebreaker**.

Stopped background subagents auto-resume when they receive a SendMessage, so a
"kept-alive" agent that has gone idle is simply messaged again — do not re-spawn a
fresh one for the same node (that loses its context and its name may be refused).

## Recycle persistent infra to shed context

The Gatekeeper and Scribe hold **no durable state in their context** — the DAG,
ledger, and git are the source of truth. So recycle them to reclaim their context
window on long runs: dismiss the current one and spawn a fresh replacement with
only the store path + run id; it rehydrates what it needs (Gatekeeper: approved-
but-unmerged nodes via `graph.py list --state approved`, the current base, and any
open conflicts from the ledger; Scribe: nothing — it reads on demand).

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

## Worktree & cleanup ownership

Whoever creates a worktree owns its removal. After a node merges and its coder is
dismissed, the orchestrator sweeps: confirm the worktree is clean
(`git -C <wt> status --porcelain` empty and commits harvested), delete build dirs
(`target/`, `node_modules/`, …), then `git worktree remove <wt>` + `git worktree
prune`. Fan-out runs must sweep after fan-in; periodically check `git worktree
list` for strays. The shared run store (`.orchestration/run-<id>/`) is kept for
post-run forensics, not swept.
