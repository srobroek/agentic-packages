# Feature Specification: Stack Decision Record + Reproduce-Time Staleness Check

**Feature Branch**: `feat/project-setup-modular-redesign` (continues) → likely a
dedicated `feat/stack-adr-staleness` branch

**Created**: 2026-06-28

**Status**: **Draft (2026-06-28)**

**Input**: Roadmap rank #10 from `reviews/tier2-agentic-features-roadmap.md:89-93`
("stack-decision-record + reproduce-time staleness check — medium value / small
effort"). Builds on the 003 Tier-2 resolver (pinned stack decisions in
`answers.toml`) and the 004 gate machinery (hardness=informational + init_only).

## Overview

003 resolves a fully-pinned stack (framework + companions + dev tools) and freezes
it into `answers.toml`. Until now, that decision lives only as raw key/value pairs —
there is no human-readable record of WHY the stack was chosen, no ADR number that
other tooling (docs, PR templates, CI references) can cite, and no feedback loop
when pinned versions silently rot or pick up CVEs while the project is in active
development.

This feature adds a **new module** (`stack-adr`) with two distinct parts:

> **Part 1 — Deterministic STACK.md write (kind=python, both modes):** A pure-
> Python step reads all frozen stack decisions from the plan — every module that
> carries `pinned_deps`, `framework`, `companions`, or `rationale` answers — and
> writes a single `docs/decisions/STACK.md` (or `docs/adr/NNN-stack-decision.md`
> when ADR numbering is requested) from a verbatim template. The date field is
> sourced from the plan's frozen `written_at` timestamp (not wall-clock) so the
> output is byte-identical across reproducers. The ADR number is derived from a
> deterministic max+1 scan of existing files in the target directory. No agent, no
> network.
>
> **Part 2 — Reproduce-only staleness advisory (kind=agent + informational gate):**
> A `kind=agent` step that runs ONLY in reproduce mode checks whether the frozen
> pins are materially stale or CVE-affected, emits an advisory note classifying
> each finding as `high`/`critical` or `hard-deprecation` (lower severity is
> suppressed to avoid fatigue), and surfaces the findings at a `hardness=informational`
> gate (spec 004). This step NEVER mutates pins, `package.json`, `pyproject.toml`,
> or `answers.toml`. Acting on findings is a separate explicit human decision
> (`--refresh lang-python`, not this module). Tier-1 reproduction stays byte-
> identical.

This is the first module to use `hardness=informational` (introduced by spec 004
FR-001/FR-003) and the first to use a `kind=agent` step that runs in reproduce mode
rather than init mode — a deliberate, advisory-only exception to the "research only
at init" principle. The tension is resolved by the advisory posture: the agent emits
no `answers_to_persist`, mutates no files, and the gate never blocks.

## Current state (verified — citations, do not re-derive)

All file:line references verified against shipped code on
`feat/project-setup-modular-redesign` at authoring (HEAD `7779c27`).

- **`hardness=informational` is implemented.** `StepSpec` (`runner/manifest.py:63`)
  declares `hardness: str = "hard"` with valid values `"hard" | "soft" |
  "informational"` (`manifest.py:120` `_VALID_GATE_HARDNESS`). The data-driven
  resolver (`executor.run_gate_step`) handles `informational` → print and proceed
  without prompting (004 FR-003, SC-002). The machinery is in place; 012 is its
  first real consumer.
- **`init_only` is implemented.** `StepSpec` (`manifest.py:69-71`) carries
  `init_only: bool = False`; the gate auto-proceeds in reproduce mode without
  prompting when `init_only=True` (004 FR-006a). 012 needs the INVERSE: a step
  that runs ONLY in reproduce. No `reproduce_only` flag exists yet — this is net-new
  (see Settled Decision D + OQ-1).
