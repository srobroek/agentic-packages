# Implementation Plan: 019 Answer-Driven CLI

**Spec**: `specs/019-answer-driven-cli/spec.md` · **Status**: Draft (2026-06-29)
**Baseline**: full suite 831 passed, 4 deselected.

Keystone fix; mostly exposes existing plumbing. Single phase + a SKILL.md update, full-
suite gate.

## Phase 1 — IO + CLI + pipeline wiring

1. `runner/io_adapter.py`: add `FileAnswersIO` (a production, non-interactive IO) — or
   extend ScriptedIO — that:
   - `ask(input_spec, default)`: resolve `f"{input_spec['module_id']}.{input_spec['key']}"`
     FIRST, then bare `input_spec['key']`, then `default`. Never reads stdin.
   - `confirm(item)`: NEVER prompt — return based on gate semantics the runner already
     applies via flags (FileAnswersIO.confirm should defer to non-interactive behavior;
     simplest: return False so hard gates SAFE-skip unless their --allow flag is active —
     match how non-interactive TerminalIO/run_gate handles it; verify against
     executor.run_gate_step so flags still drive the outcome).
   - `agent_step(...)`: return the no-op `{"answers_to_persist": {}, "message": ...}`
     (agent-steered answers are pre-seeded, so this should never be reached when answers
     are complete).
   - `notify`: print to stdout (like TerminalIO) so the user sees progress.
   - seed from the parsed answers dict; also accept the `enabled` list.
2. `runner/pipeline.py`: add `"module_id": manifest.id` (or the current module's id) to
   the `input_spec` dict at `_interview_module` (~line 244) AND the module-selection spec
   at ~line 499 (so `enabled` resolves too). This is the one structural gap (FR-003).
3. `runner/cli.py`: add `--answers <path>` arg. When present: parse the file (json; also
   accept .toml by extension), build `FileAnswersIO(answers=..., enabled=...)`, and call
   run_pipeline non-interactively (set non_interactive=True semantics for ask). When
   absent + not --non-interactive → TerminalIO (human fallback, FR-006). Keep all existing
   flags. Malformed/missing answers file → clear error, exit 1 (do not fall back to stdin).

**Tests:** `tests/test_answer_driven_cli.py` (mirror the ScriptedIO test style):
- SC-001 end-to-end: --answers file → .project-setup written, ZERO input() (run with
  stdin closed / a stdin that raises).
- SC-002 module.key disambiguation: lang-python.framework vs lang-ts.framework.
- SC-003 agent-phase no-op: agent-steered answers pre-seeded → zero agent_step calls.
- SC-004 gate via flags: hard gate safe-skips without --allow-*, proceeds with it; no prompt.
- SC-005 enabled from file; SC-006 missing required → MISSING_ANSWER (not a prompt).
- SC-007 backward-compat: existing ScriptedIO tests + TerminalIO direct path unaffected.
**Gate full suite.**

## Phase 2 — SKILL.md + closeout

- SKILL.md "How to run it end-to-end" (FR-008): the answer-driven invocation is primary —
  agent collects answers (interview + agent-steered) → writes answers file → `uv run …/
  cli.py --project-dir <dir> --answers <file> [gate flags]`. Add `--answers` to the flag
  table; state the two-phase model; note interactive form is the human fallback. Sync to
  the global install copy.
- Final full-suite gate; flip spec Status → Implemented; memory AS-BUILT; commit.

## Risk notes
- The change is additive (new flag + IO + a field); the interactive path and all ScriptedIO
  tests must stay green (FR-010/SC-007) — the full suite is the guard.
- Confirm FileAnswersIO.confirm interplay with executor.run_gate_step so the per-action
  flags genuinely drive gate outcomes (don't double-gate or deadlock).
- After build: re-copy the WHOLE skill tree to ~/.claude/skills/project-setup (this touches
  runner code, not just SKILL.md — the global copy must be re-synced fully).
