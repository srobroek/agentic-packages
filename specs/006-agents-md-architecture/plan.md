# Implementation Plan: AGENTS.md Architecture Section

**Branch**: `feat/project-setup-modular-redesign` (continues) → likely `feat/agents-md-architecture`
| **Date**: 2026-06-28 | **Spec**: [spec.md](./spec.md)

**Input**: `specs/006-agents-md-architecture/spec.md` + the synthesis sequencing
(`roadmap-synthesis.md`) which ships 006 second (after 010), as the first feature to
exercise the 004 gate machinery in a fresh module and to add reusable SDK primitives.

## Summary

Extend the `agents-md` module with a Tier-2 architecture-section resolver: an agent
step authors a stack-aware `## Architecture & Conventions` block, a hard `init_only`
gate confirms it, and a python `splice` step writes it into AGENTS.md between fixed
sentinels. Adds two net-new, reusable SDK primitives — `splice_between_sentinels`
(span-replace inside a file) and `scan_top_level_dirs` (shallow dir scan). **Zero
runner/pipeline/executor/manifest changes** — the agent + gate + `{decision}` + init_only
machinery all exist (003/004); 006 only adds module steps + two SDK helpers.

Build order is risk-first: land + unit-test the two SDK primitives FIRST (they are
reused and are the only runner-library surface), then the module extension (toml steps,
step-dispatch in module.py, `_do_splice`, steering doc, template markers), then the
module + full-suite gate.

## OQ resolutions (per spec memory leans — all implementer-resolvable, LOW)

- **OQ-1 (cross-module ctx for the agent)** → read sibling answers via
  `load_frozen_inputs(plan_path, module_id="lang-python"/"lang-ts")` from within the
  agent step's context assembly; if the agent step's context dict can't carry them
  directly, mirror the needed keys as `[[inputs]]` is NOT needed — the agent receives
  context via `io.agent_step(steering, ctx)`; verify `executor.run_agent_step` passes
  the module's resolved answers and add cross-module reads in the steering-doc-driven
  flow. Confirm against `executor.py` `run_agent_step` before wiring.
- **OQ-2 (phantom-path regex)** → match path-table rows of the form
  `| \`<name>/\`` (a backtick-quoted top-level dir name ending in `/` in the first
  table column); strip rows whose `<name>` ∉ `scan_top_level_dirs()`. Heuristic is
  sufficient; documented in `_do_splice`.
- **OQ-3 (primitive home)** → both primitives in `sdk.py` (reusable by future modules;
  e.g. 007 CI could splice a CI section, 012 could scan dirs). NOT module-local.

## Technical Context

**Language/Version**: Python ≥3.11 via `uv`, stdlib only (`os.scandir`, string ops).
No network in either primitive or the splice step. Consistent with 001–005.

**Primary Dependencies**: none new. The two SDK primitives are stdlib. The agent step
reuses the existing Tier-2 subsystem; the gate reuses the 004 enrichment fields.

**Storage**: unchanged. `architecture_md` + `agent_editable_globs` persist as
`agent-steered` answers in `answers.toml` (existing `merge_module_answers_to_persist`
path). AGENTS.md gains a sentinel-bounded span; the rest is byte-identical.

**Testing**: pytest. New unit tests for the two SDK primitives (in `test_sdk.py` or a
new `test_sdk_splice.py`); extended `test_module_agents_md.py` for the splice step +
phantom-path strip + missing-marker fallback + the agent/gate flow via ScriptedIO.
Reproduce zero-network proven by the existing two-phase test harness pattern.

**Constraints**: AGENTS.md splice is byte-identical for the same frozen
`architecture_md` (Tier-1). The architecture section is agent judgment behind a hard
init_only gate (CI safe-skips without `--allow-arch-write`; the skeleton is always
written ungated). Phantom paths are structurally stripped, never trusted. The agent
gets dir NAMES only (no file contents — prompt-injection guard, Settled Decision H).

## Constitution Check

No ratified constitution. Gates on: spec Settled Decisions A–I, the 003 determinism
contract (agent decides / python writes / reproduce replays zero-network), the 004
gate calibration (hard + init_only + allow_flag, no global yes-to-all), and the 001
template-substitution convention. The one extension is two additive SDK functions —
documented here, no contract change to existing primitives.

## Phase 1 — SDK primitives (BLOCKING; land + unit-test first)

All in `runner/sdk.py` + unit tests. These are the reused, load-bearing additions.

1. **`scan_top_level_dirs(project_dir) -> frozenset[str]`** (FR-004): `os.scandir`,
   no recursion, dir names only (incl. hidden `.`-prefixed). Missing/empty dir →
   empty frozenset, never raises.
2. **`splice_between_sentinels(path, begin, end, body, *, project_dir=None,
   inspect=False, missing="append", warnings=None) -> Diff`** (FR-001/002/003):
   - file absent → create it as `begin\n body\n end\n` (kind="create").
   - both markers present → replace the span (exclusive of the marker lines) with
     `body`; if on-disk span == body → kind="skip"; else kind="modify". Content
     outside the markers preserved byte-for-byte.
   - `begin` present, `end` absent (malformed) → ALWAYS skip + warn
     `malformed sentinel span (begin without end)`, regardless of `missing`.
   - markers absent + `missing="append"` → append `begin\n body\n end\n` after the
     first case-insensitive `## Architecture` heading (or EOF), warn
     `sentinel markers absent — appending architecture section`, kind="modify"/"create".
   - markers absent + `missing="error"` → skip + warn, no write.
   - `inspect=True` → identical Diff kind/preview, no write (Tier-1 guarantee).
