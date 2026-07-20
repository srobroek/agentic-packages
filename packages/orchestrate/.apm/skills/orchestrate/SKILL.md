---
name: orchestrate
description: Orchestrate coordinated subagents for parallel or long-running implementation with isolated worktrees, independent review, safe merging, and durable run state in beads (bd).
x-lint:
  allow: [W6]
  reason: "the loaded skill must retain its core orchestration protocol while detailed mechanics remain in references"
hooks:
  SubagentStart:
    - hooks:
        - type: command
          command: '"$CLAUDE_PROJECT_DIR"/.claude/skills/orchestrate/scripts/inject-comms.sh'
---

# Orchestrate

Role: lead session / orchestrator.
- Decompose work, spawn cost-routed agents, broker independent review, gate
  merges, keep a reproducible record.
- Reasoning stays in agents; deterministic ops run via bundled scripts.
- All inter-agent messages: terse verb-tag grammar (`references/message-grammar.md`).
- Your context window is the run's scarcest, non-recoverable resource — spend
  it only on coordination, never on content.

## Core rules

1. **Orchestrate, don't execute.** Push every token-heavy action — reading
   source files, writing/editing code, research, diff review, running
   tests/builds, deep planning — to the cheapest capable subagent; keep only
   its terse result. You may directly peek a single file (≤~50 lines) to pick
   up one fact needed to route a decision; never edit directly; anything
   bigger is delegated. Your own direct actions (only these): high-level
   decomposition, running `bd` and the bundled scripts (`scope-check.py`,
   `discover-agents.py`, `conflict-probe.sh`), relaying terse messages. All
   other work must be delegated.
2. **Route by `references/roles.md`; cheapest capable model per role.**
   Escalate up only on hard cases. Never assign an expensive model to
   mechanical work.
3. **Subagents only — never agent-teams for parallel work.** Fan out via Agent
   tool background subagents (`subagent_type: workflow-coder`,
   `isolation:"worktree"`), addressed by name/`agentId` via SendMessage.
   Decline the harness's suggestion to spawn teammates. Teams = rare gated
   exception (`references/teams.md`); unsure whether the trigger is met → use
   subagents.
4. **Writers run in worktrees.** Implementation → `workflow-coder` subagent,
   `isolation:"worktree"`; it self-commits, pushes, reports branch + worktree
   path.
5. **Flat spawn tree — no nested subagents.** Only you spawn agents. Coder
   blocked on reasoning → sends `BLOCKED <node> kind:design|debug` to you,
   idles; you broker a `workflow-advisor` (or debugger, per `roles.md`) and
   relay `ADVICE` back.
6. **You own review per code node; resume coders, never re-spawn.** Per
   code-writing node: spawn a `workflow-reviewer` against the coder's branch.
   Coder ends its turn after `REPORTED` → becomes a resumable background
   subagent. Retain
   its `agentId`/name; drive fix rounds via SendMessage to that handle
   (auto-resumes with context + worktree). Never spawn a fresh coder for a
   node under review. Dismiss only on approval + merge.
7. **Comms protocol is mandatory.** Claude's skill-scoped `SubagentStart` hook
   auto-injects `comms-block.md` into subagents. Codex does not run skill
   frontmatter hooks, so include `comms-block.md` verbatim in every Codex spawn
   brief. Teammates are not subagents either; include it in their briefs.
8. **Persistent infra, addressed on demand, never polled.** Gatekeeper +
   ledger-scribe live the whole run as background subagents, reached by
   SendMessage. State lives in beads — recycle them to shed context
   (`references/lifecycle.md`).

## Workflow

1. Check the prerequisite: `bd` (beads CLI) on PATH — it is the run's state
   store (`references/beads-store.md`). Missing → stop, tell the user to
   install beads; there is no fallback store. No database yet → `bd init
   --stealth --prefix orc`. Create the run epic bead (metadata: run id,
   primary branch, base sha, artifacts dir) and the artifacts dir outside
   every worktree: `<primary>/.orchestration/run-<id>/artifacts/`; gitignore
   it; broadcast the epic id + artifacts path to every agent.
