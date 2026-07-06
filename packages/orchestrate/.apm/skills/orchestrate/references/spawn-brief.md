# Writing an agent brief

Every subagent starts with fresh context. The brief must carry everything the agent
needs to act and participate in the run — node id, owned scope, base ref, absolute
store path, deterministic commands, protocol pointers, tool guidance, and escalation
rules — templates below.

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
    meta:   graph.py --store <store> set-meta <node> --assignee <agentId>
    log:    ledger.py --store <store> add --event <e> --node <node> --actor coder-<node> …
    verify: <project verify cmd, e.g. `just test` / `cargo test -p <crate>`>
  protocol: on block → BLOCKED kind:<design|debug> to main (do NOT spawn). After green:
            commit + push branch, log `reported`, send REPORTED to main, STAY ALIVE.
            Apply only FIX items; same reviewer re-reviews delta. Dismissed on DISMISS.
  tools:    <codebase-memory / context7 / etc. as relevant>
  ASK:      raise ASK <node> for anything needing product intent not covered here.
```

The orchestrator records `--assignee <agentId>` at spawn and `--branch --commit` once
the node is `REPORTED` — see `references/lifecycle.md` (Resume).

## Persistent-infra brief (once each)

Give the **gatekeeper** and **scribe** only the store path, the run id, and their
job pointer — they carry their own protocol in their agent definition. Example:
`You are the run gatekeeper. store=<abs>. Integrate approved branches FCFS,
conflict-guarded; message me MERGED/CONFLICT. Await approved nodes.`

## Reviewer brief (one per code node)

Spawn a `workflow-reviewer`:
`Review node <node>: branch <b> at worktree <wt> (base <ref>). Scope <globs>.
Report REVIEW <node> verdict=approve|changes; for changes give a numbered list,
each` file:line — problem — required action `(one clause each). Log verdict with
--event review. Kept alive to re-review the delta only.`
Escalate to opus in the brief when the diff is complex or security-critical.

## Advisor / debugger brief

Spawn a `workflow-advisor` (kind:design) or `debugger`/`general-purpose` (kind:debug)
with the coder's question verbatim + the minimal code context from its `BLOCKED`.
Reply ADVICE back in one call, read-only; relay to the coder, then dismiss.
