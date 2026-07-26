---
name: orchestrate
description: Use when decomposing work across multiple subagents with isolated worktrees, independent review, safe merging, and durable run state in beads (bd).
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
   its terse result. Read only the control evidence needed to route a
   decision. Never open, hash, parse, or precompute target-scope
   content or independently verify the requested deliverable in the lead;
   those are node and reviewer work. Your own direct actions (only these):
   high-level decomposition, running `bd` and the bundled scripts
   (`scope-check.py`, `discover-agents.py`, `conflict-probe.sh`), and sending
   content-free doorbell wakes. A worker or hook failure is diagnosed through
   its durable evidence by a delegated node; never open hook, guard, or tool
   implementation in the lead to debug an actor. All other work must be
   delegated.
2. **Route by `references/roles.md`; cheapest capable model per role.**
   Escalate up only on hard cases. Never assign an expensive model to
   mechanical work.
3. **Subagents only — never agent-teams for parallel work.** Fan out via Agent
   tool background subagents (`subagent_type: domain-specialist`), addressed
   by their parent-visible runtime handles. Allocate every checkout through
   the `worktrunk-writer` contract.
   Decline the harness's suggestion to spawn teammates. Agent-teams are a
   Claude Code-only mechanism and are a rare gated exception (`references/teams.md`);
   unsure whether the trigger is met → use subagents.
4. **Every claim-holder and tool user runs in Worktrunk.** Each independently
   dispatched actor gets a prepared checkout; the bundled shepherd gets a
   dedicated integration checkout per repository. Record each assigned
   branch/path on its activation resource. Writers self-commit, push, and
   report their Worktrunk branch. Allocation and activation are separate:
   WAIT-only spawn, context acknowledgement, handle/context bind and stamp,
   then an exact `CLAIM {resource-id}` to the routing handle.
5. **Flat claim-holder tree.** Only you spawn claim-holding specialists,
   reviewers, advisors, researchers, scribes, and shepherds. A
   domain-specialist may spawn bounded throwaway implementation children in
   its prepared checkout; they never claim, manage worktrees, commit, push, or
   spawn another writer. Every other actor spawns nothing.
6. **Route content peer to peer.** A blocked specialist writes an escalation
   wisp; an advisor claims and answers that wisp. A reviewer writes FIX
   material on its review wisp. You create shells, wake actors, and observe
   state, but never relay questions, advice, review findings, or task briefs.
   A wake or recovery activation is only `CLAIM {bead-or-wisp-id}`.
7. **Comms protocol is mandatory.** Bundled role definitions carry the
   bead-as-brief and wisp protocol. Claude's skill-scoped `SubagentStart` hook
   reinforces the generic claim contract. Codex activations remain the same
   single CLAIM verb; do not paste a protocol block into an activation.
8. **Durable state, bounded processes.** Beads, wisps, and GitHub are the
   record. The bundled in-run `shepherd` owns this run's landing patrol and
   uses the dependency-owned `pr-shepherd` landing safeguards. The standalone
   `pr-shepherd` drains the repository-global queue across runs. Scribes drain
   ledger wisps on demand or at their timer boundary. No process or second
   graph is authoritative.

## Workflow

1. Check the prerequisites: `bd` (run state), `wt` (all local checkout
   lifecycle), and the package dependency's `worktrunk-writer` skill. Missing
   `bd` → stop; there is no fallback store. Missing `wt` or the writer contract
   → stop. No database yet → `bd init --stealth --prefix orc`. Create the run epic bead (metadata:
   run id, primary branch, base sha, artifacts dir) and the artifacts directory
   outside every worktree:
   `<primary>/.orchestration/run-<id>/artifacts/`; resolve it to an absolute
   path, create it, and read the epic metadata back before dispatch. A relative
   path or a path under any Worktrunk checkout is invalid. Gitignore it. The
   prompt hook creates `<primary>/.orchestration/.active-run` with
   `run_id=pending` before the first tool call. Preserve an existing run id
   during restart recovery; otherwise bind `pending` to this epic id with the
   active runtime's installed hook entry:
   `.claude/hooks/orchestrate/scripts/orchestrator-run-activate.py bind
   {epic-id}` or
   `.codex/hooks/orchestrate/scripts/orchestrator-run-activate.py bind
   {epic-id}`. Read the marker back before dispatch; a pending marker makes
   claim-holder allocation invalid. Put run identity and artifact paths on
   Beads; never broadcast them in activation prompts.
