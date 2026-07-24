# Phase 0 Research — Agent Regression Harness

All NEEDS CLARIFICATION items from Technical Context resolved below.

## R1. Execution vehicle: how to run a shipped agent definition

**Decision** *(revised 2026-07-24 — see decisions-log)*: split the harness
into a deterministic engine and an in-session sweep driver.

- **Engine** (`conformance.py`, Python stdlib + PyYAML): subcommands `check`
  (coverage/drift, no LLM), `stage` (create per-case sandbox, emit a run
  manifest: agent name, resolved pins, fixture prompt, sandbox path, reply
  destination), `assert` (judge one captured reply file against its case →
  CaseResult JSONL line), `report` (assemble report.json/md from the
  journal). Everything except the model call itself.
- **Sweep driver**: a Claude Code session following the package's
  `/agent-conformance` skill. For each staged case the session spawns the
  target agent **via the Task tool** — the exact production spawn path (the
  installed agent definition, its pinned model/effort, SubagentStart
  injection, guard hooks all active) — with the fixture prompt, saves the
  subagent's final reply verbatim to the staged reply path, then calls
  `assert`. Parallel Task spawns give the concurrency; the skill mandates
  save-then-assert so no judgment is delegated to the LLM.
- **Headless fallback** (`--engine headless`, opt-in): the previous
  `claude -p --safe-mode --system-prompt-file …` design, retained for
  API-key/CI environments only, deferred to the CI follow-up bead
  (`orc-qrt`). Not the default and not required for v1 acceptance.

**Rationale**:
- **Billing constraint (user-reported, probe-confirmed)**: headless
  `claude -p` bills the API meter (probe: $0.165 for a haiku ping), not the
  subscription. In-session Task spawns are subscription-covered — a fleet
  sweep must not cost API dollars for local maintainers.
- **Fidelity is strictly better**: Task-tool spawn *is* how subagents run in
  production. The headless reconstruction (system prompt file + tool flags)
  was an approximation; this is the real path.
- **Security**: the pre-implementation security review rated headless
  `--safe-mode` HIGH-risk (guard hooks stripped while Bash-bearing agents run
  unjailed). In-session spawns keep every PreToolUse guard active and stay
  inside the session's permission model — the finding is eliminated rather
  than mitigated.
- The deterministic engine remains 100% pytest-coverable in CI (no LLM),
  preserving the per-PR layer (R9).

**Alternatives considered**:
- **Headless CLI as default** (original design): rejected on billing (above);
  survives as the opt-in engine for orc-qrt.
- **promptfoo**: assertion vocabulary fits, but Node dependency, no notion of
  `.agent.md` pins or Claude Code agent semantics, and no subscription-covered
  execution path either.
- **Claude Agent SDK (Python)**: same API-billing problem, plus a heavyweight
  dependency for what the Task tool already does natively.
- **Raw Anthropic API**: bypasses the Claude Code runtime entirely; weakest
  evidence and API-billed.

**Accepted tradeoff**: the sweep driver is an LLM session following a skill,
so sweep orchestration itself is not a deterministic program. Mitigations:
`stage` writes an explicit manifest (the session cannot silently drop a
case — `report` fails on journal/manifest mismatch), `assert`/`report` are
pure, and the reply file is the subagent's verbatim final message. Driver
integrity hardening (critique HIGH-1): SKILL.md mandates writing the Task
result to `reply_path` directly with no editing, summarizing, or reformat;
`assert` enforces a reply plausibility floor (R4) so truncated/paraphrased
saves surface as ERROR. This matches the repo's existing pattern of
skill-driven verification (verify/pr-shepherd skills).

**Context inheritance is accepted fidelity, made observable** (critique
HIGH-2): Task spawns inherit the session's injection stack (SubagentStart
inject, guard hooks) exactly as production spawns do — that *is* the shipped
configuration under test; "fixture is the only context" applies to
task-shaped input, not the runtime preamble. To make environment-induced
drift diagnosable, `stage` records a `context_fingerprint` in the manifest
(SHA-256, truncated to 16 hex chars, of installed-agent-file bytes +
harness version + ISO date YYYY-MM-DD); `report` carries
it so a verdict change with an unchanged agent file points at environment
drift rather than contract drift.

## R2. Contract extraction: source of truth for assertions

**Decision**: Two-layer approach. (1) Each conformance case YAML declares the
concrete expectations (first-line regex, cap words, regime). (2) A
deterministic, LLM-free `check` mode re-derives the declarable slice from the
agent source — first-line pattern from the `## Output` section's `L1`/verdict
line, cap regime from the `CAP` line, no-reprint rule presence — and fails on
mismatch with the case file (FR-011, SC-004).