3. **Unit tests** (SC-002, SC-009): idempotent skip on identical body; modify replaces
   only the span (surrounding bytes identical); create on absent file; malformed
   begin-without-end → skip+warn; missing-markers append-after-heading; scan returns
   correct set incl hidden dirs + empty on missing dir.

**Gate Phase 1 on:** `test_sdk*` green + the full suite still green (sdk.py is imported
everywhere; a regression here is broad). Run the targeted sdk/contracts tests in the
foreground, then the full suite in background before Phase 2's module work is committed.

## Phase 2 — agents-md module extension

1. **`module.toml`** (FR-005/006): append after `write`:
   `resolve-arch` (agent, steering="steering/resolve-arch.md") →
   `arch-gate` (gate, hard, allow_flag="allow-arch-write", init_only=true, message with
   `{decision}`) → `splice` (python). Add two `[[inputs]]`: `architecture_md`
   (string, default "") + `agent_editable_globs` (list, default []).
2. **`module.py`** (FR-007): introduce `STEP_HANDLERS` dispatch (the module currently
   has a single `main()` — refactor to `{"write": _do_write, "splice": _do_splice}`,
   mirroring lang-python; the agent + gate steps are runner-dispatched, never hit
   module.py). `_do_write` = the existing skeleton write (unchanged logic, moved into
   a handler). `_do_splice` = read `architecture_md` + `agent_editable_globs`, call
   `scan_top_level_dirs`, strip phantom path rows (OQ-2 regex), call
   `splice_between_sentinels("AGENTS.md", BEGIN, END, filtered, inspect, missing="append")`,
   emit ModuleResult with warnings. BEGIN/END sentinel constants at module top.
3. **Templates** (FR-008): replace the `<!-- ARCHITECTURE: to be filled… -->`
   placeholder (line 24) in `templates/single.md` + `templates/monorepo.md` with
   `<!-- BEGIN ps:architecture -->\n<!-- END ps:architecture -->` so a fresh `write`
   lands the markers for `splice`.
4. **Steering** (FR-009): create `steering/resolve-arch.md` — instruct the agent to
   read frozen inputs (layout, project_name, org, cross-module framework/pins, top-level
   dir names), check-MCP-don't-depend, author `architecture_md` (description + path
   table using ONLY provided dir names + framework conventions + agent-editable note),
   emit `agent_editable_globs`, never write files, never invent paths, never emit the
   sentinels.

## Phase 3 — tests + verification

1. Extend `test_module_agents_md.py`:
   - splice writes the sentinel span; rest of AGENTS.md byte-identical (SC-003).
   - phantom-path row stripped + warned (SC-004, stub `scan_top_level_dirs`).
   - missing-markers append fallback + second-run splice-replace (SC-007, two-run).
   - `--non-interactive` without `--allow-arch-write` → skeleton written, splice
     safe-skipped; with the flag → splice runs (SC-008).
   - agent step emits `architecture_md`+`globs` via ScriptedIO; reaches frozen plan
     before splice (SC-001); reproduce replays zero-network byte-identical (SC-005);
     `--refresh agents-md` updates / declined leaves unchanged (SC-006).
   - existing agents-md tests pass unchanged (FR-012).
2. Full suite green (FR-012): `uv run --with pytest pytest -q packages/project-setup/tests/
   -k 'not SuccessfulGitFetch'` in background (~7min). 616 baseline → +new tests, zero
   regressions.

## Project Structure

```text
packages/project-setup/skills/project-setup/
├── runner/
│   └── sdk.py                    # + splice_between_sentinels + scan_top_level_dirs (Phase 1)
└── modules/agents-md/
    ├── module.toml               # + resolve-arch/arch-gate/splice steps + 2 inputs (Phase 2)
    ├── module.py                 # STEP_HANDLERS dispatch + _do_splice (Phase 2)
    ├── steering/resolve-arch.md  # NEW agent steering (Phase 2)
    └── templates/
        ├── single.md             # placeholder → BEGIN/END ps:architecture sentinels
        └── monorepo.md           # same
tests/
├── test_sdk*.py                  # + primitive unit tests (Phase 1)
└── test_module_agents_md.py      # + splice/phantom/fallback/CI/agent-flow tests (Phase 3)
```

**Structure Decision**: extend `agents-md` (Settled Decision A) — no new module, no
runner/pipeline change. The only runner-library surface is two additive `sdk.py`
helpers; everything else is module-local.

## Complexity Tracking

| Decision | Why needed | Simpler alternative rejected because |
|----------|------------|--------------------------------------|
| New SDK primitive `splice_between_sentinels` (not `idempotent_write`) | The architecture span is a sub-region; full-file replace would clobber the skeleton + any hand-edits outside the span | Reusing `idempotent_write` requires the agent to emit the WHOLE AGENTS.md — re-introduces the freehand-file risk the resolver pattern avoids |
| Splice step ordered AFTER the skeleton `write` | The markers must exist before the span can be replaced; the skeleton is the deterministic base | Writing markers in `_do_splice` itself would couple skeleton + span into one step and lose the "skeleton always written, section gated" separation (Settled Decision G) |
| Phantom-path structural strip (not agent trust) | The agent can hallucinate a `services/` row a single-package app lacks; AGENTS.md steers every future agent so a phantom path misleads them | Trusting the agent's paths re-introduces the hallucination risk; the dir scan is the deterministic ground truth |
| Agent gets dir NAMES only, no file contents | Prompt-injection guard — a stray repo file must not steer the architecture section | Feeding file contents to the agent opens the exact injection vector spec-004 G8 + the brownfield spec also guard against |
