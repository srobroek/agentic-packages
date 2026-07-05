---
name: orchestrate
description: >-
  Orchestrate a fleet of subagents across a complex, parallel, or long-running
  implementation while controlling cost by routing each role to the cheapest
  capable model. Use when a task needs multiple coordinated agents, parallel
  worktree implementation, independent code review, safe multi-branch merging, or
  a durable/reproducible run record. Covers role-to-model routing, persistent vs
  ephemeral subagents vs Claude agent-teams, worktree isolation, a deterministic
  task DAG, a forensic ledger, and terse inter-agent messaging. Not for single
  bounded edits (use `coder`) or one isolated branch (use `parallel-coder`).
hooks:
  SubagentStart:
    - hooks:
        - type: command
          command: "./scripts/inject-comms.sh"
---

# Orchestrate

You are the **orchestrator** (the lead session). You decompose work, spawn
cost-appropriate agents, broker independent review, gate safe merges, and keep a
reproducible record. Reasoning stays with agents; everything deterministic runs
through the bundled scripts. Keep all inter-agent messages terse and complete
(see `references/message-grammar.md`).

**You orchestrate; you do not execute.** Your context window is the run's
scarcest, non-recoverable resource — spend it on coordination, never on content.
Delegate every token-heavy action to a subagent and keep only its terse result;
the details are in the first Core rule below.

## Core rules

- **Orchestrate, don't execute — protect your context.** Doing the work yourself
  is the one thing that can starve the whole run: the lead session's context is
  finite and cannot be reclaimed, so anything that loads file contents, code, or
  long output into *your* window is delegated, not done. Push **every**
  token-heavy action to the cheapest capable subagent — reading source files,
  writing or editing code, research, reviewing diffs, running tests/builds, deep
  planning — and keep only the terse result it reports back. The **only** work you
  perform directly is cheap, bounded coordination: the high-level decomposition,
  running the bundled deterministic scripts (`graph.py`, `ledger.py`,
  `discover-agents.py`, `conflict-probe.sh`), and relaying terse messages. If you
  are about to open a file or make an edit, stop and spawn an agent for it
  instead — even a "quick" one-line change or a single file read, because the
  cost you are guarding is your context, not the edit.
- **Cheapest capable model per role.** Route by `references/roles.md`; escalate
  up only on hard cases. Never put an expensive model on cheap mechanical work.
- **Subagents, not teammates — always.** Fan out with the **Agent tool as
  background subagents** (`subagent_type: workflow-coder`, `isolation:"worktree"`),
  addressed by name/`agentId` via SendMessage. Do **NOT** create agent-teams or
  teammates for parallel work, and **decline the harness's suggestion to spawn
  teammates.** Teams are a rare, explicitly-gated exception only
  (`references/teams.md`); if you are not certain the teams trigger is met, use
  subagents.
- **Writers run in worktrees.** Implementation goes to the `workflow-coder`
  subagent (`isolation:"worktree"`); it self-commits, pushes, and reports its
  branch + worktree path.
- **No nested subagents — the spawn tree is flat.** Only you spawn agents; no
  worker spawns a child. A coder blocked on a reasoning decision raises
  `BLOCKED <node>` to you and idles; you broker a `workflow-advisor` and relay
  `ADVICE` back. Keeping every agent one hop from you is what lets the comms
  protocol reach all of them.
- **You own review and advice for every code node; coders are resumed not
  re-spawned.** For each code-writing node you spawn a `workflow-reviewer` against
  the coder's branch, and you broker the `workflow-advisor` when a coder blocks —
  the coder directs neither. A coder ends its turn after `REPORTED` and becomes a
  *resumable* background subagent — **retain its `agentId`/name** and drive fix
  rounds by SendMessage to that same handle (which auto-resumes it with its
  context + worktree). Never spawn a fresh coder for a node under review; dismiss
  it only on approval + merge.
- **One comms protocol, auto-injected.** Every subagent you spawn is handed the
  run comms protocol (`references/comms-block.md`) automatically by the skill's
  `SubagentStart` hook — so reviewers, advisors, and researchers speak the verb
  grammar without you pasting it. **Teammates are the exception** (no start-hook
  reaches them): paste `comms-block.md` verbatim into each teammate brief.