- **Frozen plan carries no timestamp.** `ExecutionPlan` (`runner/plan.py:65-78`)
  holds `{schema_version, mode, order, modules}` only; there is NO `frozen_at`,
  `written_at`, or `plan_date` field. `freeze()` (`plan.py:200-221`) writes the
  canonical JSON without any timestamp. The roadmap's "date = frozen plan timestamp
  not wall-clock" requirement therefore has NO current timestamp to read — it needs
  either (a) a new `written_at` field on `ExecutionPlan` frozen at plan-write time,
  or (b) a different deterministic source (see OQ-2, the genuine open question).
- **`answers.toml` carries frozen stack decisions.** `write_answers_toml`
  (`persist.py:233-283`) writes `[module.lang-python]` with all resolved keys
  (including `pinned_deps`, `framework`, `rationale` etc.) at stage 8. `FrozenInputs`
  (`sdk.py:66-138`) exposes `get_str`, `get_list`, `get_choice` on the plan's
  `answers` dict. A `kind=python` step can therefore read the full stack decision
  from the frozen plan via `FrozenInputs.get_list("pinned_deps")` etc., with no
  new persistence primitive.
- **`verify_pins` is a shared SDK helper.** `sdk.verify_pins(pins, ecosystem)`
  (`sdk.py:315-380`) does MCP-free registry verification. It is callable from any
  `module.py`; the staleness advisory step can call it for a fresh freshness probe
  (online at reproduce time, advisory only — not a hard write gate).
- **No existing ADR/STACK.md writing.** A global search over
  `packages/project-setup/` finds no existing module that writes ADR files or
  `STACK.md`. The `agents-md` module writes `AGENTS.md` from a verbatim template
  (`modules/agents-md/module.toml:39-41`, `kind=python` step) — the same
  structural pattern 012's write step follows.
- **`idempotent_write` with `reconcile=True` is the write primitive.**
  `sdk.idempotent_write(rel_path, body, reconcile=..., inspect=...)` (`sdk.py:182-257`)
  writes bytes idempotently — `reconcile=True` updates an existing file to match
  the new body (so re-running updates the record when pins change via `--refresh`);
  `reconcile=False` is write-once (not appropriate here since pins may be refreshed).
- **The `kind=agent` reproduce-mode re-invoke is explicitly blocked today.** 003
  FR-009 (`reproduce.py:335-356` — the old path; fixed in 003) made agent steps
  replay committed answers with zero network. 012 needs to RE-INVOKE the agent in
  reproduce mode (for the staleness probe), but emit NO `answers_to_persist`. This
  requires a new execution path: a "probe-only" agent invocation that fires in
  reproduce but emits only a `message` (no persist), OR a `reproduce_only` marker
  on the step that the runner's Phase-A agent dispatch respects. See Settled
  Decision D.
- **The informational gate fires and auto-proceeds in CI.** 004 FR-003 /
  `executor.run_gate_step`: `hardness="informational"` → prints the message and
  returns True (proceed) without calling `io.confirm`. In non-interactive mode it
  likewise prints and proceeds — never blocks, never SAFE-skips. 012 inherits this
  behavior for its advisory gate verbatim.

## Settled decisions

Letters restart at A for this spec.

- **A — One new module (`stack-adr`), not steps added to `lang-python`/`lang-ts`.**
  The stack record aggregates decisions from ALL enabled lang-* modules (Python +
  TypeScript together, or either alone). Adding the step to a single lang module
  would produce a partial record when both are enabled. A standalone `stack-adr`
  module with `requires = []` and `after = ["lang-python", "lang-ts"]` (order
  dependency only) reads every module's frozen answers via `FrozenInputs` and
  writes one unified record. Module shape: `module.toml` + `module.py` +
  `templates/` + `steering/`.
- **B — Part 1 (STACK.md write) is a pure-python step in BOTH modes.**
  `kind=python`, no agent, no network. It runs at init (first-time record) and on
  every reproduce (update record to reflect current frozen state — correct because
  `--refresh lang-python` may have updated pins). `reconcile=True` so re-runs
  overwrite the record with the current frozen content. No gate (the record write is
  local, deterministic, and reversible — the calibration rules give it hardness
  "none", i.e. no gate step). This is consistent with the roadmap: "no gate for the
  deterministic record write."
