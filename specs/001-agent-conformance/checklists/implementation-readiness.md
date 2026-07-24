# Implementation Readiness Checklist: 001-agent-conformance

**Purpose**: Gate implementation on requirement quality + plan coverage
**Created**: 2026-07-24 (autonomous pass; see decisions-log.md)
**Feature**: [spec.md](../spec.md) · [plan.md](../plan.md)

## Requirements → design traceability

- [x] Every FR maps to a design decision or contract (FR-001→R1/T002 discovery; FR-002→R9/T004; FR-003→R1/T006; FR-004→R4/T005; FR-005→T005 artifacts; FR-006→R5; FR-007→R8/T007; FR-008→cli.md scoping/override; FR-009→R9 CI posture; FR-010→cli.md fail-fast; FR-011→R2/T004 drift; FR-012→T006 timeout/budget; FR-013→case-schema rules)
- [x] Every SC has a validation path in quickstart.md (SC-001→§1 negative probe; SC-002→§3; SC-003→§4; SC-004→§1 drift probe; SC-005→§2)
- [x] All four user stories have implementing tasks (US1→T006/T007/T009-T011; US2→T004; US3→cli.md --agent; US4 removed by clarify Q2)

## Ambiguity scan

- [x] No [NEEDS CLARIFICATION] markers in spec or plan
- [x] Frozen constants documented (160-char no-reprint threshold, exact caps, retry=2, jobs=4, timeout=120s, budget=$1/case)
- [x] Underivable-contract fallback defined (case YAML is encoding of record; check validates only non-null derived fields)
- [x] Unpinned-agent policy defined (default-model + model_source stamp)

## Risk checks

- [x] Cost: in-session sweeps are subscription-covered (no metered spend); monetary budgets enforced only in the deferred headless fallback (per-case cap + $25 aggregate, orc-qrt)
- [x] Interrupted-run behavior specified (JSONL journal + report rebuild)
- [x] No new runtime dependencies beyond PyYAML (already CI baseline)
- [x] Constitution check passed pre- and post-design (plan.md)
- [x] Execution fidelity: resolved by the R1 pivot — the sweep spawns
  installed agents via the Task tool, the production path itself; the
  headless-proxy fidelity question is mooted for v1 (deferred with orc-qrt).

## Notes

- Post-pivot re-evaluation: 13/13 pass. Gate assessed PASS for proceeding to
  analyze/implement.