2. Plan & decompose yourself at high level; delegate deep planning (read-only
   `Plan`) or speccing (`speckit-*`) for work spanning >3 tasks with
   cross-cutting deps or an unfamiliar subsystem. Beads-managed external
   framework (SpecKit molecule) driving the work → its step beads ARE the run
   DAG; don't build a second graph. Otherwise: one child bead per task
   (label `orc-node`, disjoint `scope` globs in metadata), deps via
   `bd dep add`; `bd dep cycles` must stay clean. See
   `references/planning.md`.
   When a run has more than one dependent node, create one durable Beads swarm
   for the epic (`bd swarm create <epic>`), record its returned molecule handle
   on the epic metadata, and use `bd swarm validate <epic>` plus
   `bd swarm status <epic>` for health checks. The swarm is the DAG runtime;
   never recreate it in `graph.py`, JSON, or an in-memory ledger.
3. Run `scripts/discover-agents.py` to catalog agents (name/model/tools).
   Match task→agent via `references/roles.md`. Bundled claim-holder roles are
   `domain-specialist`, `researcher`, `reviewer`, `advisor`, `shepherd`, and
   `scribe`. Broad research uses the fan-out/fan-in route in `roles.md`.
4. Prepare one dedicated integration Worktrunk checkout and spawn one bundled
   `shepherd` patrol per GitHub repository for this run. It
   follows the shared `pr-shepherd` landing contract but keeps run-scoped
   lifecycle and cleanup ownership. The standalone `pr-shepherd` remains the
   repository-global recovery/drain actor; the sheepdog lease prevents both
   from owning the same repository concurrently. Create scribe query wisps
   only when a bounded status or ledger drain is needed.
5. Per ready node (`bd ready --label orc-node --parent <epic> --json`, then
   `scope-check.py --candidate <bead> --epic <epic>` per candidate): create
   the writer checkout through `worktrunk-writer prepare` without `--bead`.
   Write the complete BRIEF and stamp the returned anchors, stable actor, and
   lease on the unclaimed node, then read them back. Spawn with only the
   canonical WAIT bootstrap; do not put CLAIM in the Agent prompt. Record the
   parent-visible handle, require its exact `WAIT context={id}`
   acknowledgement, and bind both values. Stamp and read back
   `runtime_handle` and `runtime_context`, then send a separate exact
   `CLAIM {node-id}` message to `runtime_handle`. The role definition owns
   claim and validation.
   A BOUNCE invalidates that attempt: repair the envelope and redispatch from
   durable state; never continue or close the bounced actor by manual
   messages. See `references/spawn-brief.md`.
6. On `REPORTED`, create all review-wisp shells and merge-bead dependency
   edges before any reviewer starts. Give each tool-using reviewer its own
   Worktrunk checkout, stamp and bind the wisp, then activate it with exactly
   `CLAIM {review-wisp-id}`. Changes stay on the review wisp; wake the
   specialist with `CLAIM {same-node-id}` only after every dimension has a
   verdict. A blocked specialist similarly exchanges content with an advisor
   through an escalation wisp. The last approving reviewer closes the final
   wisp, swaps the review label, and makes the draft PR ready.
7. The run's shepherd claims ready merge beads, revalidates the exact PR head
   and CI through the shared landing safeguards, serializes landing with the
   merge slot, and either merges or creates an unassigned fix bead with bounce
   evidence. Content conflicts, failed CI, and stale heads return to the
   originating specialist through a node or fix-bead claim; the shepherd never
   edits or pushes. Dismiss actors only after terminal evidence and sweep
   every checkout through `worktree-sweep.sh`.
8. A dispute not settled by durable evidence gets a fresh read-only
   tiebreaker on an escalation wisp; its `ADVICE` is promoted before use. A
   product-intent question becomes an ASK wisp plus human gate. See
   `references/lifecycle.md`.
9. Close out: go/no-go gate — `bd dep cycles` clean and no `in_progress`/
   `blocked` node beads left under the epic (`bd list --label orc-node
   --parent {epic} --status in_progress,blocked`); activate a scribe query wisp
   for the end-of-run report; confirm all registered worktrees removed, then run
   `worktree-sweep.sh --prune <primary-repo-path>` and resolve every refused
   path before declaring cleanup complete. Clean run-local build artifacts and
   remove the active-run marker only after verifying it contains this run id.

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
