# Lifecycle: states, spawn/dismiss, resume, human-in-the-loop, cleanup

Agent lifecycle and task-node state share one vocabulary, tracked on the
node's bead: `bd set-state <bead> state=<name> --reason "<why>"` plus bead
status per the mapping table in `references/beads-store.md`.

## State diagram

```
                 ┌────────── ASK (question) ──► waiting_human ──(answer)──┐
                 │                                                         ▼
pending ─ready─► working ─(BLOCKED→orch brokers advisor→ADVICE)─► working ─► reported ─► in_review
   ▲ bd ready +                                                             │
   │ scope-check.py                             changes_requested ◄─────────┤ verdict=changes
   │                                                    │                   │ verdict=approve
   └──────────── deps closed + scope free ──────────────┘                   ▼
                                                                         approved
                                             (orch: APPROVE → gatekeeper: merge-slot + conflict-probe)
                                    CONFLICT ─► working (rebase)          │
                                                                          ▼
                                                                merged ─► dismissed
                                            (any state) ───────────────► failed
```

Blocked coders stay in `working` — `BLOCKED` is a message, not a node state.

## Transitions

| Transition | Trigger |
|---|---|
| `pending → ready` | `bd ready --label orc-node --parent <epic>` (all blocking deps closed, no open gate) AND `scope-check.py --candidate <bead>` clean |
| `ready → working` | coder: `bd update <bead> --claim` (atomic, first-wins) + stamp `branch`/`worktree`/`base_sha` metadata |
| `reported → in_review` | coder finished; orchestrator spawns a `workflow-reviewer` |
| `working` (blocked) | coder sends `BLOCKED kind:design\|debug` to orchestrator, idles; orchestrator brokers `workflow-advisor`/debugger, relays `ADVICE` back; coder spawns nothing |
| `changes_requested → working` | coder applies exactly the `FIX` items; same reviewer re-reviews the delta |
| `approved → merged` | orchestrator sends `APPROVE`; gatekeeper acquires the merge slot, probes conflicts, merges, stamps `pr`/`merge_sha`, closes the bead |
| `waiting_human` | agent raised `ASK`; goes idle; orchestrator surfaces the question, forwards the answer or lets the user message the agent directly. Node not yet started → also `bd gate create --type=human --blocks <bead>` |
| `failed` | unrecoverable; `state:failed` + status `blocked` (never satisfies a dep), logged with the error, surfaced |

## Persistence classes

| Class | Agents | Rule |
|---|---|---|
| Persistent | Integration Gatekeeper, Ledger Scribe | spawned once, live the whole run, addressed via SendMessage — never polled |
| Task-scoped | Workflow-coder; Workflow-reviewer (per node) | kept alive across fix rounds; reviewer re-reviews deltas with prior context; dismissed only after the node is approved and merged. Never re-spawn a fresh coder for an in-flight node — resume its handle instead. |
| Ephemeral | Researcher (+ fan-out gatherers/synthesizer), Workflow-advisor/debugger (orchestrator-brokered), Tiebreaker | spawn → return → maybe resume for follow-ups |

Stopped background subagents auto-resume on SendMessage. Never re-spawn a fresh
agent for the same node — it loses context and its name may be refused.

## Resume after orchestrator compaction/crash

1. Find the run epic: `bd list --type epic --json` (metadata `run_id`).
2. In-flight nodes: `bd list --label orc-node --parent <epic> --status
   in_progress --json`. Each bead carries the recovery record: `assignee` =
   the agent handle (set atomically by the coder's `--claim`), metadata
   `worktree`/`branch` = where the work physically lives, `state:` label = the
   fine-grained state.
3. `bd merge-slot check` — a slot held by a crashed gatekeeper must be
   verified and released before integration resumes.
4. Re-spawn only unassigned in-flight beads (truly orphaned); resume
   everything else by messaging the recovered handle.

## Failure propagation

- `failed` never satisfies a dependency — a failed node's bead is `blocked`,
  never `closed`, so dependents stay out of `bd ready` permanently.
- `bd dep tree <bead>` shows every downstream node stranded by a failure. The
  orchestrator re-plans (new node covering the gap) or abandons the stranded
  subtree — never lets it silently stall as `pending`.

## Recycle persistent infra to shed context

The Gatekeeper and Scribe are restartable at any quiescent point — beads and
git are the source of truth, not their context. Dismiss the current one and
spawn a fresh replacement with only the epic id + artifacts path.

- **Gatekeeper:** recycle at a **quiescent point** — after a merge completes
  (slot released) and before picking up the next, never mid-conflict-negotiation
  with a coder. Trigger every N merges or when its context grows large.
- **Scribe:** read-only; restartable anytime.
- **Coders are NOT recycled mid-node** — their in-progress reasoning for that
  node is the work. They are short-lived per node anyway; let them finish and
  dismiss.

## Human-in-the-loop

When an agent needs a decision outside its brief (product intent, ambiguous scope,
during speccing/grilling), it sends `ASK <node> <question>` to `main` and idles.
The orchestrator: (1) notifies the user; (2) holds the agent in `waiting_human`;
(3) either forwards the user's answer (`FIX`/`ASSIGN`/free text) or lets the user
select and message that agent directly. Never let an agent guess product intent.

## Worktree & cleanup

Sweep after fan-in, per the global worktree rule. The artifacts dir
(`.orchestration/run-<id>/`) and the beads database are never swept.
