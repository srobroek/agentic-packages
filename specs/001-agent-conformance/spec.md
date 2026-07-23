# Feature Specification: Agent Regression Harness — Contract-Conformance Tests for Shipped Agents

**Feature Branch**: `001-agent-conformance`

**Created**: 2026-07-24

**Status**: Draft

**Input**: User description: "Agent regression harness: contract-conformance tests for shipped agents. The repo ships ~34 production agent definitions (.apm/agents/*.agent.md across packages) with zero behavioral tests. Build a harness that feeds canned task fixtures to each agent and asserts contract conformance deterministically: first-line verdict format (regex/enum), word caps, no-reprint rules, output-section presence. LLM-in-the-loop by design — run nightly or pre-release, not per-PR. Prior art: wshobson plugin-eval is authoring-quality scoring, orthogonal; its static checks already ported to write-agentic lint."

## Context

The repository ships 34 production agent definitions (`.apm/agents/*.agent.md`
across 13 packages). Each declares an output contract in its body: a
first-line verdict format (CAPS enum like `VERDICT: APPROVE|CHANGES|ESCALATE`
or a structured line like `LINT-GUARD <node> verdict=PASS|WARN|BLOCK items=<N>`),
word caps (fixed, dual clean/with-findings, or explicitly uncapped),
no-reprint rules (never reprint code, diffs, file contents, or the caller's
claim), and conditional sections. Today nothing verifies that an agent, when
actually run against a task, honors its own contract. The write-agentic linter
checks that a contract is *declared*; nothing checks that it is *obeyed*.
Contract violations (verdict drift, cap blowouts, fixture reprints) surface
only when a downstream orchestrator misparses a reply in production.

This feature adds a behavioral regression harness: canned task fixtures are
fed to each shipped agent, the live reply is captured, and conformance to the
declared contract is asserted deterministically. The LLM call is the only
nondeterministic element; every assertion on the captured reply is pure and
reproducible.

## Clarifications

### Session 2026-07-24

- Q: Run each agent with its pinned model/effort, or one cheap model for cost? → A: Pinned models — the regression under guard is the shipped configuration; a scoped iteration run may override the model explicitly, but fleet/release sweeps always use the pins. *(auto-resolved: recommended default, user unavailable)*
- Q: How does the unattended run ship in v1? → A: Scheduled CI (nightly cron) plus manual dispatch, never a required PR check; requires an API-key secret in the CI environment. *(auto-resolved: recommended default, user unavailable)*
- Q: Where does the harness live? → A: A new self-contained package (`packages/agent-conformance`), versioned and released like the other packages, reading other packages' agent sources read-only at run time. *(auto-resolved: recommended default, user unavailable)*

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pre-release conformance sweep (Priority: P1)

A maintainer about to cut a release runs the full conformance suite locally
with one command. Every shipped agent is exercised against its fixture(s); the
maintainer gets a per-agent pass/fail/flaky report and a stored artifact of
each non-passing reply, and can decide whether the release proceeds.

**Why this priority**: This is the core gap — 34 agents, zero behavioral
tests. A single runnable sweep with trustworthy verdicts is the MVP; every
other story builds on it.

**Independent Test**: Run the suite command on a clean checkout with
credentials available. Verify it discovers all shipped agents, executes each
fixture, and emits a report where every agent appears exactly once with a
verdict of PASS, FLAKY, FAIL, or SKIP (with reason).

**Acceptance Scenarios**:

1. **Given** a checkout where all agents honor their contracts, **When** the
   maintainer runs the suite, **Then** the report lists every shipped agent
   with PASS (or SKIP with a documented reason) and the process exits zero.
2. **Given** one agent whose live reply violates its first-line verdict
   format, **When** the suite runs, **Then** that agent is reported FAIL with
   the violated assertion named, the offending reply is persisted as an
   artifact, and the process exits non-zero.
3. **Given** an agent whose reply fails once but passes on automatic retry,
   **When** the suite completes, **Then** the agent is reported FLAKY
   (distinct from PASS), and the exit code treats FLAKY as configurable
   (default: non-fatal, reported prominently).

---

### User Story 2 - Coverage completeness is enforced deterministically (Priority: P2)

A contributor adds a new agent package (or renames an agent) without adding a
conformance case. A deterministic, LLM-free check — runnable per-PR — fails
and names the uncovered agent, so coverage cannot silently erode.

**Why this priority**: Without a coverage gate the suite decays as the fleet
grows; the gate is cheap (no LLM) and protects the P1 investment.

**Independent Test**: Delete one fixture mapping and run the coverage check;
it must fail naming exactly that agent. Restore it; the check passes.

**Acceptance Scenarios**:

1. **Given** every shipped agent has at least one fixture or an explicit skip
   entry with a reason, **When** the coverage check runs, **Then** it passes.
2. **Given** a newly added `.agent.md` with no fixture and no skip entry,
   **When** the coverage check runs, **Then** it fails and names the agent.
