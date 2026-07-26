# Feature Specification: Bead-as-Brief Orchestration Contracts

**Feature Branch**: `002-bead-as-brief`

**Created**: 2026-07-24

**Status**: Draft

**Input**: User description: "bead-as-brief orchestrate v2: all task data lives on node beads (metadata schema + BRIEF comment), spawn prompts carry only CLAIM verbs; claim⟺contract enforced by per-agent SubagentStop rules engine; actor tier taxonomy; wisps for ephemeral coordination; graph links for provenance; needs-review:/reviewed: label flow with dep-graph verdict aggregation; draft-PR landing via pr-shepherd only; gates for human approval, scribe timer, CI; SendMessage wake with respawn fallback; planner as high-tier node separate from routing orchestrator. Full accepted design in specs/002-bead-as-brief/design.md (bead orc-3v0)"

**Design authority**: The accepted architecture lives in [design.md](design.md) (bead orc-3v0). This spec defines testable behavior and does not restate the design.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Crash-resumable task handoff (Priority: P1)

An orchestrator operator runs a multi-agent implementation. Every task's instructions, scope, and progress live on its bead, so any agent that dies mid-task — or any wake that silently becomes a respawn — recovers by reading the bead and its work-log thread. No task instruction ever exists only in a prompt.

**Why this priority**: This is the foundation every other story builds on; without bead-resident briefs, contracts and wake fallbacks have nothing to validate or recover from.

**Independent Test**: Create a node bead with BRIEF and metadata, allocate an
agent with the canonical WAIT bootstrap, bind its runtime, activate it with
only `CLAIM <bead-id>`, kill it mid-task, and verify a replacement continues
from the last checkpoint without information from the first agent's prompt.

**Acceptance Scenarios**:

1. **Given** a node bead with BRIEF comment and complete metadata, **When** an
   agent receives the canonical WAIT bootstrap and a later exact CLAIM
   activation, **Then** it performs the task without task data in either
   message.
2. **Given** an agent killed mid-task after writing checkpoints to its work-log wisp, **When** a replacement claims the same bead, **Then** it resumes from the last checkpoint and delivers the node.
3. **Given** an orchestrator whose agent handle expired, **When** it attempts a wake, **Then** the respawn path recovers the node with no loss of durable state.

---

### User Story 2 - Contract enforcement at agent exit (Priority: P1)

An agent that claims a bead cannot exit cleanly until its role's completion checklist is satisfied, and cannot write bead properties outside its role's authority. An agent that claims nothing is never touched by any contract. A stuck agent always has a legitimate failure exit, and after three blocked exits the bead bounces back to the orchestrator with diagnostic evidence.

**Why this priority**: Enforcement is what turns the brief convention into a guarantee; without it agents can exit having written nothing durable, which is the failure mode that motivated the redesign.

**Independent Test**: Spawn a contract-bound agent, have it attempt to stop without pushing its branch, and observe the structured block; then set `state=failed` with a FAILED comment and observe the unconditional exit.

**Acceptance Scenarios**:

1. **Given** a claiming coder missing a required delivery field, **When** it attempts to stop, **Then** the stop is blocked with a structured, failure-specific report naming only the failed checks.
2. **Given** an agent whose bead is in `failed` state with a FAILED comment, **When** it stops, **Then** the exit is allowed regardless of other checklist items.
3. **Given** three consecutive blocked stop attempts, **When** the third block would fire, **Then** the exit is force-allowed, a BOUNCE comment records the accumulated evidence, the bead is unassigned, and both counters reset.
4. **Given** any agent with no claim, **When** it stops, **Then** no contract check runs and no block occurs.
5. **Given** an unlisted agent type that claims a bead, **When** it stops, **Then** the generic fallback contract applies.
6. **Given** the orchestrator session, **When** it attempts to claim any bead, **Then** the claim is denied.

---

### User Story 3 - Multi-dimension review with graph aggregation (Priority: P2)

A node requiring several review lenses (code, security, QA) is reviewed by one fresh reviewer per dimension. Verdict aggregation is structural: the merge bead becomes ready exactly when the last review wisp closes; no actor counts dimensions. Review continuity is also visible on the pull request itself.

**Why this priority**: Review integrity gates landing; it depends on the contract layer (P1) but landing (P3) depends on it.

**Independent Test**: Label a node with two review dimensions, report it, verify two wisp shells block the merge bead, approve one dimension and verify the merge bead stays blocked, approve the second and verify it becomes ready with the PR undrafted.

**Acceptance Scenarios**:

1. **Given** a reported node labeled `needs-review:code` and `needs-review:security`, **When** the orchestrator processes it, **Then** two review-wisp shells exist, each blocking the merge bead, before any reviewer spawns.
2. **Given** one dimension approved and one open, **When** readiness is evaluated, **Then** the merge bead is not ready.
3. **Given** the last open review wisp closing on approval, **When** the close lands, **Then** the merge bead is ready and the closing reviewer promotes the PR from draft.
4. **Given** a changes verdict, **When** all dimensions' round verdicts are in, **Then** the coder is woken once with the union of all open dimensions' fix items.
5. **Given** a fix diff touching an approved dimension's trigger scope, **When** the orchestrator evaluates the diff, **Then** that dimension's label reverts and a fresh shell is created.
6. **Given** any verdict, **When** the reviewer records it, **Then** a matching GitHub review (approve or request-changes) exists on the PR.

