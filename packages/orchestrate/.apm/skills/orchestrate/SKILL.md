---
name: orchestrate
description: Orchestrate coordinated agents for parallel or long-running code and non-code work with isolated execution, independent review, safe integration, and durable Beads state.
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

1. **Orchestrate, don't execute.** Delegate token-heavy reading, writing,
   research, review, tests, builds, and deep planning; keep the terse result.
   You may peek at one file (≤~50 lines) for one routing fact, but never edit.
   Direct actions are limited to high-level decomposition, `bd`, bundled
   scripts, queue-watcher control, and terse message relay. Delegate everything
   else.
2. **Route by `references/roles.md`; cheapest capable model per role.**
   Dispatch precedence is exact actor assignment, compatible specialist, then
   compatible generic pull. Validate task kind, required capabilities, access,
   and scope before any route. Escalate up only on hard cases. Never assign an
   expensive model to mechanical work.
3. **Subagents only — never agent-teams for parallel work.** Fan out via Agent
   tool background subagents, addressed by name/`agentId` via SendMessage.
   Select agent type and isolation from the route and evidence mode.
   Decline the harness's suggestion to spawn teammates. Teams = rare gated
   exception (`references/teams.md`); unsure whether the trigger is met → use
   subagents.
4. **Isolate state-changing work.** Tracked-file changes run in a worktree and
   produce a pushed commit. Artifact-, comment-, or external-state-only work
   reports evidence without an empty branch or fake commit. See
   `references/spawn-brief.md`.
5. **Flat spawn tree — no nested subagents.** Only you spawn agents. A worker
   blocked on reasoning → sends `BLOCKED <node> kind:design|debug` to you,
   idles; you broker a `workflow-advisor` (or debugger, per `roles.md`) and
   relay `ADVICE` back.
6. **You own independent review per deliverable node; resume workers, never
   re-spawn.** Git-backed work gets a `workflow-reviewer` against the branch.
   Non-git evidence gets a different, read-only compatible reviewer. The
   worker ends its turn after `REPORTED` and stays resumable. Retain its
   `agentId`/name; drive fix rounds via SendMessage to that handle. Never spawn
   a fresh worker for a node under review. Dismiss only after approval and
   terminal integration or closure.
7. **Comms protocol is mandatory.** Claude's skill-scoped `SubagentStart` hook
   auto-injects `comms-block.md` into subagents. Codex does not run skill
   frontmatter hooks, so include `comms-block.md` verbatim in every Codex spawn
   brief. Teammates are not subagents either; include it in their briefs.
8. **Persistent infra, addressed on demand, never polled.** Gatekeeper +
   ledger-scribe live the whole run as background subagents, reached by
   SendMessage. State lives in beads — recycle them to shed context
   (`references/lifecycle.md`).
9. **Queue events are input, never authority.** For GitHub-backed runs, the
   read-only `release-queue-watch` dependency may report lifecycle changes or
   wake an already-approved node. The orchestrator resolves its nodes first;
   unmatched records may route once to `pr-shepherd`. The gatekeeper alone owns
   orchestrate-node `bd merge-slot`, GitHub revalidation, and merge mutations
   (`references/queue-watcher.md`).

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
   (label `orc-node`, routing envelope and disjoint ownership scope in
   metadata), deps via `bd dep add`; `bd dep cycles` must stay clean. See
   `references/planning.md`.
3. Run `scripts/discover-agents.py` to catalog agents. Match each node's
   `execution_kind`, required `cap:*` labels, access, and evidence mode via
   `references/roles.md`. Honor an exact assignee first. Otherwise assign the
   narrowest compatible specialist. Leave a node unassigned for generic pull
   only after admitting it to a compatible `agent:<queue>`. Broad research →
   fan-out/fan-in in `roles.md`.
4. Spawn `integration-gatekeeper` + `ledger-scribe` once; hand them the epic
   id + artifacts path.