3. **Given** a skip entry pointing at an agent that no longer exists, **When**
   the coverage check runs, **Then** it fails and names the stale entry.

---

### User Story 3 - Single-agent iteration loop (Priority: P3)

An agent author editing one agent's prompt runs only that agent's conformance
case(s) and gets a verdict in a tight loop, without paying for the full-fleet
sweep.

**Why this priority**: Makes the harness a daily authoring tool, not just a
release gate; increases the chance fixtures stay maintained.

**Independent Test**: Run the suite scoped to a single agent name; only that
agent's fixtures execute; the report contains only that agent.

**Acceptance Scenarios**:

1. **Given** the suite invoked with a single agent filter, **When** it runs,
   **Then** only the selected agent's fixtures execute and the per-agent
   report is produced for it alone.

---

### User Story 4 - Scheduled unattended run (Priority: P4)

The suite runs on a schedule (nightly or pre-release automation) without a
human present, publishes its report where maintainers will see it, and fails
loudly on regressions without blocking unrelated PR merges.

**Why this priority**: The bead explicitly scopes this as
nightly/pre-release, not per-PR; automation is valuable but only after the
local runner (P1) is trustworthy.

**Independent Test**: Trigger the scheduled job manually; verify it completes,
publishes the report artifact, and its failure status is visible without
appearing as a required check on any PR.

**Acceptance Scenarios**:

1. **Given** credentials configured for unattended use, **When** the scheduled
   run executes, **Then** the same report as the local run is produced and
   persisted, and a regression sets the run's status to failed.
2. **Given** credentials are absent, **When** the scheduled run starts,
   **Then** it fails fast with an explicit configuration message rather than
   reporting agents as failing.

---

### Edge Cases

- **Uncapped agents** (e.g., agents whose contract says `CAP uncapped`):
  word-cap assertions are skipped for those cases; all other assertions
  (first line, no-reprint, sections) still apply.
- **Dual caps** (clean vs with-findings): the fixture declares which regime it
  drives the agent into, and the matching cap is asserted.
- **Environment-dependent agents** (orchestrate workers that require a live
  beads database, git worktrees, or an assigned node): fixtures provide a
  minimal stubbed environment; where a faithful stub is not feasible, the
  agent carries an explicit skip entry with a reason, which the coverage
  check accepts and the report surfaces.
- **Agents whose contract is a written file, not only a reply** (e.g., a
  verification agent that must write a report file): the fixture asserts the
  file's presence and its machine-parseable verdict lines in addition to the
  chat reply.
- **LLM nondeterminism**: a failing case is retried a bounded number of times;
  pass-on-retry is reported FLAKY, never silently promoted to PASS.
- **Contract drift**: an agent's declared contract changes (new verdict enum,
  new cap) but its fixture assertions still encode the old contract. The
  harness must fail visibly in this situation rather than green-wash: the
  assertions live with the fixture, and a deterministic consistency check
  compares the fixture's declared first-line pattern and caps against the
  agent source and fails on mismatch.
- **Runaway output**: a reply that never terminates or exceeds a hard byte
  budget is truncated, the case fails with a timeout/size verdict, and the
  suite continues with remaining agents.
- **Partial fleet run interrupted mid-sweep**: already-captured results are
  persisted; re-running resumes or restarts cleanly without corrupting the
  report.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST discover every shipped agent definition
  (`packages/*/.apm/agents/*.agent.md`) automatically; discovery MUST NOT
  rely on a hand-maintained list of agent names.
- **FR-002**: Every discovered agent MUST be associated with at least one
  conformance case (fixture + assertion set) or an explicit skip entry with a
  human-readable reason; a deterministic coverage check MUST fail otherwise.
- **FR-003**: A conformance case MUST supply a canned task fixture (the
  task-shaped input the parent would send) and MUST execute the agent's
  actual shipped definition — same system prompt content, same pinned
  model/effort — capturing the complete reply.
- **FR-004**: The system MUST assert, deterministically and reproducibly on
  the captured reply: (a) first-line verdict conformance via regex/enum
  derived from the agent's declared contract; (b) word-cap conformance for
  the regime the fixture drives (clean vs with-findings), skipped only for
  contracts that declare uncapped; (c) no-reprint conformance — the reply
  contains no verbatim run of fixture-supplied content beyond a small
  threshold; (d) presence/absence of declared output sections, including
  conditional sections that must be absent when empty.
- **FR-005**: The system MUST support cases that additionally assert on
  side-effect artifacts an agent's contract requires (e.g., a report file
  with machine-parseable verdict lines).
- **FR-006**: Each case verdict MUST be one of PASS, FLAKY (failed then
  passed within a bounded retry budget), FAIL (all attempts failed), ERROR
  (infrastructure/credential failure, not an agent failure), or SKIP (with
  reason); the distinction between FAIL and ERROR MUST be preserved in the
  report and exit status.