- **C — Part 2 (staleness advisory) is a `kind=agent` step in REPRODUCE mode only,
  behind a `hardness=informational` gate.** The agent checks whether the frozen pins
  are materially stale/CVE-affected; emits only a `message` (advisory text, no
  `answers_to_persist`); the gate shows the advisory and auto-proceeds. In init mode
  the step is skipped entirely (pins were just researched and verified; a redundant
  freshness check at init is fatigue with no value — the agent just verified them
  moments ago). On plain reproduce without network the agent MUST gracefully degrade
  (emit "network unreachable, staleness check skipped" as the message).
- **D — The `reproduce_only` mechanism: a new `reproduce_only: bool` field on
  `StepSpec`, parallel to `init_only`.** `init_only=True` makes a gate auto-proceed
  on reproduce; `reproduce_only=True` on an agent step makes the runner's Phase-A
  dispatch SKIP the step in init and INVOKE it in reproduce. In the frozen plan the
  step is present regardless of mode (it must be, so the gate after it fires and
  can be blocked); `run_agent_phase` checks `step.get("reproduce_only")` and
  dispatches accordingly. This is the minimal, symmetric addition to the
  `init_only` mechanism. The staleness gate step carries BOTH `reproduce_only=True`
  (only the agent fires on reproduce) and `init_only=True` (the gate auto-proceeds
  at init — because the agent never ran, there is nothing to show). Together they
  express the "reproduce-only advisory pair" idiom cleanly.
- **E — The ADR date uses the plan's `written_at` field (a new field on
  `ExecutionPlan`).** The roadmap is explicit: "date = frozen plan timestamp not
  wall-clock." The current `ExecutionPlan` has no timestamp (verified above), so
  012 adds a `written_at: str` field (ISO 8601 date string, e.g. `"2026-06-28"`,
  set once at `freeze()` time and never mutated). This makes the ADR date
  byte-identical across all reproducers: clone + reproduce on any machine on any
  date → same `written_at` → same file bytes. Spec-012 adds this field to the plan;
  it is a backward-compatible additive change (old plans without `written_at` fall
  back to an empty string, which the write step renders as `"unknown"`). OQ-2
  captures the exact source and format question.
- **F — The ADR number is a deterministic max+1 scan over existing files in the
  output directory.** The write step scans `docs/decisions/` (or `docs/adr/`) for
  files whose names start with a three-digit prefix (`NNN-…`), takes
  `max(found_numbers, default=0) + 1`, and zero-pads to three digits. Scan order
  is `sorted()` (lexicographic). If no files exist, number = `001`. The scan is
  performed at write time in the `module.py` subprocess, reading the project dir
  via `$PROJECT_DIR`. Because the scan is deterministic (same on-disk state → same
  number), reproduce reads the same files and produces the same number — byte-
  identical if no new ADRs were added between runs. A new ADR added by a human
  between runs produces a higher number; this is correct behavior (the record
  advances to the next available slot).
- **G — Output path is `docs/decisions/STACK.md` (no ADR number, simple format)
  by default; a `format` input switches to `docs/adr/NNN-stack-decision.md` (ADR
  format with number).** The simple path covers teams that do not use ADR
  conventions (the common case for greenfield projects). The ADR format is opt-in.
  Both use the same python write step; the format choice is a module input.
- **H — Severity threshold is enforced in the staleness steering doc, not in code.**
  The steering instructs the agent to flag ONLY: (a) `critical`/`high` CVEs by
  CVSS score, (b) hard deprecations (end-of-life, package abandoned/archived, major
  version replacement with breaking changes announced). LOW/MEDIUM CVEs, patch
  bumps, and minor version bumps are explicitly suppressed. This keeps the advisory
  signal/noise ratio high without a custom severity-filter in code (which would be
  harder to tune). The severity threshold lives in `steering/staleness.md` as human-
  readable guidance to the agent; it is a steering data decision, not a code
  decision.