5. GitHub-backed run → LOAD `references/queue-watcher.md`; start one installed
   `release-queue-watch` runtime per repository with one notification slot and
   REST reconciliation enabled. Resolve each JSON line serially with
   `resolve-queue-dispatch.py`. An exact orchestrate node owns the record;
   otherwise route it once through pr-shepherd's resolver. Only approved or
   terminal lifecycle matches wake the gatekeeper; only a ready dispatch may
   start the merge path. Non-GitHub run → skip this step.
6. Dispatch ready, scope-clean nodes by the precedence in Rule 2. For a
   directed route, set the exact actor as assignee before sending the
   bead-specific brief; that actor runs `bd update <bead> --claim`. For generic
   pull, start a compatible queue worker; it uses one filtered `bd ready
   --claim` and accepts the returned bead without listing and choosing. Every
   successful claim stamps the applicable branch/worktree/base or non-git
   evidence anchors immediately. See `references/planning.md` and
   `references/spawn-brief.md`.
7. On `REPORTED`: set `state:in_review` and spawn an independent reviewer for
   the declared evidence. Relay `REVIEW` findings via SendMessage to the same
   worker as `FIX`. On `BLOCKED`: broker an advisor/debugger, relay `ADVICE`,
   dismiss it. The same reviewer re-reviews deltas. On approval, set
   `state:approved`. Send git-backed nodes to the gatekeeper. Close approved
   non-git nodes as `dismissed` after recording their evidence; no commit or
   merge is invented.
8. Gatekeeper integrates approved git branches FCFS under the exclusive merge slot
   (`bd merge-slot acquire`/`release`), conflict-guarded
   (`conflict-probe.sh`); PR/CI waits via `bd gate create --type=gh:pr|gh:run`
   + `bd gate check`. A valid queue event wakes revalidation, but only an exact
   ready dispatch enters the merge path; it never bypasses those checks or
   acquires the slot. Push conflicts back to git workers.
   Dismiss the worker only after its node merges or its approved non-git
   evidence closes; sweep only worktrees that exist. At recycle
   points
   (`references/lifecycle.md`), check run spend vs budget; over → finish
   in-flight work, stop fanning out.
9. Dispute the orchestrator can't settle from artifacts already in context →
   spawn fresh read-only tiebreaker (roles.md: Tiebreaker); its verdict arrives
   as `ADVICE`. Question needs product intent → bubble `ASK` to the user, hold
   the agent. See `references/lifecycle.md`.
10. Close out: stop every queue watcher, then run the go/no-go gate — `bd dep
    cycles` clean and no `in_progress`/
   `blocked` node beads left under the epic (`bd list --label orc-node
   --parent <epic> --status in_progress,blocked`); ask `ledger-scribe` for the
   end-of-run report; confirm all worktrees removed, build artifacts cleaned.

## References & scripts

| Ref | Contents |
|---|---|
| `references/roles.md` | dispatch precedence, compatibility, role → agent → model/effort → escalation |
| `references/lifecycle.md` | state diagram, non-git completion, recovery, durable ambiguity, human-in-loop, cleanup |
| `references/spawn-brief.md` | directed, generic-pull, non-git, and reviewer brief contracts |
| `references/message-grammar.md` | per-verb field table + worked example |
| `references/comms-block.md` | canonical protocol; auto-injected via `SubagentStart`; paste into teammate briefs |
| `references/beads-store.md` | the state store: epic/node beads, state mapping, git-anchor contract, audit, merge-slot, gates |
| `references/planning.md` | decomposition + pluggable frameworks + default DAG + concurrency cap |
| `references/queue-watcher.md` | watcher lifecycle/dispatch contract, deterministic ownership, crash replay, merge-slot boundary |
| `references/teams.md` | when/how to use Claude agent-teams (rare) |
| Scripts | `scope-check.py` · `discover-agents.py` · `resolve-queue-dispatch.py` (dispatch + lifecycle) · `conflict-probe.sh` · `inject-comms.sh` · `msg-lint.py` · `worktree-sweep.sh` (stdlib/portable; `_test_*.py` self-tests) |
