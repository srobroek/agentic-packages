# Decisions & Escalations Log — 001-agent-conformance

Autonomy grant (2026-07-24): user instructed "continue working autonomously
and resolve human gates yourself; record all questions, ambiguities, issues,
or escalations/input required." Gates are self-resolved with rationale here
and on the gate beads.

## Resolved by user (interactive)

- **Q1 model fidelity → pinned models.** Fleet/release sweeps run each agent
  with its shipped model/effort pins; scoped runs may override explicitly
  (stamped in report).
- **Q2 automation → local-only v1.** No CI workflow in this feature; runner
  is non-interactive/automatable (FR-010). CI wrapper deferred to bead
  `orc-qrt`.
- **Q3 location → new package** `packages/agent-conformance`.

## Resolved autonomously (recorded for review)

- **Plan/agent-context step skipped** (2026-07-24): speckit-plan Phase 1 asks
  to update the `<!-- SPECKIT START/END -->` block in CLAUDE.md; no such
  markers exist and CLAUDE.md is APM-generated ("do not edit manually").
  Hand-editing would violate constitution II. Plan reference lives in the
  spec dir + beads instead.
- **Execution vehicle** (plan R1): headless `claude -p --safe-mode` per case,
  not promptfoo / Agent SDK / raw API. Highest-fidelity reproduction of the
  shipped runtime with zero new runtime deps. Revisit if a future Agent SDK
  gains first-class .agent.md execution.
- **No-reprint threshold** (plan R4): ≥160 normalized chars verbatim from
  fixture content = reprint. Word caps enforced exactly (no grace). These are
  now frozen assertion semantics per spec assumption.
- **Unpinned agents** (plan R6): run on `--default-model sonnet` with
  `model_source: inherited-default` stamped — visible weaker evidence rather
  than a hard error, because production behavior is parent-inherited anyway.

## Open questions for the user

<!-- anything that genuinely needs human input lands here; none yet -->