---

### User Story 4 - Single landing path via pr-shepherd (Priority: P3)

All merges — node branches into an integration base, integration branches into main, external PRs — flow through one landing path: draft PRs, merge beads, the per-repo shepherd, and the merge slot. The shepherd manages PR state and audit only; it never edits content.

**Why this priority**: Consolidating landing removes a whole agent (integration-gatekeeper) and its drift risk, but only pays off once contracts and review exist.

**Independent Test**: Open a draft PR with a merge bead from an agent, verify the shepherd ignores it while draft, undraft it, and verify the shepherd probes, acquires the slot, merges, stamps evidence, and closes the merge bead.

**Acceptance Scenarios**:

1. **Given** an agent completing a git-kind node, **When** it opens the PR, **Then** the PR is draft and an unassigned merge bead exists with the PR body carrying its id.
2. **Given** a draft PR with an open merge bead, **When** the shepherd patrols, **Then** it does not claim, gate, bounce, merge, or close it.
3. **Given** a content defect on a PR, **When** the shepherd detects it, **Then** it files a fix bead, parks the merge bead behind it, releases its claim, and pushes no commits.
4. **Given** two shepherd starts against one repo, **When** the second starts, **Then** it fails to take the repo lease and exits.

---

### User Story 5 - Ephemeral coordination without context waste (Priority: P2)

Operational chatter — checkpoints, advice threads, review working notes, ledger events, CI probes — rides ephemeral wisps that burn after use, so durable bead threads stay short (~5 comments for a healthy node) and every future reader pays only for evidence, not process noise. Blocked agents never idle live; they checkpoint and exit (or bounded-poll on runtimes without resume), and the orchestrator wakes the counterpart when the answer lands.

**Why this priority**: Context economy is the design's running cost; it makes long runs affordable but the system functions (expensively) without it.

**Independent Test**: Run a coder→advisor exchange over an escalation wisp, verify no message content passes through the orchestrator, and verify the wisp burns at node close leaving only a one-line summary on the node.

**Acceptance Scenarios**:

1. **Given** a blocked coder, **When** it raises a question, **Then** the question lives on an escalation wisp linked to the node, the advisor answers on the wisp, and the orchestrator relays no content.
2. **Given** a closed node, **When** cleanup runs, **Then** its work-log and escalation wisps are burned and no dependency edge points at a purged bead.
3. **Given** ledger events from multiple actors, **When** the scribe's timer gate expires, **Then** the scribe drains all open ledger wisps in one batch and folds them into the epic run record.
4. **Given** a subagent needing human approval, **When** it raises ASK, **Then** a human gate blocks the node and the node leaves the ready frontier until resolved.

---

### Edge Cases

- Wake attempt on a dead handle (compaction, overnight gap) → respawn from bead; must be loss-free.
- Reviewer approves while a second dimension's shell was added mid-round (label added by a T1 actor) → shell set is re-read at round barrier; late labels create shells for the next round, never race the current one.
- Two "last" reviewers close simultaneously → both promotion attempts are idempotent; no double-merge (merge slot serializes).
- Open wisp untouched for 24h (bd flags as abandoned) → claiming actor's activity or explicit touch keeps live wisps fresh; stale sheepdog is the dead-shepherd signal, not an error.
- `stop_attempts` reaching the cap on a bead whose failure is environmental (CI down) → BOUNCE evidence lets the orchestrator distinguish agent failure from world failure before respawning.
- Repo with dismiss-stale-approvals branch protection → all dimensions retrigger on any fix, keeping bead state and PR state aligned.
- Runtime without SendMessage (Codex, or Claude without the agent-teams flag) → every mechanism still functions via fresh-per-node spawns; only warm-context optimizations disappear.
- Child agent attempting a bead claim → universal contract net binds it; briefs forbid it; claim-holders come only from the orchestrator.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Node beads MUST carry all task data (metadata schema + BRIEF
  comment) sufficient for a fresh agent to execute the node after an exact
  CLAIM activation.
- **FR-002**: Claim-holder allocation prompts MUST contain only the canonical
  WAIT bootstrap with the resource id and optional checkout. Activation
  messages MUST contain only `CLAIM <resource-id>` or
  `CLAIM queue:<filter>`. Neither message may contain task data.