- **I — The staleness agent emits NO `answers_to_persist`.** Its result carries
  only `message` (the advisory text) and `status="ok"`. The runner's persist stage
  (stage 8, `pipeline.py:568-591`) merges `answers_to_persist` from step outcomes;
  with an empty dict there is nothing to merge. The frozen `answers.toml` is
  unchanged by the advisory step. This is the hard boundary between "advisory" and
  "mutation."
- **J — `stack-adr` is `default_enabled = true`.** Both parts provide high-signal
  output at low cost for any project that uses a lang-* resolver. A team can opt
  out by disabling the module. It is NOT `requires = ["lang-python"]` because it
  works on any combination of enabled lang-* modules, including TypeScript-only
  projects; if no lang-* module is enabled, it emits a minimal record of
  non-resolver decisions (framework = none, no pins) rather than erroring.

## User Scenarios & Testing

### User Story 1 — Fresh init writes a byte-identical STACK.md (Priority: P1)

A user initialises a Python project. After the lang-python resolver runs and pins
are frozen, the `stack-adr` write step produces `docs/decisions/STACK.md` containing
the framework name, all pinned deps, the agent's rationale, and the plan date. A
second user clones the repo and reproduces; their STACK.md is byte-identical.

**Acceptance Scenarios**:

1. **Given** a frozen plan with `lang-python` answers (`framework`, `pinned_deps`,
   `rationale`), **When** the `write` step runs, **Then**
   `docs/decisions/STACK.md` is created with framework, pins, rationale, and
   `written_at` date — no wall-clock date, no randomness.
2. **Given** the same frozen plan on a different machine, **When** reproduce runs,
   **Then** the STACK.md bytes are identical to the init output (Tier-1
   byte-identity check).
3. **Given** `--non-interactive`, **When** the write step runs, **Then** it writes
   without prompting (no gate on the write step).

### User Story 2 — `--refresh` updates the STACK.md (Priority: P1)

A maintainer runs `--refresh lang-python` to upgrade pins. After the new pins are
frozen, the write step re-runs and overwrites `docs/decisions/STACK.md` with the
updated pins. The ADR date reflects the plan's new `written_at`.

**Acceptance Scenarios**:

1. **Given** a committed STACK.md, **When** `--refresh lang-python` produces new
   pins and reproduce runs, **Then** the STACK.md is overwritten with the new pins
   (`reconcile=True`).
2. **Given** ADR format enabled, **When** an ADR number was written at init,
   **Then** reproduce rewrites the same file (same path, same number — the file
   already exists; the scan finds it and re-uses the same slot via an exact-path
   `idempotent_write` call, not a new scan).

### User Story 3 — Reproduce-time staleness advisory (Priority: P1)

A developer reproduces a three-month-old project. The staleness agent finds a
high-severity CVE in one frozen dep. The informational gate prints the advisory
and proceeds without blocking. The developer can act on it by running
`--refresh lang-python`.

**Acceptance Scenarios**:

1. **Given** committed pins, some of which are materially stale or CVE-affected,
   **When** the staleness agent runs in reproduce mode, **Then** it emits an
   advisory message naming the affected packages, their severity, and the
   recommended action (`--refresh`).
2. **Given** the advisory message at the informational gate, **When** it fires in a
   TTY, **Then** it prints and proceeds without prompting (no `[y/N]`).
3. **Given** `--non-interactive`, **When** the advisory fires, **Then** it prints
   and proceeds (informational gates never block CI).
4. **Given** all frozen pins are current or only patch-bumped, **When** the
   staleness agent runs, **Then** it emits "no high/critical findings" (or an
   empty advisory) and the gate proceeds silently with no noise.

### User Story 4 — Init mode skips the staleness check (Priority: P2)

A user runs init. The staleness agent step is NOT invoked (the pins were just
researched and verified moments ago — a redundant check). The informational gate
also does not fire. The write step still runs and produces STACK.md.

**Acceptance Scenarios**:

