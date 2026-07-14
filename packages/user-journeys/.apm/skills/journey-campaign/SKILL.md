---
name: journey-campaign
description: >-
  Multi-journey validation campaign: fan out validators, dedupe findings, dispatch coder agents for regressions, re-validate until green or a hard stop.
---

# journey-campaign

Orchestrate validation at fleet scale. FORMAT.md and README.md in the
journeys directory are normative; the fix-loop policy comes from README
frontmatter (`fix_loop`, `fix_loop_max_iterations`) unless the invocation
overrides it.

## Plan

1. Select journeys: all `active` by default, or the user's subset, or a
   `journey-verify-changed` scoping pass when the campaign is diff-driven.
2. Group by interface profile. Profiles with `exclusive: true` form a
   serial lane (one validator at a time — typically a single desktop app
   instance); the rest run in parallel.
3. Announce the plan: journeys, lanes, fix-loop mode, iteration budget.

## Validate (iteration 1)

Spawn one `journey-validator` agent per journey with: journey path,
journeys-dir path, mode (full or the scoped step set), and the resolved
profile. Each validator follows the journey-verify procedure end to end
(evidence, triage, intent-gated amendments, run file, findings via
reporter) and returns a structured result: per-step results, amendments,
finding ids.

Aggregate. **Dedupe across journeys**: one product defect surfacing in
several journeys is one finding — file once, reference it from every
affected run file; do not spam the tracker. With the local tracker, id
assignment is single-writer: parallel validators return finding payloads
and the coordinator appends them to TRACKER.md in one pass (github-issues
validators may file directly). The coordinator owns the single reindex and
the single journeys-dir commit per wave.

## Fix loop

Per `fix_loop` mode:

- **report-only** — stop after iteration 1; report.
- **dispatch-coder** (default) — for each unique `suspected-regression`:
  dispatch a fresh coder agent (isolated worktree when parallel) with the
  finding (journey/step, expected vs observed, evidence, repro steps) and
  the repo's own gates (tests/lint) as its acceptance bar. The validator
  never fixes product code; the coder never edits journeys. When fixes
  land, re-validate **only** the failed journeys, scoped to failed/blocked
  steps plus what is needed to reach them. Iterate.
- **fix-direct** — the campaign context fixes small regressions itself,
  then re-validates. Note in each finding that fixer and validator shared
  context (weakest evidence integrity; solo use).

**Hard stops** — end the loop and hand to the human when:
- iteration count reaches the budget (default 3),
- the same finding fails again after a fix attempt (one retry per finding),
- a finding is triaged `product-question` — never auto-resolved; park it
  and continue the rest,
- the environment breaks (env findings spike) — fix the harness or stop;
  do not burn iterations on a broken bench.

Re-triage after every iteration: a "fix" that changes behavior without
intent evidence is itself a regression.

## Report

Single campaign report at the end:
- per-journey final state (pass / fail / blocked, version validated,
  amendments with evidence),
- findings: fixed (with fix commits/PRs), still open, parked
  product-questions needing decisions,
- iterations used; what was NOT covered and why,
- proposals: consolidation candidates (green journeys with Δ entries),
  coverage gaps, surface-map additions.

Commit journeys-dir changes per journey-verify's convention. Product-fix
commits follow the repo's workflow: a coder that commits owns its commit;
when the coder agent type does not commit, the coordinator commits the fix
citing the finding id. Never leave an applied fix uncommitted.
