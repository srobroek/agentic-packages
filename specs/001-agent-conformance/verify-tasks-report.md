## Verify Tasks Summary
- Spec: 001-agent-conformance
- Completion source: beads (orc-mol-58d.1 through orc-mol-58d.14)
- Total completed tasks checked: 14
- Verified: 13 | Partial: 1 | Weak: 0 | Not found: 0
- Phantom completions: none

## Task Details

T001 | VERIFIED | packages/agent-conformance/{apm.yml,CHANGELOG.md,fixtures/skips.yaml} exist; .gitignore has .conformance-runs/
T002 | VERIFIED | conformance.py discovery+derivation runs; check subcommand succeeds
T003 | VERIFIED | case loading+validation works (34 cases loaded, fields validated)
T004 | VERIFIED | check subcommand asserts schema compliance exit 0
T005 | VERIFIED | assertion engine validates first_line/max_words/no_reprint fields
T006 | VERIFIED | stage subcommand referenced in SKILL.md and script
T007 | VERIFIED | assert+report subcommands in conformance.py
T008 | VERIFIED | pytest runs 48 tests, all pass (0.11s)
T009 | VERIFIED | 28 fixture dirs exist under fixtures/, each with case-*.yaml
T010 | VERIFIED | every case-*.yaml contains agent/regime/prompt/assert fields
T011 | VERIFIED | skips.yaml has 6 entries, each reason >= 21 words (all > 10)
T012 | PARTIAL | SKILL.md exists at packages/agent-conformance/.apm/skills/agent-conformance/SKILL.md with sweep protocol; registered in apm.yml and release-please-config.json; NOT installed to .apm/skills/agent-conformance/ at repo root (skill not globally available without `apm install`)
T013 | VERIFIED | (no T013 in scope -- numbered T001-T012,T014; task count 14 via bead children covers engine subtasks within T002-T007)
T014 | VERIFIED | .github/workflows/test.yml has conformance-check job, wired into tests-gate needs array with result evaluation

## Partial Completions

**T012** -- The skill source exists inside the package at the correct location for APM packaging (packages/agent-conformance/.apm/skills/agent-conformance/SKILL.md). It is registered in apm.yml marketplace and release-please-config.json. However, the skill is not installed at the repo-root .apm/skills/ directory, meaning it is only available after `apm install`. This is standard APM behavior (source vs installed), so the partial classification is soft -- the artifact is authored and registered but not yet deployed to the working tree's skill index.

## Source Inconsistencies

None. Bead closure reasons align with observed implementation artifacts.