1. **Given** init mode, **When** the runner reaches the `stack-adr` module's agent
   step, **Then** Phase A SKIPS the agent step (reproduce_only=True) and no
   staleness check is performed.
2. **Given** init mode, **When** the informational gate for the staleness advisory
   fires, **Then** it auto-proceeds immediately (init_only=True on the gate →
   auto-proceed, message not shown because there is no advisory to show).

### User Story 5 — ADR format with number scanning (Priority: P2)

A project opts into ADR format (`format = "adr"`). Init writes
`docs/adr/002-stack-decision.md` (because `001-` already exists for a prior ADR).
Reproduce rewrites the same file. A human-added `003-…` between runs does NOT
affect the number the next reproduce uses (the file already exists at `002-`; the
step writes by exact path, not by re-scanning).

**Acceptance Scenarios**:

1. **Given** `format = "adr"` and one existing `001-…` file in `docs/adr/`,
   **When** init runs, **Then** the file is written to `docs/adr/002-stack-decision.md`.
2. **Given** the committed `002-stack-decision.md`, **When** reproduce runs (even
   if `003-` was added by a human), **Then** the same `002-` path is overwritten
   (path derived from the frozen `adr_path` answer persisted at init, not a re-scan
   on reproduce).

### Edge Cases

- **No lang-* resolvers enabled:** `stack-adr` writes a minimal STACK.md stating
  "no resolver decisions recorded" and no pins section. Not an error — a useful
  stub for projects that later enable a resolver.
- **Both Python and TypeScript resolvers enabled:** STACK.md has sections for both.
  The write step iterates all plan modules and renders any that carry `pinned_deps`
  or `framework` answers.
- **Network unavailable at reproduce time (staleness step):** The agent MUST
  gracefully degrade — it emits "network unreachable, staleness check skipped" as
  its advisory message. The informational gate still fires and prints this message,
  then proceeds. No error, no block.
- **`written_at` absent in an old frozen plan (pre-012):** The write step falls
  back to `"unknown"` for the date field. The record is still written; only the
  date field is affected.
- **ADR directory does not exist:** The write step creates it (via
  `idempotent_write`'s `abs_path.parent.mkdir(parents=True, exist_ok=True)`,
  `sdk.py:246`).
- **A human edits STACK.md between runs:** The `reconcile=True` write will
  overwrite it on the next reproduce (same as any other reconcile-mode file — the
  deterministic re-render wins, consistent with 003/004 behavior). G5
  (destructive-overwrite gate, 004 FR-015) will escalate this to a hard confirm if
  the on-disk content diverges — this is correct behavior and requires no special
  handling in 012.

## Requirements

### Module scaffold

- **FR-001**: A new `stack-adr` module MUST exist at
  `modules/stack-adr/module.toml` + `module.py` + `templates/` + `steering/`.
  Its `module.toml` MUST declare `id = "stack-adr"`, `default_enabled = true`,
  `reconcile = true`, and `[order] after = ["lang-python", "lang-ts"]`.
- **FR-002**: The module MUST declare two inputs: `format` (choice: `"simple"` |
  `"adr"`, default `"simple"`) and `adr_path` (string, derived at init by the write
  step from the ADR scan, persisted to `answers.toml` as a `"derived"` provenance
  answer so reproduce uses the exact same path without re-scanning).

### Part 1 — Deterministic STACK.md/ADR write

- **FR-003**: The `write` step MUST be `kind=python`, run in both init and
  reproduce, have no gate step, and write the output via `sdk.idempotent_write`
  with `reconcile=True` (update on re-run) and `inspect=args.inspect` (preview
  support).
- **FR-004**: The write step MUST read all relevant frozen answers from the plan via
  `sdk.load_frozen_inputs` and `FrozenInputs` accessors. It MUST iterate all plan
  modules and collect any module whose answers carry at least one of `pinned_deps`,
  `framework`, or `rationale`. It MUST NOT hard-code the module ids
  `"lang-python"` / `"lang-ts"` — it discovers resolver modules by the presence of
  those answer keys, so future resolvers (lang-go, lang-rust, package-add) are
  picked up without code changes.
