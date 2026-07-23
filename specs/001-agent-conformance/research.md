# Phase 0 Research — Agent Regression Harness

All NEEDS CLARIFICATION items from Technical Context resolved below.

## R1. Execution vehicle: how to run a shipped agent definition

**Decision**: Thin custom runner (Python, stdlib + PyYAML) that invokes the
`claude` CLI headless per case: `claude -p --safe-mode --system-prompt-file
<agent-body> --model <pin> --effort <pin> --tools <frontmatter-tools>
--output-format json --no-session-persistence --max-budget-usd <cap>` with
cwd set to a per-case sandbox directory.

**Rationale**:
- Production agents run inside Claude Code; the `claude` CLI is the same
  runtime stack, so a headless invocation with the agent body as system
  prompt is the highest-fidelity reproduction available without a full
  interactive session. The bead itself suggested "thin custom runner via
  Claude Agent SDK" — the CLI *is* the SDK's execution engine and is already
  a required ambient tool for every maintainer of this repo.
- `--safe-mode` disables CLAUDE.md, hooks, plugins, skills, and MCP — the
  fixture is the only context — while ambient auth (OAuth keychain or API
  key) works normally. `--bare` was considered and rejected as the default
  because it hard-requires `ANTHROPIC_API_KEY` and never reads OAuth/keychain,
  which breaks the local maintainer path; the runner exposes it as an opt-in
  for API-key environments.
- `--output-format json` returns the reply plus usage metadata (cost,
  duration, turns) in one parseable envelope.
- `--max-budget-usd` per case is a hard cost guard complementing the
  wall-clock timeout (FR-012).

**Alternatives considered**:
- **promptfoo**: assertion vocabulary fits, but it is a Node ecosystem
  dependency, has no notion of `.agent.md` frontmatter (model/effort/tools
  pins) or Claude Code agent semantics, and the repo's test stack is
  bash/bats + python/pytest. Adapting it costs more than the thin runner.
- **Claude Agent SDK (Python package)**: programmatic and supported, but adds
  a heavyweight dependency for what is ultimately "spawn CLI, capture JSON";
  the CLI path keeps the package dependency-free beyond PyYAML (already the
  repo's CI baseline).
- **Raw Anthropic API**: bypasses the Claude Code runtime (system-prompt
  scaffolding, tool loop), so it would test the prompt text, not the shipped
  agent — explicitly the weaker evidence the clarify session rejected.

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

**Decision**:
- **First line**: regex match against the first non-empty line of the reply.
- **Word cap**: whitespace-token count of the full reply ≤ declared cap for
  the fixture's regime; skipped when the contract declares uncapped. A 10%
  grace multiplier is NOT applied — caps are the contract, exact enforcement,
  because production parsers budget on the stated numbers.
- **No-reprint**: fail if the reply contains any verbatim run of ≥160
  consecutive characters (after whitespace normalization) from any
  fixture-staged file or the fixture prompt. 160 chars ≈ 2–3 code lines —
  above quoting a path or identifier, below any meaningful "reprint".
  Frozen as part of assertion semantics per the spec assumption.
- **Sections**: required-section presence via regex (e.g. `^L1 ` line);
  conditional sections asserted absent for clean-regime fixtures where the
  contract says "only if non-empty".
- **Side-effect artifacts** (FR-005): fixture declares expected files
  (path glob + per-line verdict regex), checked in the sandbox after the run.

**Rationale**: every assertion is a pure function of (reply, fixture,
declared contract) — reproducible offline against persisted artifacts.

## R5. Verdicts, retries, flake policy

**Decision**: PASS / FLAKY / FAIL / ERROR / SKIP as specified (FR-006).
Default 2 retries after first failure; retry re-invokes the LLM (fresh
sample), assertion layer identical. FLAKY = any retry passed. ERROR = CLI
exit non-zero, timeout at the transport layer, auth/config failure — never
counted as an agent regression. Exit code: 0 all PASS/SKIP; 1 any FAIL; 2 any
ERROR; FLAKY configurable (`--strict-flaky` → exit 1), default exit 0 with
prominent report line.

## R6. Model/effort pin resolution

**Decision**: read `model:` and `effort:` from agent frontmatter (the
portable source of truth for the Claude runtime; `.apm/agent-models.yml` maps
Codex only and is out of scope). Pass aliases (`haiku`/`sonnet`/`opus`)
straight through to `--model` — the CLI resolves aliases to current IDs, so
the harness never hardcodes model IDs. Agents without a `model:` pin inherit
the parent's model in production; the runner uses a configurable default
(`--default-model`, default `sonnet`) and stamps `model_source:
inherited-default` in the report so these verdicts are visibly
weaker-evidence. Explicit `--model` override (P3 iteration) stamps
`model_source: override` (FR-008).

## R7. Concurrency and runtime budget

**Decision**: bounded worker pool (default 4 concurrent CLI invocations,
`--jobs` flag). 34 agents × ~1–2 cases × (10–60s per call) with 4 workers
fits the 30-minute fleet budget (SC-002) with headroom for retries; a scoped
single-agent run is 1–3 calls ≈ under 3 minutes (SC-005).

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
expectations match the source-derived contract slice (R2). Ships as the
package's pytest suite too, so the existing per-package CI matrix runs it on
any PR touching the package — no new CI wiring needed (consistent with the
local-only-v1 clarify ruling; fleet-wide drift still surfaces on the next
local sweep or when orc-qrt lands CI).

## R10. Where the LLM suite hooks into maintainer flow

**Decision**: documented pre-release step (quickstart + package README):
`uv run conformance run --all` before cutting releases. No hook, no CI in
this feature (clarify Q2 = C). Follow-up bead `orc-qrt` tracks CI wrapping.
