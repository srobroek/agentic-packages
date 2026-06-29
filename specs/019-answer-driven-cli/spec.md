# Feature Specification: Answer-Driven CLI (the agent passes collected answers)

**Feature Branch**: `feat/project-setup-modular-redesign` (continues) → likely a
dedicated `feat/answer-driven-cli` branch

**Created**: 2026-06-29

**Status**: **Implemented (2026-06-29)** — KEYSTONE fix shipped. The CLI is now
answer-driven: `--answers <file>` (module.key→value + optional `enabled`) builds a
`FileAnswersIO` that runs the pipeline non-interactively; agent-steered answers are
pre-seeded so the agent-phase no-ops (`is_answer_driven` marker → `run_agent_phase` skips
live calls); `module_id` added to `input_spec` for per-module key disambiguation;
`TerminalIO` demoted to the human-fallback path; SKILL.md rewritten to the two-phase
answer-driven invocation. 20 new tests; full suite 851 passed, 4 deselected. This unblocks
the agent-driven flow (the cause of every prior stalled live test). See
`[[project-setup-distribution-program]]` ⭐ KEYSTONE + AS-BUILT below.

**Input**: Observed in every live test — "The CLI takes no answer arguments… I've already
gathered every answer via the user interview… there's no answer-passing flag." The agent
literally cannot feed its collected answers to the runner.

## Overview

`run_pipeline(io=…)` takes no answers parameter; answers enter ONLY through `io.ask()`,
and `TerminalIO.ask` is a pure stdin `input()` prompt. So at the moment the agent has
every answer in hand (from the SKILL.md interview), the CLI tries to prompt a human. The
interactive path is **vestigial** — the migrated runner is always driven by the agent
("you drive the runner"); the human-stdin model is leftover from the `.sh` monolith.

The io contract is four methods: `ask` (human stdin → should be agent-provided), `confirm`
(human stdin → agent/flags), `agent_step` (agent callback), `notify` (output). None
genuinely needs human stdin. `ScriptedIO` already implements all four as a non-interactive
driver — but only tests use it.

**This spec makes the CLI answer-driven (two-phase model, user-confirmed):** the agent
resolves EVERYTHING up front — the interview AND any agent-steered decisions (stack pins,
etc.) — then passes the complete frozen answer set via `--answers <file>`. The runner runs
start-to-finish non-interactively with ZERO prompts and ZERO agent callbacks (every
answer, including agent-steered, is pre-frozen). `TerminalIO` demotes to a legacy fallback.

## Why most of this already exists (verified)

- `run_agent_phase`'s `do_invoke` gate (`reproduce.py:638-642`): an agent step is SKIPPED
  when its agent-steered answer is already in `resolved_answers`. So pre-seeding
  agent-steered answers makes the agent-phase a NO-OP — exactly the two-phase model. No
  callback fires.
- `resolve_final_answers` already merges layers (home / committed / user_choices) — the
  `--answers` set slots in as an authoritative user-choice layer.
- `ScriptedIO(answers={"module.key": v})` already implements all four io methods. The
  answer-file IO is its production sibling.
- Non-interactive interview already consults `io.ask_non_interactive`/`io.ask`
  (`pipeline.py:252-265`) so a PROVIDED-answers IO is honored without blocking on stdin.

## The one real gap to fix

`input_spec` built in `_interview_module` (`pipeline.py:244-250`) passes `key` but NOT
`module_id`, and `ScriptedIO.ask` looks up the BARE `key` only (`io_adapter.py:212-220`).
Two modules can share an input key (`framework` on lang-python AND lang-ts). So the
answer-file IO MUST resolve `module_id.key` first (then bare `key`), which requires
`module_id` in `input_spec`.

## Functional Requirements

- **FR-001**: The CLI MUST gain `--answers <path>` accepting a file of pre-collected
  answers. Format: JSON (or TOML) mapping `"module_id.key"` → value (and optionally bare
  `"key"` as a fallback for shared defaults). Example:
  `{"core-identity.name": "demo", "core-identity.license": "mit", "lang-python.framework": "fastapi", "lang-python.python_version": "3.13"}`.
  Agent-steered answers (e.g. resolved pins) are included here as ordinary entries.
- **FR-002**: When `--answers` is given, the CLI MUST construct an answer-driven IO (a
  production `FileAnswersIO`, or `ScriptedIO` extended to resolve `module_id.key`) seeded
  from the file, and run `run_pipeline` NON-INTERACTIVELY (implies `--non-interactive`
  semantics for `ask`). No `input()` is ever called.
- **FR-003**: `input_spec` (built in `_interview_module`, `pipeline.py:244`) MUST include
  `module_id`, and the answer-driven IO's `ask` MUST resolve `module_id.key` FIRST, then
  bare `key`, then the declared default. This disambiguates shared keys across modules.
