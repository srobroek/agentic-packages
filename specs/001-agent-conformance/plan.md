# Implementation Plan: Agent Regression Harness — Contract-Conformance Tests

**Branch**: `001-agent-conformance` | **Date**: 2026-07-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-agent-conformance/spec.md`

## Summary

Ship `packages/agent-conformance`: a thin Python runner that executes each
shipped agent definition headlessly via the `claude` CLI (agent body as
system prompt, pinned model/effort, sandboxed cwd, fixture prompt as input),
captures the reply, and asserts the agent's declared output contract
deterministically — first-line verdict regex, word caps per regime,
no-reprint threshold, section presence, side-effect artifacts. A separate
LLM-free `check` mode enforces fixture coverage of the fleet and
fixture↔source contract consistency, and runs in the existing per-package CI
matrix as pytest. LLM sweeps are local-only in v1 (CI deferred to `orc-qrt`).

## Technical Context

**Language/Version**: Python 3.11+ (repo CI floor is 3.14; stdlib +
PyYAML only, matching existing package test conventions)

**Primary Dependencies**: `claude` CLI (ambient, required); PyYAML (CI
baseline); pytest for the deterministic suite. No new runtime deps.

**Storage**: files — YAML fixtures in-package; JSONL journal + JSON/MD
reports under a gitignored `.conformance-runs/` output dir

**Testing**: pytest for contract-extraction/assertion/coverage units
(deterministic, no LLM — runs in the per-package CI matrix); the LLM sweep is
itself the product and is exercised manually

**Target Platform**: macOS + Linux dev machines (bash 3.2/BSD floor
irrelevant — runner is Python; any shell entry point must honor it)

**Project Type**: single package — `packages/agent-conformance` (clarify Q3)

**Performance Goals**: full-fleet sweep < 30 min wall-clock (SC-002);
single-agent scoped run < 3 min (SC-005); default 4 concurrent CLI calls

**Constraints**: per-case wall-clock timeout + `--max-budget-usd` cap
(FR-012); non-interactive once invoked (FR-010); fixtures repo-local, no
network beyond the LLM call (FR-013); LLM suite never a required PR check
(FR-009)

**Scale/Scope**: 34 agents across 13 packages today; discovery-driven
(FR-001) so the count floats with the fleet

## Constitution Check

*GATE: evaluated pre-Phase-0 and re-checked post-design — PASS on both.*

- **I. Self-Contained Packages**: PASS. New package is independently
  installable/testable/releasable. It reads other packages' `.agent.md`
  files read-only at runtime — same cross-package read precedent as the doc
  generators; agent definitions are published contract surfaces, not
  internals. No package imports another's code.
- **II. Generated Artifacts Are Not Hand-Edited**: PASS. Reports/journals are
  run outputs in a gitignored directory, never committed. Fixtures are
  hand-authored sources, not generated artifacts.
- **III. Hooks Fail Open**: N/A — no hooks shipped.
- **IV. Conventional Commits and Release-Please**: PASS. Standard package
  layout (`apm.yml`, `CHANGELOG.md`) picked up by the generated
  release-please config on regen.

## Project Structure

### Documentation (this feature)

```text
specs/001-agent-conformance/
├── spec.md
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── case-schema.md   # fixture case YAML contract
│   ├── cli.md           # runner CLI contract
│   └── report-schema.md # report/journal JSON contract
├── checklists/requirements.md
└── decisions-log.md     # autonomy decision/escalation record
```

### Source Code (repository root)

```text
packages/agent-conformance/
├── apm.yml                          # type: hybrid, category: engineering
├── CHANGELOG.md
├── .apm/skills/agent-conformance/   # skill: how to run/interpret the suite
│   └── SKILL.md
├── scripts/
│   ├── conformance.py               # single-file runner: run/check/report
│   └── test_conformance.py          # pytest: extraction, assertions, coverage
└── fixtures/
    ├── skips.yaml                   # reasoned skip entries (FR-002)
    └── <agent-name>/case-*.yaml     # one dir per covered agent
```

**Structure Decision**: one package, one runner script (subcommands `run`,
`check`), fixtures co-located. Follows the skill-package script conventions
(`test_*.py` next to the script is auto-picked by test.yml's per-package
matrix). The SKILL.md gives sessions a discoverable entry point
(`/agent-conformance`) documenting the pre-release sweep.

## Design decisions (from research.md)

| # | Decision | Ref |
|---|----------|-----|
| 1 | Execution via `claude -p --safe-mode --system-prompt-file … --output-format json`, per-case sandbox cwd | R1 |
| 2 | Assertions declared in case YAML, cross-checked against source-derived contract slice (`check` mode) | R2 |
| 3 | Fixtures: `fixtures/<agent>/case-*.yaml` + staged sandbox files; `skips.yaml` for infeasible stubs | R3 |
| 4 | No-reprint threshold: ≥160 normalized chars verbatim from fixture content; caps exact, no grace | R4 |
| 5 | Verdicts PASS/FLAKY/FAIL/ERROR/SKIP; 2 retries; exit 0/1/2; `--strict-flaky` | R5 |
| 6 | Pins from frontmatter, aliases passed through; unpinned agents → `--default-model` + `model_source` stamp | R6 |
| 7 | 4-way concurrency default; JSONL journal enables partial-run recovery | R7, R8 |
| 8 | `check` mode + pytest = deterministic per-PR layer via existing CI matrix; LLM sweep local-only | R9, R10 |

## Complexity Tracking

No constitution violations; table not needed.
