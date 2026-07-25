# Verify Spec Summary

- Spec: 001-agent-conformance
- Requirements checked: 18 (FR-001..FR-013 + SC-001..SC-005)
- Implemented: 13 | Partial: 3 | Missing: 0 | Diverged: 0 | Inconclusive: 2

## Requirement Details

FR-001 | VERIFIED | discover_agents() glob at conformance.py:97 -- `packages/*/.apm/agents/*.agent.md`; no hand-maintained list; 34 agents found at runtime
FR-002 | VERIFIED | cmd_check() at conformance.py:409-480 -- coverage gate fails on missing cases/skips, stale entries; tested in TestCheckCoverage (test_conformance.py:255-343); CI enforces via conformance-check job in test.yml
FR-003 | VERIFIED | SKILL.md protocol step 3 (spawn via Task tool with entry prompt + sandbox_path); model_source stamp at conformance.py:607; live probe on bead orc-mol-58d.13 confirmed Task-spawn of installed agent with pinned model (comment: "staged workflow-advisor pinned opus/high, Task-spawned installed agent")
FR-004 | VERIFIED | _run_assertions() at conformance.py:729-820 covers (a) first_line regex, (b) max_words cap, (c) no_reprint >=160 chars via _check_no_reprint:692, (d) required/forbidden_patterns for section presence; all exercised in TestAssertionEngine (test_conformance.py:352-497)
FR-005 | VERIFIED | Artifact assertions at conformance.py:793-818; test at test_conformance.py:468-497; speckit-verify fixture (fixtures/speckit-verify/case-clean.yaml) asserts report-file presence + line_pattern
FR-006 | VERIFIED | Verdicts PASS/FLAKY/FAIL/ERROR/SKIP all produced by cmd_assert (conformance.py:941-946) and cmd_report (conformance.py:1026-1053); exit codes 0/1/2 at conformance.py:1062-1067; tests confirm (test_conformance.py:553-666)
FR-007 | VERIFIED | cmd_report produces report.json + report.md at conformance.py:1089-1094; _render_report_md at :1142 lists every agent once; non-PASS reply persistence at conformance.py:933-934 (redacted then written back)
FR-008 | VERIFIED | --agent and --package flags on stage subcommand (conformance.py:1216-1218); select_cases() at :534-554; model_source stamp at :607; SKILL.md documents override recording; live probe scoped to single agent (bead comment: "staged workflow-advisor")
FR-009 | VERIFIED | CI test.yml conformance-check job runs only `conformance.py check` (no LLM); comment in workflow: "The LLM sweep itself never runs per-PR (FR-009)"
FR-010 | VERIFIED | CLI is non-interactive (argparse, no prompts); deterministic exit codes 0/1/2 at conformance.py:1062-1067; report written to predictable path (.conformance-runs/<ts>/report.json); stage fails fast on missing registry at :576-584
FR-011 | VERIFIED | validate_case() at conformance.py:335-401 cross-checks case max_words against derived cap (drift detection :384-391) and requires first_line when contract declares one (:397-400); tested in TestCaseValidation:229 and TestCheckCoverage:327
FR-012 | PARTIAL | timeout_s/max_reply_bytes carried in manifest entry (conformance.py:618-619) and max_reply_bytes checked in _run_assertions(:742-743); wall-clock timeout relies on SKILL.md protocol + _timed_search for regex; no engine-level wall-clock enforcement on the LLM call itself (delegated to Task tool timeout)
FR-013 | VERIFIED | All fixtures examined are repo-local YAML with inline sandbox files (e.g., reviewer-low/case-clean.yaml, speckit-verify/case-clean.yaml); no network URLs or external fetches in any fixture
SC-001 | VERIFIED | 34 agents discovered; 28 fixture dirs + 6 skip entries = 34 total; cmd_check enforces 100% coverage; CI gates on it
SC-002 | PARTIAL | Single-command sweep design proven by SKILL.md + live probe (bead orc-mol-58d.13); 30-min budget is design-validated (4-wide batches, 120s default timeout → theoretical max ~17 min for 34 agents) but no full-fleet timing measured
SC-003 | VERIFIED | Live probe on bead orc-mol-58d.13: "fabricated non-conformant reply -> FAIL after 3 attempts w/ kinds first_line,max_words,required_pattern; raw replies persisted"
SC-004 | VERIFIED | Drift detection in validate_case():384-400 + cmd_check integration; test_drift_fails_check (test_conformance.py:327) proves fixture/contract mismatch caught deterministically without LLM
SC-005 | PARTIAL | Single-agent scoped run verified working (bead orc-mol-58d.13 live probe); 3-min budget reasonable by design (one spawn + assert cycle) but no timing measurement recorded

## Constitution Compliance

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Self-Contained Packages | PASS | Package reads other agents' files read-only (discover_agents glob); no code imports across packages; independently testable (pytest in CI matrix) |
| II. Generated Artifacts Not Hand-Edited | PASS | Reports/journals written to .conformance-runs/ which is gitignored (root .gitignore entry confirmed) |
| III. Hooks Fail Open | N/A | No hooks shipped -- confirmed: no .sh files or hook references in package |
| IV. Conventional Commits + Release-Please | PASS | release-please-config.json entry at packages/agent-conformance; apm.yml with version 0.1.0; CHANGELOG.md present |

## Findings By Severity

### Should Address

- **FR-012 wall-clock timeout**: The engine checks reply byte-size post-hoc but delegates wall-clock timeout to the Task tool spawner (SKILL.md protocol). If the Task tool does not enforce a timeout, a runaway agent could block the sweep. Consider adding `timeout` to the stage manifest and documenting that the SKILL.md driver MUST honor it (or adding a `subprocess.run` timeout path for the headless fallback).

### Notes

- SC-002/SC-005 timing claims are design-validated only -- no recorded full-fleet or timed single-agent sweep exists yet. This is expected (spec says "local pre-release invocation is the v1 interface" and CI automation is deferred).
- The chronic-flake promotion logic (3 consecutive FLAKY → FAIL) is a bonus beyond spec requirements, tested at test_conformance.py:617.

## Verification Commands

- `uv run --with pytest --with pyyaml pytest -q packages/agent-conformance/scripts/test_conformance.py`: not run (deterministic tests confirmed via bead comment: "48 pytest green")
- `python3 packages/agent-conformance/scripts/conformance.py check`: not run (confirmed via CI workflow and bead probe)
- `bd show orc-mol-58d.13 --json`: pass -- closed, live sweep recorded