- **FR-004**: With every answer (including agent-steered) pre-seeded, the agent-phase
  (`run_agent_phase`) MUST be a NO-OP — no `agent_step` callback fires (the `do_invoke`
  gate already skips steps whose answers are present). The run completes start-to-finish
  with no callbacks. (If an agent-steered answer is genuinely absent, the step's behavior
  is the existing non-interactive default — it MUST NOT block.)
- **FR-005**: Gates MUST be driven by the existing per-action flags (`--allow-install`,
  `--allow-stack-write`, `--allow-public-repo`, `--no-external-generators`) + the
  non-interactive gate semantics (spec 004) — NOT by stdin `confirm`. The answer-driven IO
  MUST NOT prompt for confirmations; hard gates SAFE-skip without their flag, soft gates
  proceed (the documented CI behavior). The agent passes the flags it needs.
- **FR-006**: `TerminalIO` (interactive stdin) MUST be demoted to a fallback used ONLY
  when neither `--answers` nor `--non-interactive` is given (i.e. a human running the CLI
  directly). The DEFAULT agent path is answer-driven. (Do not delete TerminalIO — keep it
  for direct human use / debugging — but it is no longer the primary.)
- **FR-007**: The `enabled` module-selection answer (`pipeline.py:499`, the module set)
  MUST also be supplied via the answers file (e.g. `"enabled": ["lang-python", …]`) so the
  agent's confirmed module set is honored without a prompt — consistent with the existing
  `[modules].enabled` persistence.
- **FR-008**: SKILL.md "How to run it end-to-end" MUST be updated to the answer-driven
  invocation: the agent collects answers (interview + agent-steered) → writes an answers
  file → `uv run …/cli.py --project-dir <dir> --answers <file> [gate flags]`. The current
  one-command block + flag table gains `--answers` and states the two-phase model
  explicitly. This is the primary path; the interactive form is noted as the human fallback.
- **FR-009**: Reproduce/clone is unaffected — committed `answers.toml` already drives a
  non-interactive replay (the existing reproduce path). `--answers` is the INIT-time
  channel for the agent's freshly-collected answers; on reproduce the committed answers
  are authoritative as today.
- **FR-010**: The full suite MUST stay green; existing `ScriptedIO`-based tests
  (which drive run_pipeline non-interactively) MUST be unaffected. The change is
  additive (a new CLI flag + IO + the `module_id` field); the interactive path still works.

## Success Criteria

- **SC-001**: `uv run cli.py --project-dir <tmp> --answers <file>` with a complete answer
  set runs to completion, writes `.project-setup/{sources,answers}.toml` + the scaffold,
  and calls `input()` ZERO times (assert no stdin read; test via a closed/blocked stdin).
- **SC-002**: An answers file with `lang-python.framework` and `lang-ts.framework`
  (both enabled) resolves each to the correct per-module value (module.key disambiguation,
  FR-003) — not one bleeding into the other.
- **SC-003**: With agent-steered answers pre-seeded in the file, `run_agent_phase` makes
  ZERO `agent_step` calls (FR-004) — verified via the io log / a callback counter.
- **SC-004**: A hard gate (e.g. apm-install G2) with the answer file but WITHOUT
  `--allow-install` SAFE-skips (no install, no prompt); WITH `--allow-install` proceeds
  (FR-005) — no stdin confirm either way.
- **SC-005**: `enabled` supplied in the answers file produces exactly that module set
  (FR-007); omitted → base-only (the existing non-interactive default).
- **SC-006**: A missing required answer is reported by the validate-closed gate (its
  structured `MISSING_ANSWER` error), NOT a stdin prompt — the run fails closed with a
  clear error the agent can act on.
- **SC-007**: Full pre-019 suite green; the interactive `TerminalIO` direct-human path
  still works when invoked with no `--answers`/`--non-interactive`.

## Out of Scope

- A stdio request/response co-process protocol for mid-run agent callbacks (rejected — the
  two-phase model pre-resolves agent-steered answers, so no mid-run callback is needed).
- Removing `TerminalIO` (kept as a human/debug fallback).
- The distribution program (separate repo, catalog, thin-core, SHA-cache) — 020-023; this
  keystone unblocks them but is independent.

## Dependencies

Builds on the existing `ScriptedIO`, the non-interactive interview path (pipeline.py:252),
the agent-phase do_invoke skip (reproduce.py:638), gate flags (spec 004), and
`resolve_final_answers` layering. Touches `runner/cli.py` (the `--answers` flag + IO
construction), `runner/io_adapter.py` (a `FileAnswersIO` or extended `ScriptedIO` with
`module_id.key` lookup), `runner/pipeline.py` (add `module_id` to `input_spec`), and
SKILL.md. No change to the module set or the runner's pipeline stages.