- **FR-007**: The full-fleet run MUST emit a single machine-readable report
  plus a human-readable summary, listing every agent exactly once, and MUST
  persist the raw reply of every non-PASS case as an inspectable artifact.
- **FR-008**: The runner MUST support scoping to a single agent or a single
  package for iteration, producing the same per-case verdicts as the fleet
  run; scoped runs MAY override the model explicitly, and any override MUST
  be recorded in the report so an overridden verdict is never mistaken for a
  shipped-configuration verdict.
- **FR-009**: The LLM-in-the-loop suite MUST NOT run as a required per-PR
  check; the deterministic coverage/consistency checks alone MAY run per-PR.
- **FR-010**: The suite MUST be runnable unattended via repository automation
  on a nightly schedule and on manual dispatch, failing fast with an explicit
  configuration error when credentials are unavailable, and publishing the
  same report artifacts as a local run; the automated run MUST NOT be wired
  as a required pull-request status check.
- **FR-011**: A deterministic consistency check MUST verify each case's
  encoded expectations (first-line pattern, caps) against the agent source's
  declared contract and fail on drift, so a contract edit cannot silently
  invalidate its fixture.
- **FR-012**: Every case MUST enforce a wall-clock timeout and an output size
  budget; breach fails the case without aborting the sweep.
- **FR-013**: Fixture inputs MUST be self-contained and repository-local (no
  network dependencies beyond the LLM call itself), so that the only
  nondeterminism in a run is the model's reply.

### Key Entities

- **Agent contract**: the machine-checkable slice of an agent's declared
  output rules — first-line pattern, cap regime(s), no-reprint rule,
  section list. Derived from the shipped `.agent.md`; the harness treats the
  agent file as the source of truth.
- **Conformance case**: fixture (canned task input + any stub environment) +
  assertion set + expected regime (clean / with-findings) for one agent.
  Multiple cases per agent are allowed (e.g., one per regime).
- **Skip entry**: agent name + reason; satisfies coverage without execution;
  surfaced in every report.
- **Run report**: per-agent, per-case verdicts (PASS/FLAKY/FAIL/ERROR/SKIP),
  assertion-level failure detail, links to persisted reply artifacts, model
  and timing metadata.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of shipped agent definitions are covered by at least one
  conformance case or a reasoned skip entry, enforced by a check that runs
  without any LLM call.
- **SC-002**: A maintainer can run the full-fleet sweep with a single command
  and read a per-agent verdict for all 34 agents in one report; a full sweep
  completes in under 30 minutes wall-clock.
- **SC-003**: A deliberately introduced contract violation (e.g., removing
  the verdict line from an agent's reply format) is detected as FAIL by the
  suite on the next run, with the violated assertion named and the raw reply
  preserved.
- **SC-004**: Zero false-green from drift: editing an agent's declared
  first-line contract without touching its fixture causes a deterministic
  check failure before any LLM run.
- **SC-005**: A scoped single-agent run completes in under 3 minutes,
  making the harness usable inside an authoring loop.
- **SC-006**: The scheduled run produces the same report format as the local
  run and its regressions are visible to maintainers without inspecting logs
  (failed run status + persisted report artifact).

## Assumptions

- **Runtime**: v1 exercises agents on the Claude runtime only. Codex profiles
  are generated transforms of the same portable source; cross-runtime
  conformance is out of scope for v1.
- **Packaging**: the harness ships as a new self-contained package
  (`packages/agent-conformance`) following the repository's package
  conventions, reading other packages' shipped agent sources read-only at
  run time — consistent with the constitution's self-contained-packages
  principle (no package reaches into another's internals at runtime; agent
  definitions are published contract surfaces, and the existing doc
  generators set the precedent for cross-package read-only scans).
- **Model pins are part of the contract**: cases run each agent with its
  pinned model and effort from frontmatter/agent-models metadata, because the
  regression being guarded is "the shipped configuration honors the shipped
  contract". Explicit per-run model overrides exist for cheap iteration and
  are stamped into the report (FR-008).
- **Fleet scope**: all 34 current `.agent.md` files are in scope. Agents whose
  faithful execution requires a full orchestrate run environment may ship as
  reasoned skips in v1 provided the skip is visible in every report; the
  expectation is that most get stub-environment fixtures.
- **Trigger cadence**: local pre-release invocation is the primary interface;
  a scheduled unattended run is included but is not a required PR gate.
- **Credentials**: maintainers and the scheduled environment have Claude
  credentials available; the harness does not manage or provision them.
- **Flake policy**: bounded retries (default 2 retries after first failure);
  pass-on-retry reports FLAKY and defaults to non-fatal exit.
- **No-reprint threshold**: a reply reprints the fixture when it contains a
  verbatim run of fixture content at or above a small fixed token/character
  threshold (tuned during implementation, then frozen as part of the
  assertion semantics).
- **Prior art boundary**: wshobson plugin-eval-style authoring-quality
  scoring stays out of scope; static authoring checks live in the
  write-agentic linter. This harness asserts runtime behavior only.
