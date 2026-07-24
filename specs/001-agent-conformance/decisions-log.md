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

- **Checklist step run autonomously** (orc-mol-w31): implementation-readiness
  checklist authored + self-evaluated 12/13; the open item (headless fidelity)
  was mooted by the R1 pivot below.
- **ARCHITECTURE PIVOT — execution vehicle** (2026-07-24, triggered by user):
  user flagged that `claude -p` is not subscription-covered; probe confirmed
  API metering ($0.165/haiku ping). R1 redesigned: deterministic engine
  (`check`/`stage`/`assert`/`report`) + in-session sweep driver that spawns
  installed agents via the Task tool (subscription-covered, production spawn
  path, guard hooks active). Headless `claude -p` demoted to opt-in fallback,
  deferred with CI to `orc-qrt`. Spec assumption "Credentials & billing"
  updated; plan/cli/quickstart/T006/T007/T012 rewritten. Accepted tradeoff:
  sweep orchestration is skill-driven (LLM session), mitigated by the
  manifest no-dropped-case invariant and pure assert/report.
- **Security review verdict CONDITIONAL, 5 findings** (bead orc-mol-q72):
  HIGH (safe-mode strips guards) eliminated by the pivot; MED path-traversal
  and MED credential-redaction folded into check/stage/assert (R11, T006,
  T007); LOW aggregate budget + LOW regex DoS encoded in R11 and cli.md.
  No blocking findings remain for the v1 design.

- **Critique verdict PROCEED-WITH-CHANGES, 7 findings — all adopted** (bead
  orc-mol-uf5): driver-corruption defense (verbatim-write mandate + reply
  plausibility floor), context-inheritance made observable
  (context_fingerprint), fixture-rot defense (repo-level deterministic
  conformance-check CI step, new T014 — within FR-009 since no LLM),
  per-segment no-reprint matching, first_line now optional for prose
  contracts, chronic-flake→FAIL promotion, word-count pinned to
  `len(reply.split())`.

## Open questions for the user

- **Disk pressure (2026-07-24)**: the machine hit 100% full mid-run (ENOSPC),
  then recovered to ~7 GiB free without intervention. Largest reclaimable
  caches if it recurs: `~/Library/Caches/Mozilla.sccache` 13G,
  `Homebrew` 3.8G (`brew cleanup`), `pip` 1.3G. Not deleted — user data,
  needs your call.
- FYI: the fleet sweep's wall-clock (SC-002 < 30 min) now depends on parallel
  Task-spawn batching inside one session; if real sweeps exceed it, the fix
  is raising batch width, not architecture.