- **FR-003**: Every agent holding a durable-bead claim MUST be bound by its role's completion checklist and authority matrix at stop time; agents holding no claim MUST be exempt from all bead contracts.
- **FR-004**: Role contracts MUST be declared as data (per-agent rules files) evaluated by one shared evaluator; the prose contract in each agent definition MUST be generated from the same rules file at compile time.
- **FR-005**: Contract blocks MUST report structured, failure-specific diagnostics without remediation text; `state=failed` plus a FAILED/BLOCKED comment MUST be an unconditional exit; the third blocked stop MUST bounce (force-allow, BOUNCE evidence, unassign, counter reset in one act).
- **FR-006**: The orchestrator MUST never claim any bead (hook-denied, run-marker-scoped) and MUST never relay message content between actors.
- **FR-007**: An actor MUST hold at most one durable-bead claim at a time; wisp claims are exempt; every actor MUST hold zero claims of any kind at exit.
- **FR-008**: Ephemeral coordination (checkpoints, advice, review notes, ledger events, probes, leases) MUST ride typed wisps per the design doc's TTL mapping; durable evidence MUST stay on beads; no rule-engine-checked datum may live on a wisp except wisp open/closed state.
- **FR-009**: Review dimensions MUST be declared as `needs-review:<dim>` labels; the orchestrator MUST create all review-wisp shells and merge-bead dep edges atomically before spawning any reviewer; merge-bead readiness MUST derive solely from the dependency graph.
- **FR-010**: Every review verdict MUST produce a GitHub review on the PR; approval MUST atomically close the wisp and swap the dimension label; the closing reviewer that unblocks the merge bead MUST promote the PR from draft.
- **FR-011**: All landings MUST flow through draft PRs, merge beads, and the per-repo shepherd; the shepherd MUST NOT modify PR content; any agent opening a PR MUST first create its merge bead and dep edges.
- **FR-012**: Human approvals, scribe scheduling, and CI waits MUST use native bead gates (human/timer/gh:run/gh:pr), ticked by the shepherd patrol and orchestrator wakes; a gh:pr gate MUST never block a merge bead.
- **FR-013**: Agent wake MUST attempt resume where the runtime supports it and MUST fall back to respawn-from-bead losslessly; the fleet MUST run degraded (fresh-per-node) on runtimes without resume.
- **FR-014**: Planning MUST be a high-tier node distinct from the routing orchestrator; the router MUST NOT redesign the DAG; domain specialists MUST be one definition parameterized by domain bead, skill hints, and compiled effort variants.
- **FR-015**: The fleet MUST converge to the design doc's roster: `domain-specialist` added; `workflow-coder`, `workflow-worker`, `workflow-pull-worker`, `integration-gatekeeper` removed; pr-shepherd amendments (fix-bead routing, content read-only, sheepdog lease) applied.
- **FR-016**: The wisp/link/label/gate doctrine MUST be published in the beads package steering as the cross-package source; orchestrate and speckit (orc-pyq) MUST reference it rather than restate it.

### Key Entities

- **Node bead**: One unit of run work; carries metadata schema, BRIEF, verdict lines, evidence; the sole durable task record.
- **Merge bead**: One PR's landing record; queue entry for the shepherd; blocked by review wisps and fix beads.
- **Wisp**: Ephemeral bead (typed TTL class); carries chatter, threads, leases; burns after use; claimable (advisor/reviewer activation).
- **Rules file**: Per-agent declarative contract (completion, authority, escape, pause); single source for hook evaluation and generated definition prose.
- **Domain bead**: Persistent specialist's identity and standing brief; children of the run epic; nodes link to it.
- **Gate**: Native bd blocking condition (human/timer/gh:run/gh:pr) parking beads outside the ready frontier.
- **Label**: Routing and review-state declaration (`agent:*`, `needs-review:*`, `reviewed:*`); never load-bearing for merge safety.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An orchestrate run killed at any point resumes from bead state alone with zero lost durable decisions, demonstrated across at least one overnight gap.
- **SC-002**: 100% of contract-bound agents that exit cleanly leave their bead checklist-complete or explicitly failed/bounced — no silent empty exits — measured over a full multi-node run.
- **SC-003**: A healthy node's durable thread is ≤ 6 comments at close (BRIEF, REPORTED, verdict lines, closing summary); all other traffic demonstrably rides wisps burned during run cleanup.
- **SC-004**: No landing occurs without every declared review dimension approved, across a run including at least one multi-dimension node and one scope-retrigger.
- **SC-005**: The orchestrator's own context at run end contains no relayed task content — spot-checked by transcript review — and routine routing runs on the design doc's routing tier.
- **SC-006**: The same run definition completes on a resume-capable runtime and (fresh-per-node) on a non-resume runtime with identical durable outcomes.
- **SC-007**: Agent definition count in the orchestrate package decreases by three (four removed, one added) with no orphaned references in skills, docs, or steering.

## Assumptions

- bd ≥ 1.1.0 with wisps, gates, graph links, merge slots, and label filtering as verified against the installed binary and beads source during design.
- `replies-to` linking may require the orchestrator-mail path rather than `bd dep add`; `relates-to` is the accepted fallback (design doc records this).
- Claude Code ≥ 2.1.198; resume features gate on `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` (run-start capability probe, not assumed).
- Codex hook enforcement is defense-in-depth (partial shell interception); the SubagentStop checklist is the cross-runtime backstop.
- Existing pr-shepherd landing contract (probe/claim/slot/release) remains the landing substrate; this feature amends, not replaces, it.
- Speckit formula adoption of the doctrine is scoped separately (bead orc-pyq) and depends on the beads-steering doctrine section landing first.