**Rationale**: Pure source-derivation is brittle (contracts are prose-adjacent:
`LINT-GUARD <node> verdict=PASS|WARN|BLOCK items=<N>` vs `L1 VERDICT:
APPROVE|CHANGES — one sentence why` vs ledger-scribe's "Answer queries in ≤
100 words"). Pure hand-declaration drifts. Declaring in the fixture and
cross-checking against source catches both failure modes and keeps the agent
file authoritative. The extraction reuses the parsing idioms already proven in
`packages/write-agentic/.../lint.py` (CAPS enum regex, CAP-line detection) —
patterns, not imports, to respect package self-containment.

**Alternatives considered**: full auto-derivation (rejected: ~6 of 34 contracts
are structured-line or prose-cap styles needing human judgment to encode);
assertion code per agent in Python (rejected: YAML cases are diffable,
lintable, and writable by non-implementers).

## R3. Fixture format and environment stubbing

**Decision**: Per-agent directory `fixtures/<agent-name>/` containing
`case-*.yaml` (prompt, staged sandbox files, expected regime, assertions,
optional timeout/budget overrides). Sandboxes are fresh temp dirs; fixtures
declare files to stage relative to sandbox root. Environment-dependent agents
get minimal stubs: a `git init` sandbox with committed files where the agent
expects a repo; a `bd init`-ed database where the agent expects beads. Agents
whose faithful stub is infeasible in v1 (deep orchestrate resume loops) are
listed in `fixtures/skips.yaml` with reasons (FR-002 allows this; the report
surfaces every skip).

**Rationale**: Self-contained, repo-local, no network beyond the LLM call
(FR-013). YAML matches repo conventions; per-agent directories keep coverage
checks a directory-listing exercise.

## R4. Assertion semantics (deterministic layer)

**Decision** *(refined per critique findings 4, 5, 7)*:
- **First line**: regex match against the first non-empty line of the reply.
  Optional — prose-contract agents (e.g. ledger-scribe) have no L1 pattern;
  when both the case omits `assert.first_line` and the derived contract has
  none, `check` warns (not fails) and the assertion is skipped.
- **Word cap**: `len(reply.split())` (Python semantics: split on any
  whitespace run; `path:line` is one token) ≤ declared cap for the fixture's
  regime; skipped when the contract declares uncapped. No grace multiplier —
  caps are the contract; production parsers budget on the stated numbers.
- **No-reprint**: fixture content (prompt + staged files) is segmented at
  line boundaries; fail only if the reply contains a verbatim run of ≥160
  normalized characters matching a *contiguous* fixture segment. Per-segment
  matching prevents false positives when an agent legitimately cites many
  short fragments (lint-guard echoing `file:line — rule — reason` per
  finding). Frozen as assertion semantics per the spec assumption.
- **Sections**: required-section presence via regex (e.g. `^L1 ` line);
  conditional sections asserted absent for clean-regime fixtures where the
  contract says "only if non-empty".
- **Side-effect artifacts** (FR-005): fixture declares expected files
  (path glob + per-line verdict regex), checked in the sandbox after the run.
- **Reply plausibility floor**: a reply file under 50 bytes for a non-trivial
  case is ERROR (`implausible-reply`), not judged — defends against the
  sweep driver truncating or paraphrasing a save (critique HIGH-1).

**Rationale**: every assertion is a pure function of (reply, fixture,
declared contract) — reproducible offline against persisted artifacts.

## R5. Verdicts, retries, flake policy

**Decision**: PASS / FLAKY / FAIL / ERROR / SKIP as specified (FR-006).
Default 2 retries after first failure; a retry is a fresh spawn (fresh
sample), assertion layer identical. FLAKY = any retry passed — semantically
"this agent's contract holds probabilistically, not reliably", which is
exactly the signal wanted for prompt-tightening even though each sample is
independent. ERROR = spawn failure, missing/implausible reply, timeout at
the transport layer, config failure — never counted as an agent regression.
Exit code: 0 all PASS/SKIP; 1 any FAIL; 2 any ERROR; FLAKY configurable
(`--strict-flaky` → exit 1), default exit 0 with prominent report line.
**Flake escalation** (critique finding 6): `report` compares against prior
run reports found in the out-dir's parent; an agent-case FLAKY in ≥3
consecutive recorded runs is promoted to FAIL with kind
`chronic-flake` — persistent boundary-oscillation is a real contract
regression, not noise.

## R6. Model/effort pin resolution

**Decision**: in the default in-session engine, pins are honored by
construction — the Task tool spawns the *installed* agent definition, whose
frontmatter carries `model:`/`effort:`; the harness never re-resolves them.
`stage` still parses the pins into the manifest so `report` can stamp
`model`, `effort`, and `model_source: pinned` per case, and `check` verifies
the installed agent registry contains every in-scope agent (a missing install
is a staging error, not a FAIL). Agents without a `model:` pin inherit the
spawning session's model in production and in the sweep alike —
`model_source: inherited-session` marks these visibly weaker-evidence
verdicts. A model override (P3 iteration) is a sweep-driver instruction
(spawn with `model:` param); the reply manifest records `model_source:
override` (FR-008). The headless fallback keeps the previous
`--model`-alias-passthrough behavior for orc-qrt.

## R7. Concurrency and runtime budget

**Decision**: the sweep driver spawns Task subagents in parallel batches
(default 4 per batch, skill-specified). 34 agents × ~1–2 cases × (10–60s per
spawn) in 4-wide batches fits the 30-minute fleet budget (SC-002) with
headroom for retries; a scoped single-agent run is 1–3 spawns ≈ under 3
minutes (SC-005). Cost control: subscription-covered spawns make the
per-case `budget_usd` cap advisory in-session (recorded, not enforced); the
headless engine enforces it via `--max-budget-usd` plus an aggregate
`--max-run-budget-usd` (default $25) per the security review.

## R8. Report format and artifact persistence

**Decision**: `report.json` (machine-readable: per-case verdicts, assertion
detail, model/timing/cost metadata, model_source) + `report.md`
(human summary table) under `--out-dir` (default
`.conformance-runs/<timestamp>/`, gitignored). Raw reply of every non-PASS
attempt persisted as `<agent>/<case>-attempt<N>.txt`. Interrupted sweeps:
results are appended per-case as completed (JSONL journal) and the report is
assembled from the journal, so a partial run leaves a valid partial journal
(edge case: interrupted mid-sweep).

## R9. Coverage + consistency checks (deterministic, per-PR eligible)

**Decision**: `conformance check` subcommand, no LLM: (a) every
`packages/*/.apm/agents/*.agent.md` has ≥1 case dir or a `skips.yaml` entry;
(b) no case/skip references a nonexistent agent; (c) every case's declared
expectations match the source-derived contract slice (R2). Two CI surfaces
(critique finding 3 — fixture-rot defense; both deterministic and free, so
within the local-only-v1 ruling which deferred only the *LLM* sweep;
FR-009 explicitly permits per-PR deterministic checks):
1. Ships as the package's pytest suite → per-package CI matrix runs it on
   PRs touching this package.
2. A repo-level `conformance-check` step in test.yml (alongside the existing
   `agentic-lint` job, same shape) runs `check` whenever any
   `packages/*/.apm/agents/*.agent.md` or `packages/agent-conformance/**`
   changes — so editing an agent's contract in *another* package fails
   per-PR when its fixture drifts, instead of waiting for the next manual
   sweep.

## R10. Where the LLM suite hooks into maintainer flow

**Decision**: documented pre-release step (quickstart + package README):
invoke the `/agent-conformance` skill in a Claude Code session (`sweep all`),
which stages, spawns, asserts, and reports. No hook, no CI in this feature
(clarify Q2 = C). Follow-up bead `orc-qrt` tracks CI wrapping via the
headless engine.

## R11. Security posture (from pre-implementation security review)

Findings and dispositions (full text on bead orc-mol-q72):

1. **HIGH — headless `--safe-mode` strips guard hooks while Bash-bearing
   agents run unjailed** → eliminated for v1 by the in-session engine (guards
   active, session permission model applies). For the orc-qrt headless
   engine: default `--tools Read,Grep,Glob` (contract testing doesn't need
   write/exec), `--permission-mode plan` when an agent's tools include Bash.
2. **MED — path traversal via `sandbox.files` keys** → `check`/`stage`
   validation: keys must be relative, no `..` segments, no leading `/`,
   resolved path must stay under the sandbox root.
3. **MED — credential leakage into persisted replies** → largely eliminated
   in-session (guards + no raw key in env of spawned agent); additionally
   `assert` scans replies for high-entropy token patterns and redacts before
   persisting, flagging the case for human review.
4. **LOW — no aggregate run budget** → in-session: advisory (subscription);
   headless: `--max-run-budget-usd` default $25, aborts remaining cases.
5. **LOW — regex catastrophic backtracking from fixture patterns** →
   `check` rejects patterns exceeding a length/complexity bound;
   `assert` wraps matching in a hard timeout (SIGALRM, 5s per pattern).
