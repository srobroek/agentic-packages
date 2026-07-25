# Retrospective -- 001-agent-conformance

**Cycle**: 2026-07-23 (bead orc-qg0 created) → 2026-07-24 (implementation
complete). **Output**: 19 commits, 63 files, ~4.3k insertions on branch
`001-agent-conformance`.

## Metrics

- Molecule: 29 steps, all executed or reasoned-skipped; 4 human gates (1
  user-resolved, 3 self-resolved under an explicit autonomy grant with audit
  trail on the gate beads + decisions-log.md).
- Adversarial passes: 1 security review pre-impl (5 findings), 1 critique
  (7 findings), 1 analyze (8 findings), 1 code review (6 findings + gaps),
  1 post-impl security review (2 findings). **28 findings total, all
  remediated or explicitly accepted in-cycle** -- none deferred untracked.
- Tests: 48 pytest (engine, no LLM) + live probes (real Task-spawn PASS,
  fabricated FAIL, FLAKY + strict-flaky flip, missing-result ERROR,
  coverage/drift negative probes, redaction spot check).
- Fleet coverage: 34/34 agents -- 34 cases (28 agents) + 6 reasoned skips.

## What went well

- **Grounding the spec in a fleet survey first** (reading all 34 contracts
  before writing FR-004) meant the assertion vocabulary matched reality;
  only 2 derivation gaps surfaced later (prose caps, regime-noun variance).
- **The adversarial pipeline earned its cost**: the critique caught the
  sweep-driver-corruption and context-inheritance risks that neither the
  spec nor the security review saw; the code review caught two real
  correctness bugs (timeout re-hang, parent-dir scan) before any real sweep.
- **Deterministic engine / LLM driver split** survived every review intact --
  the architecture pivot strengthened rather than weakened it.

## What went poorly / lessons

1. **Billing assumption nearly shipped wrong**: the original design ran on
   headless `claude -p` until the user flagged subscription coverage;
   a $0.165 probe confirmed API metering. **Lesson**: cost-model assumptions
   about execution vehicles are clarify-phase questions, not plan-phase
   defaults -- ask "who pays and from which meter" whenever a design spawns
   model calls.
2. **argparse `nargs="+"` without `action="extend"`** silently dropped
   repeated `--agent` flags; found only by the live T013 probe. **Lesson**:
   the quickstart validation pass is load-bearing -- keep it mandatory.
3. **Blind regex edits to code broke 9 tests** during cleanup (reverted,
   redone precisely). **Lesson**: mechanical edits to code go through exact
   string replacement, not broad regex, when a test suite exists to protect.
4. **Environment fragility burned wall-clock**: two disk-full incidents
   (ENOSPC) interrupted commits and probes; macOS snapshot purges recovered.
   Machine-level, not process-level -- flagged to user in decisions-log.

## Deferred / follow-ups (tracked)

- `orc-qrt`: CI wrapper (scheduled/manual) + headless engine with tool
  restriction and budget enforcement (R11 headless items).
- v2 stubs for the 6 skipped orchestrate agents (skips.yaml reasons).
- SC-002/SC-005 timing validation on the first real fleet sweep.
- Named test gaps from code review (timeout path, assert e2e, git-init
  failure, CRLF) -- hardening, not blocking.

## Improvement suggestions for the process

- speckit-beads formula: the `security review` step's `execution_skill`
  (`speckit.security-review`) names a skill that doesn't exist standalone --
  map to `speckit-security-review-plan` in the formula metadata.
- The molecule's checklist/critique/analyze trio generated overlapping
  findings; sequencing critique BEFORE checklist would have avoided one
  checklist rewrite.