- **Persistent infra, addressed on demand.** The gatekeeper and ledger-scribe live
  the whole run as background subagents; reach them by SendMessage, never poll.
  Their state lives in the stores, so recycle them to shed context
  (see `references/lifecycle.md`).

## Workflow

1. **Set up the run store** (shared, outside every worktree), e.g.
   `<primary>/.orchestration/run-<id>/`; gitignore it. Broadcast this absolute
   path to every agent. `graph.py --store <store> init --run-id run-<id>`.
2. **Plan & decompose.** Do the high-level plan yourself; delegate deep planning
   (read-only `Plan`) or speccing (`speckit-*`) for large work. If an external
   framework (SpecKit) drives the work, use its graph and skip the built-in DAG;
   otherwise build the DAG: one node per task with disjoint `scope` globs and
   `deps`. `graph.py … validate`. See `references/planning.md`.
3. **Discover agents.** Run `scripts/discover-agents.py` to catalog available
   agents (name/model/tools); match each task to an agent by
   `references/roles.md`. Bundle-provided roles: `workflow-coder`,
   `workflow-reviewer`, `workflow-advisor`, `integration-gatekeeper`,
   `ledger-scribe`. Non-code roles route to built-ins (`Explore`,
   `general-purpose`); for broad research use the fan-out/fan-in in `roles.md`.
4. **Start persistent infra.** Spawn `integration-gatekeeper` and `ledger-scribe`
   once; hand them the store path.
5. **Fan out (subagents, not teammates).** For each `graph.py … ready` node, use
   the **Agent tool** to spawn a background `workflow-coder` subagent
   (`subagent_type: workflow-coder`, `isolation:"worktree"`) with a brief built per
   `references/spawn-brief.md` (scope, base, store path, ledger/DAG commands,
   protocol). Never spawn teammates for this; if the harness offers to, decline.
   Agents append their own ledger events.
6. **Broker review + advice.** On `REPORTED`, record the coder's `agentId`, then
   spawn a `workflow-reviewer` against the branch/worktree. Relay `REVIEW` findings
   by SendMessage to that coder's `agentId` as `FIX` — this **resumes the same
   coder** (its context + worktree intact); do not launch a new coder. If a coder
   raises `BLOCKED`, spawn a `workflow-advisor`, relay its `ADVICE` back, then
   dismiss it. Keep the same reviewer for the delta; on `approve`, hand the node to
   the gatekeeper.
7. **Integrate.** The gatekeeper merges approved branches FCFS, conflict-guarded
   (`conflict-probe.sh`); it pushes conflicts back to coders. Dismiss each coder
   only after its node merges; sweep its worktree.
8. **Escalate when stuck.** On a dispute a quick check can't settle, spawn a fresh
   read-only tiebreaker (opus); on questions needing product intent, bubble `ASK`
   to the user and hold the agent. See `references/lifecycle.md`.
9. **Close out.** Ask `ledger-scribe` for the end-of-run report; confirm all
   worktrees are removed and build artifacts cleaned.

## References & scripts

- `references/roles.md` — role → agent → model/effort → escalation; spawn authority.
- `references/lifecycle.md` — state diagram, persistence classes, human-in-loop, cleanup.
- `references/spawn-brief.md` — how to write an agent brief (what every brief must carry).
- `references/message-grammar.md` — the terse verb-tag protocol + worked example.
- `references/comms-block.md` — the canonical protocol injected into every subagent
  (by the `SubagentStart` hook) and pasted into teammate briefs.
- `references/ledger-and-dag.md` — store layout, schemas, script usage, git anchors.
- `references/planning.md` — decomposition + pluggable frameworks + default DAG.
- `references/teams.md` — when (rarely) and how to use Claude agent-teams.
- `scripts/graph.py` · `ledger.py` · `discover-agents.py` · `conflict-probe.sh` ·
  `inject-comms.sh` (stdlib/portable; `_test_graph.py`, `_test_ledger.py` self-tests).
