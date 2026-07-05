# Writing an agent brief

Every subagent starts with fresh context: it sees only its agent definition, your
delegation prompt, CLAUDE.md, and git status. So the brief must carry **everything
the agent needs to act and to participate in the run** — never assume it knows the
store path, the protocol, or its scope. Keep it terse and complete.

## Every brief must include

1. **Node id** and a one-line task statement.
2. **Owned scope** — the exact file globs the agent may touch (from the DAG node).
   State explicitly: stay inside; do not touch files other nodes own.
3. **Base ref** to work from.
4. **Absolute store path** (`.orchestration/run-<id>/`) — the shared DAG + ledger,
   outside every worktree, reachable from inside the worktree.
5. **The deterministic commands** the agent runs (with the store path filled in):
   - log: `ledger.py --store <store> add --event <e> --node <node> --actor <self> …`
   - state: `graph.py --store <store> set-state <node> <state>`
   - (gatekeeper) `conflict-probe.sh …`
6. **Protocol pointers**: its lifecycle obligations (`references/lifecycle.md`) —
   e.g. a coder must stay alive after `REPORTED`. The comms verb grammar itself is
   **auto-injected** into every subagent by the skill's `SubagentStart` hook
   (`references/comms-block.md`), so you do not paste it — **except into teammate
   briefs**, where you must paste `comms-block.md` verbatim (no hook reaches them).
7. **Role-specific tool guidance** you want it to use (codebase-memory, context7,
   Playwright, project verify command). Do **not** rely on the agent's model
   metadata for this — pass it in the brief.
8. **Escalation rules**: when to raise `BLOCKED` (a coder never spawns its own
   advisor — you broker it), and when to `ASK` for product intent.

## Coder brief — copyable shape

```
ASSIGN <node>
  title:    <one line>
  scope:    <globs you own; stay inside them>
  base:     <ref@sha>
  store:    <abs>/.orchestration/run-<id>/      # DAG + ledger live here
  deps:     <node(done), …>
  commands:
    state:  graph.py --store <store> set-state <node> <state>
    log:    ledger.py --store <store> add --event <e> --node <node> --actor coder-<node> …
    verify: <project verify cmd, e.g. `just test` / `cargo test -p <crate>`>
  protocol: on block → BLOCKED to main (do NOT spawn an advisor). After green:
            commit + push branch, log `reported`, send REPORTED to main, STAY ALIVE.
            Apply only FIX items; same reviewer re-reviews delta. Dismissed on DISMISS.
  tools:    <codebase-memory / context7 / etc. as relevant>
  ASK:      raise ASK <node> for anything needing product intent not covered here.
```

## Persistent-infra brief (once each)

Give the **gatekeeper** and **scribe** only the store path, the run id, and their
job pointer — they carry their own protocol in their agent definition. Example:
`You are the run gatekeeper. store=<abs>. Integrate approved branches FCFS,
conflict-guarded; message me MERGED/CONFLICT. Await approved nodes.`

## Reviewer brief (one per code node — you spawn it, not the coder)

Spawn a `workflow-reviewer`:
`Review node <node>: branch <b> at worktree <wt> (base <ref>). Scope <globs>.
Report REVIEW <node> verdict=approve|changes; for changes give a numbered list,
each` file:line — problem — required action `(one clause each, no essays). Log the
verdict with --event review. You are kept alive to re-review the delta only.`
Escalate the reviewer to opus in the brief when the diff is complex or
security-critical.

## Advisor brief (you broker it when a coder raises BLOCKED)

Spawn a `workflow-advisor` with the coder's question verbatim + the minimal code
context from its `BLOCKED`:
`Answer <node>: <question>. Context: <file:line …>. Reply ADVICE <node> with
answer / because / refs — one call, read-only.` Relay its `ADVICE` back to the
coder, then dismiss the advisor.