- **FR-005**: The ADR date MUST be sourced from `plan.written_at` (the new
  `ExecutionPlan` field, Settled Decision E). A plan without a `written_at` field
  (pre-012, or loaded from a plan that predates the field) MUST render the date as
  `"unknown"` without erroring.
- **FR-006**: For `format = "adr"`, the write step MUST:
  (a) scan `docs/adr/` for existing `NNN-…` files using `sorted(glob)`, take
      `max(found_numbers, default=0) + 1`, zero-pad to three digits;
  (b) write to `docs/adr/{NNN}-stack-decision.md`;
  (c) persist the resolved path as `adr_path` in `answers_to_persist` with
      provenance `"derived"`, so reproduce reads it from the frozen plan and writes
      to the same path without re-scanning.
  For `format = "simple"`, the output path is always `docs/decisions/STACK.md`
  (no scan, no `adr_path` needed).
- **FR-007**: The write step MUST produce byte-identical output for the same frozen
  plan on any machine (Tier-1 guarantee). Wall-clock (`datetime.now()`,
  `time.time()`, `os.environ.get("SOURCE_DATE_EPOCH")` etc.) MUST NOT appear in
  the rendered content.
- **FR-008**: The output file MUST be rendered from a verbatim template in
  `templates/` with placeholder substitution (no freehand string concatenation of
  ADR content in `module.py`). The template renders: title, date (from
  `written_at`), ADR number (for ADR format), a "Context" section (framework +
  ecosystem), a "Decision" section (pinned_deps table), a "Status" section
  (`"Accepted"`), and a "Rationale" section (agent's rationale text).

### Part 2 — Reproduce-only staleness advisory

- **FR-009**: A new `reproduce_only: bool = False` field MUST be added to
  `StepSpec` (`runner/manifest.py`). When `reproduce_only=True` on a `kind=agent`
  step, the runner's Phase-A dispatch (`run_agent_phase`) MUST skip the step in
  init mode and invoke it in reproduce mode. The step MUST remain in the frozen plan
  regardless of mode (so the subsequent gate is present in both modes).
- **FR-010**: The staleness agent step MUST carry `reproduce_only=True`. Its
  steering doc (`steering/staleness.md`) MUST instruct the agent to:
  (a) check the live registries (PyPI / npm) for each frozen pin's current latest
      version and known CVEs;
  (b) report ONLY findings of severity `high`/`critical` (CVSS ≥7.0) or hard
      deprecations (EOL, abandoned, replaced);
  (c) emit the advisory as `message` (human-readable markdown) with NO
      `answers_to_persist` (advisory-only, never mutates state);
  (d) if the registry is unreachable, emit "network unreachable, staleness check
      skipped" as the message and `status="ok"`;
  (e) NEVER suggest mutating `answers.toml`, `pyproject.toml`, `package.json`, or
      any project file — direct the user to `--refresh` instead.
- **FR-011**: The staleness `kind=gate` step MUST carry `hardness="informational"`
  and `init_only=True`. Together with FR-009 (`reproduce_only` on the agent step):
  at init the agent is skipped (reproduce_only) and the gate auto-proceeds
  (init_only); at reproduce the agent runs (its `reproduce_only` check passes) and
  the gate prints the advisory and auto-proceeds (informational). Neither mode
  blocks. The gate message MUST be `{decision}` (rendered from the staleness
  module's resolved answers at plan-freeze time) so the gate shows the advisory
  text the agent emitted.
- **FR-012**: The staleness agent MUST NOT emit any `answers_to_persist` entries.
  The runner's stage-8 persist (`pipeline.py:568-591`) MUST receive an empty
  `answers_to_persist` dict from this step. This is the hard boundary between
  advisory and mutation (Settled Decision I). This constraint MUST be verified by a
  test that asserts `answers.toml` is unchanged after a reproduce run containing
  the staleness step.
- **FR-013**: The staleness check MUST use `sdk.verify_pins` (the existing
  MCP-free registry helper, `sdk.py:315-380`) as the primary freshness probe, NOT a
  separate network client. The agent MAY supplement with MCP tools (context7,
  package-version) if available, but correctness MUST NOT depend on them.

### `ExecutionPlan` timestamp

- **FR-014**: `ExecutionPlan` (`runner/plan.py:65-78`) MUST gain a `written_at: str`
  field (ISO 8601 date string, e.g. `"2026-06-28"`). `freeze()` (`plan.py:200-221`)
  MUST populate it from `datetime.date.today().isoformat()` at the moment of
  writing. `load_plan()` MUST deserialize it (defaulting to `""` for plans without
  the field). The `to_dict()` serialization MUST include `written_at` so it is
  present in the frozen `plan.json`. This is additive: pre-012 plans are still
  readable (missing field → empty string default).
- **FR-015**: The `written_at` date MUST be the calendar date at freeze time in the
  local timezone of the machine running init. It is an advisory date for human
  consumption (the ADR "decided on" date); it is NOT a cryptographic or audit
  timestamp, and NOT a reproducibility guarantee (OQ-2 captures the open question
  about timezone/UTC policy). Once written to the frozen plan it is immutable:
  reproduce reads it unchanged.

### Determinism & compatibility

- **FR-016**: The `write` step MUST satisfy Tier-1 byte-identity: for the same
  frozen plan, two reproduce runs on any machine MUST produce the same
  `STACK.md`/ADR bytes. The `written_at` field satisfies this because it is read
  from the frozen plan (not the current date) on reproduce.
- **FR-017**: 012 MUST NOT change the behavior of any pre-012 module or gate. The
  `reproduce_only` field defaults to `False` (backward-compatible: existing agent
  steps run in both modes as before). The `written_at` field on `ExecutionPlan` is
  additive (pre-012 plans load without error, missing → `""`). The full 004 suite
  MUST stay green.

## Success Criteria

- **SC-001**: A frozen init plan with `lang-python` answers produces a
  `docs/decisions/STACK.md` containing the framework, all `pinned_deps` in a table,
  the `rationale`, and the `written_at` date from the plan — no wall-clock date
  (unit test: frozen plan with a fixed `written_at`; assert byte-identical output
  across two invocations of the write step).
- **SC-002**: Two reproduce runs of the same committed plan on different machines
  produce byte-identical STACK.md bytes (Tier-1 check; asserted via byte comparison
  in test with a fixed `written_at` plan).
- **SC-003**: ADR format (`format = "adr"`) scans `docs/adr/`, assigns the correct
  `max+1` number, writes to the numbered path, and persists `adr_path` in
  `answers_to_persist` with provenance `"derived"`; reproduce writes to the same
  exact path without re-scanning (unit test with a tmp dir containing one existing
  `001-` file).
- **SC-004**: In init mode, the staleness agent step is NOT invoked (reproduce_only
  check), the advisory gate auto-proceeds (init_only), and no network calls are
  made for the staleness step (verified with a network-blocking IO double).
- **SC-005**: In reproduce mode, the staleness agent step IS invoked; the advisory
  gate fires as informational (prints, proceeds, no prompt); `answers.toml` is
  unchanged after the run (no `answers_to_persist` from the staleness step).
- **SC-006**: With `--non-interactive` in reproduce mode, the informational gate
  prints the advisory and proceeds (never blocks, never deadlocks).
- **SC-007**: When the staleness agent's registry calls are network-blocked
  (test double), it emits "network unreachable, staleness check skipped"; the gate
  still fires and proceeds.
- **SC-008**: A reproduce run where a frozen dep has a simulated HIGH-severity
  CVE produces an advisory message naming the package and severity; a run where all
  deps are patch-bumped only emits a "no high/critical findings" message.
- **SC-009**: `reproduce_only=True` on an agent step is backward-compatible: all
  pre-012 `kind=agent` steps (which carry `reproduce_only=False` by default) behave
  identically to today — full 004 suite stays green unchanged.
- **SC-010**: The `written_at` field is present in the frozen `plan.json` after
  012; loading a pre-012 plan (without `written_at`) does not error and yields
  `plan.written_at == ""` (backward-compat unit test).

## Out of Scope

- Mutating pins, `pyproject.toml`, `package.json`, or `answers.toml` in response
  to staleness findings. Acting on findings requires an explicit `--refresh` run;
  012 never triggers it automatically.
- A structured staleness data schema (machine-readable JSON per-pin with CVSS
  scores). The advisory is human-readable markdown emitted via the gate message;
  machine-readable CVE data is out of scope for this spec.
- Auto-opening a GitHub issue or PR when a CVE is found. Advisory only.
- Go/Rust staleness advisory (pattern extends when those overlays gain resolvers;
  012 handles the py/ts ecosystem which 003 already supports).
- Integrating with external CVE databases beyond what the registries expose
  (PyPI Advisory DB, npm advisories). The advisory relies on what the agent can
  determine from registry metadata and its training knowledge; a dedicated
  CVE-database integration is a separate capability.
- Changing the STACK.md format from markdown to TOML/JSON/YAML structured data.
- A `--no-staleness-check` flag to suppress the advisory in reproduce. The
  informational gate never blocks, so suppression adds no user value. (The whole
  module can be disabled if truly unwanted.)
- Changing the 001/003/004 runner contract, manifest schema, or gate machinery
  beyond the additive `reproduce_only` field and the `written_at` plan field.

## Assumptions

- The 004 runner (informational gate hardness, `init_only` auto-proceed,
  data-driven non-interactive resolver, gate-blocking apply) is in place and green
  (613 tests at 004 ship).
- The two-phase plan (Phase A = agent steps, Phase B = python/gate steps) from 003
  is the execution model. The `reproduce_only` flag is an extension to Phase-A
  dispatch logic in `run_agent_phase` (`reproduce.py`) — no other execution
  subsystem changes.
- The staleness agent has sufficient training knowledge and/or access to registry
  APIs (via `sdk.verify_pins` supplemented by MCP if available) to assess pin
  freshness meaningfully. If the agent's knowledge is insufficient, the graceful
  degradation path (emit a low-confidence advisory) is preferable to a hard error.
- `docs/decisions/` and `docs/adr/` are conventional output paths; projects that
  use a different ADR convention can override via the `format` input and the
  `adr_path` derived answer.
- The `written_at` ISO 8601 date is sufficient for the ADR "decided on" date; UTC
  vs local timezone is an acceptable ambiguity for a human-readable advisory field
  (see OQ-2).

## Dependencies & Open Questions

**Build-order dependency, resolved:** 012 builds on 003 (pinned stack decisions in
`answers.toml`), 004 (informational gate hardness, `init_only` auto-proceed), and
005 (SDK import ergonomics). There is no reverse dependency — 003/004/005 ship
standalone; 012 enriches the record layer on top of them.

**Additive runner changes in scope:** 012 touches `runner/manifest.py` (add
`reproduce_only` to `StepSpec`), `runner/plan.py` (add `written_at` to
`ExecutionPlan` + `freeze()`/`load_plan()`), and `runner/reproduce.py`
(Phase-A dispatch respects `reproduce_only`). These are additive, backward-
compatible changes. Per the scope boundary, they are part of this spec.

**Remaining open questions** (OQ-1 … OQ-3, all MED) are tracked in `memory.md`
so they can be resolved during planning/implementation without re-reading this spec.
**OQ-1** the `reproduce_only` + Phase-A dispatch interaction with `--refresh` (does
`--refresh stack-adr` re-invoke the staleness agent at init?); **OQ-2** `written_at`
source and timezone (UTC vs local, date vs datetime); **OQ-3** the `adr_path`
persist mechanism (can a `kind=python` step emit `answers_to_persist` with
`"derived"` provenance?). None block authoring the plan once OQs are resolved with
the human.