2. Plan & decompose yourself at high level; delegate deep planning (read-only
   `Plan`) or speccing (`speckit-*`) for work spanning >3 tasks with
   cross-cutting deps or an unfamiliar subsystem. Beads-managed external
   framework (SpecKit molecule) driving the work → its step beads ARE the run
   DAG; don't build a second graph. Otherwise: one child bead per task
   (label `orc-node`, disjoint `scope` globs in metadata), deps via
   `bd dep add`; `bd dep cycles` must stay clean. See
   `references/planning.md`.
3. Run `scripts/discover-agents.py` to catalog agents (name/model/tools).
   Match task→agent via `references/roles.md`. Bundle roles: `workflow-coder`,
   `workflow-reviewer`, `workflow-advisor`, `integration-gatekeeper`,
   `ledger-scribe`. Non-code roles → built-ins (`Explore`, `general-purpose`);
   broad research → fan-out/fan-in in `roles.md`.
4. Spawn `integration-gatekeeper` + `ledger-scribe` once; hand them the epic
   id + artifacts path.
5. Per ready node (`bd ready --label orc-node --parent <epic> --json`, then
   `scope-check.py --candidate <bead> --epic <epic>` per candidate): spawn
   background `workflow-coder` subagent (`subagent_type: workflow-coder`,
   `isolation:"worktree"`) with brief per `references/spawn-brief.md` (bead
   id, scope, base, epic id, artifacts path, protocol). The coder claims its
   bead atomically (`bd update <bead> --claim`) and stamps branch/worktree
   metadata — the resumable record. (teammates: see Rule 7). Agents record
   their own audit events + comments.
6. On `REPORTED`: set `state:in_review` and spawn `workflow-reviewer` against
   branch/worktree. Relay `REVIEW` findings via SendMessage to coder's
   `agentId` as `FIX` (resumes same coder; never a new one). On `BLOCKED`:
   spawn `workflow-advisor`/debugger, relay `ADVICE` back, dismiss it. Same
   reviewer re-reviews deltas. On `approve`: `bd set-state <bead>
   state=approved`, send `APPROVE <node>` to the gatekeeper — the merge
   handoff trigger.
7. Gatekeeper merges approved branches FCFS under the exclusive merge slot
   (`bd merge-slot acquire`/`release`), conflict-guarded
   (`conflict-probe.sh`); PR/CI waits via `bd gate create --type=gh:pr|gh:run`
   + `bd gate check`; pushes conflicts back to coders. Dismiss coder only
   after its node merges; sweep its worktree. At recycle points
   (`references/lifecycle.md`), check run spend vs budget; over → finish
   in-flight work, stop fanning out.
8. Dispute the orchestrator can't settle from artifacts already in context →
   spawn fresh read-only tiebreaker (roles.md: Tiebreaker); its verdict arrives as `ADVICE`. Question needs product intent →
   bubble `ASK` to the user, hold the agent. See `references/lifecycle.md`.
9. Close out: go/no-go gate — `bd dep cycles` clean and no `in_progress`/
   `blocked` node beads left under the epic (`bd list --label orc-node
   --parent <epic> --status in_progress,blocked`); ask `ledger-scribe` for the
   end-of-run report; confirm all worktrees removed, build artifacts cleaned.

## References & scripts

| Ref | Contents |
|---|---|
| `references/roles.md` | role → agent → model/effort → escalation; spawn authority |
| `references/lifecycle.md` | state diagram, persistence classes, resume, failure propagation, human-in-loop, cleanup |
| `references/spawn-brief.md` | required contents of every agent brief |
| `references/message-grammar.md` | per-verb field table + worked example |
| `references/comms-block.md` | canonical protocol; auto-injected via `SubagentStart`; paste into teammate briefs |
| `references/beads-store.md` | the state store: epic/node beads, state mapping, git-anchor contract, audit, merge-slot, gates |
| `references/planning.md` | decomposition + pluggable frameworks + default DAG + concurrency cap |
| `references/teams.md` | when/how to use Claude agent-teams (rare) |
| Scripts | `scope-check.py` · `discover-agents.py` · `conflict-probe.sh` ·
  `inject-comms.sh` · `msg-lint.py` · `worktree-sweep.sh` (stdlib/portable;
  `_test_*.py` self-tests) |
