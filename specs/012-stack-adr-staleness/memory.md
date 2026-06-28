# Feature 012 — Stack Decision Record + Reproduce-Time Staleness Check (memory)

Authored in one session against HEAD `7779c27` on `feat/project-setup-modular-redesign`.
Every code citation was verified by direct read of the runner source; none are
inferred from prior spec text. This file is the durable record of HOW the spec
was reasoned and WHAT needs the human's input before planning can proceed.

## Scope decision (what 012 is)

012 = **one new module (`stack-adr`) with two distinct parts**: (1) a pure-python
`kind=python` step writing `STACK.md` or `docs/adr/NNN-stack-decision.md` from all
frozen stack decisions — deterministic, byte-identical, no agent, no network;
(2) a `kind=agent` reproduce-only advisory step + `hardness=informational` gate
checking whether frozen pins are materially stale or CVE-affected — never mutates
state, never blocks.

Runner changes in scope (additive, backward-compatible):
- `StepSpec.reproduce_only: bool = False` (new field, symmetric with `init_only`)
- `ExecutionPlan.written_at: str` (new field populated at `freeze()` time)

Everything else is module-level code confined to `modules/stack-adr/`.

## VERIFIED CODE FACTS (read these first — grounded against real file:line)

### Fact 1 — `hardness=informational` is fully implemented (004)

`StepSpec` (`runner/manifest.py:63`): `hardness: str = "hard"` with valid set
`{"hard", "soft", "informational"}` (`manifest.py:120`, `_VALID_GATE_HARDNESS`).
The non-interactive resolver handles informational → print and proceed without
prompting (004 FR-003). The freeze serializer carries `hardness` into the frozen
plan (omits only if `== "hard"`, the default — `plan.py:170-171`). 012 is the
first real consumer; no code changes needed for the gate itself.

### Fact 2 — `init_only` is implemented; `reproduce_only` is NOT

`StepSpec` (`manifest.py:69-71`): `init_only: bool = False`. The runner's Phase-A
dispatch and `run_gate_step` respect it. There is NO symmetric `reproduce_only`
field anywhere in `manifest.py`, `reproduce.py`, or `executor.py`. 012 adds it.

### Fact 3 — `ExecutionPlan` has NO timestamp field

`ExecutionPlan` (`plan.py:65-78`): `{schema_version, mode, order, modules}` only.
`freeze()` (`plan.py:200-221`) writes these four fields and nothing else.
`load_plan()` (`plan.py:224-295`) reconstructs from these four fields.
There is NO `frozen_at`, `written_at`, `plan_date`, or any wall-clock capture.
012's FR-014 adds `written_at: str` as a new field — confirmed net-new.

### Fact 4 — No existing ADR/STACK.md writer anywhere in the package

Full-package search for "ADR", "STACK.md", "stack_adr", "decision.record" returned
zero hits in Python or TOML files under `packages/project-setup/`. The only
template-based markdown writer currently is `agents-md` (`modules/agents-md/module.toml:39-41`,
`kind=python`). 012 follows that exact pattern.

### Fact 5 — `idempotent_write(reconcile=True)` is the right write primitive

`sdk.idempotent_write` (`sdk.py:182-257`): `reconcile=True` overwrites an existing
file to match the new body (returns `Diff(kind="modify")`); `reconcile=False` skips
existing files. For STACK.md (which must update after `--refresh`) `reconcile=True`
is correct. The `inspect=True` path produces the same `Diff` without writing —
determinism guarantee holds (`sdk.py:190-196`: "bytes produced in inspect=True are
IDENTICAL to those that would be written").

### Fact 6 — `kind=python` steps CAN emit `answers_to_persist` with `"derived"` provenance

`sdk.emit_result` (`sdk.py:596-657`): validates that `answers_to_persist` sources
are in `MODULE_EMITTABLE_PROVENANCE`. `contracts.py:MODULE_EMITTABLE_PROVENANCE`
includes `Provenance.DERIVED` (`"derived"`) alongside `"default"` and
`"agent-steered"`. So a `kind=python` step CAN emit `adr_path` with
`source="derived"`. This resolves OQ-3 (see below) affirmatively — no new
persistence primitive needed.

### Fact 7 — `run_agent_phase` is the Phase-A dispatch locus

`reproduce.run_agent_phase` (invoked at `pipeline.py:484-492`) iterates manifests
and dispatches `kind=agent` steps. The `reproduce_only` flag must be read here
(or in the `run_agent_step` / `run_agent` branch it calls) to decide whether to
invoke the agent or skip. The step dict in the frozen plan carries whatever fields
`build_plan` serialized; `reproduce_only` must be threaded through the plan
serializer (`plan.py:151-178`) the same way `init_only` is (`plan.py:176-177`).

### Fact 8 — Staleness agent emits NO `answers_to_persist` → stage 8 is a no-op for it

`merge_module_answers_to_persist` (`pipeline.py:570`) merges step outcomes' `answers_to_persist`
into the resolved maps. An empty dict is a safe no-op. `write_answers_toml` then
writes unchanged maps. Confirmed: an advisory-only step with no `answers_to_persist`
leaves `answers.toml` byte-identical — no special runner change needed for FR-012.

### Fact 9 — `sdk.verify_pins` is available from any `module.py`

`sdk.verify_pins(pins, "pypi"|"npm")` (`sdk.py:315-380`): callable from any
module subprocess; uses stdlib `urllib` only; has a `_opener` test seam; returns
`{pin: "verified"|"disconfirmed"|"unreachable"}`. The staleness agent step can
call it directly as the freshness probe (in `module.py` for the reproduce step),
or the steering doc can instruct the agent to call it as a tool. The exact dispatch
is a plan.md detail (OQ-1 touches on whether the agent calls verify_pins or the
runner does it separately).

## OPEN QUESTIONS — require human input before implementation

Each is standalone-answerable. All are MED priority; none block spec authoring.
They DO block finalizing `plan.md` and `tasks.md`.

### OQ-1 — Does `--refresh stack-adr` re-invoke the staleness agent at init? (MED)

FR-009 says `reproduce_only=True` skips the agent at init. But `--refresh` is
defined as "the ONLY mode that re-researches" (003 FR-010). If a user runs
`--refresh stack-adr` in init mode, should the staleness agent fire as a one-off
advisory?

**The tension:** `--refresh` re-invokes agent steps normally (003). A
`reproduce_only` step with `--refresh` is ambiguous: does `--refresh` override
`reproduce_only`? Or does `reproduce_only` always win, making `--refresh stack-adr`
equivalent to `--refresh stack-adr.write` (just re-write the STACK.md)?

**My lean:** `--refresh` on a `reproduce_only` agent step overrides the flag and
invokes the agent (because `--refresh` is an explicit user gesture that signals
"I want fresh research now"). This is consistent with `--refresh` overriding
`init_only` for regular agent steps. The staleness agent should then surface the
advisory at init if the user explicitly asked for it.

**Why it needs the human:** the `--refresh`-overrides-reproduce_only rule is a
runner contract decision that will affect all future `reproduce_only` steps, not
just this one. The human should settle the precedence rule once.

---

### OQ-2 — `written_at` source: UTC date vs local date, and format? (MED)

FR-014 says "ISO 8601 date string, e.g. `2026-06-28`". FR-015 says "calendar date
at freeze time in the local timezone."

**The tension:** `datetime.date.today()` is local-timezone; `datetime.datetime.utcnow().date()`
is UTC. For a human-readable ADR "decided on" date, local is more intuitive (the
developer sees the date they ran init). But it makes the frozen plan non-reproducible
across timezones (user in Tokyo running init at 23:30 JST gets a different date than
their colleague in NYC running at the same UTC moment). For byte-identity this doesn't
matter (the date is frozen in the plan and replayed unchanged), but it does mean two
independent inits of the same project on the same UTC day can produce different dates.

**My lean:** use `datetime.date.today().isoformat()` (local date). The ADR date is
an advisory "human decided on X" field, not a cryptographic timestamp. Byte-identity
is preserved because reproduce reads from the frozen plan. The timezone gap is an
acceptable advisory-field ambiguity. Document in a spec comment.

**Why it needs the human:** the choice is a project-wide policy (every future spec
that uses `written_at` will inherit it), and the human may have a preference for UTC
consistency across contributor machines.

---

### OQ-3 — Can a `kind=python` step emit `adr_path` with `"derived"` provenance? (MED) — TENTATIVELY RESOLVED

**Tentatively resolved YES by Fact 6** (`sdk.py:MODULE_EMITTABLE_PROVENANCE`
includes `"derived"`). The write step can emit
`answers_to_persist = {"adr_path": {"value": "docs/adr/002-stack-decision.md", "source": "derived"}}`
and it will be persisted to `answers.toml` at stage 8, available on reproduce.

**Still open:** does the `kind=python` step's `answers_to_persist` get merged into
`final_answers` in time for `build_plan` to see it? According to 003 AS-BUILT (memory.md
note 1), `answers_to_persist` from step outcomes is only merged at stage 8 (`pipeline.py:570`),
AFTER execution. So the write step can emit `adr_path` at stage 7 but `build_plan`
at stage 6 won't have seen it. This means reproduce can only use the `adr_path`
from `answers.toml` (the committed project layer), not from the current run's emit.
On first init: `adr_path` is not yet in `answers.toml` → the write step must
determine the path itself (do the scan) and emit it; it lands in `answers.toml`
after the run. On subsequent reproduce: `adr_path` IS in `answers.toml` (from the
prior init's stage-8 persist) → it's in `final_answers` → it's in the frozen plan →
the write step reads it from `FrozenInputs` and uses it directly (no re-scan).

**This self-resolves the ADR-path question cleanly:** the write step conditionally
scans (when `adr_path` is absent from the frozen plan = first run) or reads it from
the plan (reproduce). No new mechanism. Confirm with human that this multi-run
bootstrap pattern is acceptable.

---

## ASSUMPTIONS made (flagged so they can be corrected)

1. The `run_agent_phase` dispatch (`reproduce.py`) is the correct attach point for
   `reproduce_only` — not `executor.py` or `pipeline.py`. This mirrors how `init_only`
   is checked at gate execution time (`executor.py`), not at dispatch time. The
   parallel design should be: `reproduce_only` checked at Phase-A dispatch (skip
   invocation at init), `init_only` checked at gate execution (skip prompt on
   reproduce). These are orthogonal concerns.

2. The staleness agent step's advisory message is the text that the informational
   gate renders. Because the gate uses `{decision}` token composition
   (`plan.py:162-164`), the staleness module's answer for a synthetic key
   (e.g. `staleness_advisory`) will be rendered as the gate message. This requires
   the staleness agent step to emit its advisory text as an `answers_to_persist`
   entry so the re-freeze can compose the gate message. But FR-012 says NO
   `answers_to_persist`. This is a real tension:

   **Resolution:** the gate message for the staleness step is NOT composed via
   `{decision}` (which requires the answer to be in `answers_to_persist`). Instead,
   the staleness agent step emits the advisory as part of its `message` field in the
   `ModuleResult`, and the runner surfaces it via `io.notify` as part of the agent
   phase output — BEFORE the gate fires. The gate itself carries a static message
   ("Review staleness advisory above. Proceeding."). The advisory text is shown via
   the agent step's output, not the gate message. This is consistent with FR-012
   (no answers_to_persist) and the informational gate behavior (print, proceed).

3. The module is `default_enabled = true` even though it depends on lang-* resolvers
   producing `pinned_deps`. If neither `lang-python` nor `lang-ts` is enabled,
   the write step emits a minimal STACK.md with no pins section. This is correct
   behavior (a useful stub) and avoids an `optional = true` guard on the module.

4. The `written_at` date in the plan is the date of the INIT run (when the plan
   is first frozen). On subsequent reproduce runs the plan is re-frozen at Stage 6
   (`pipeline.py:495-503`), which would update `written_at` to the reproduce date —
   this breaks byte-identity for the STACK.md date. **Resolution:** `written_at` is
   populated ONLY when `mode == "init"` in `freeze()`; on reproduce it is read from
   the committed plan's module answers or a sentinel field, not re-set to today.
   **This is a design detail for plan.md**: the simplest approach is that `written_at`
   is populated at every `freeze()` call but the STACK.md template reads it from the
   plan's MODULE ANSWERS (persisted from the init run via `answers_to_persist`),
   not directly from the plan's top-level field. The write step emits
   `written_at = plan.written_at` as a `"derived"` answer at init; reproduce reads
   it from `FrozenInputs` (unchanged). Confirm with human which approach (plan-level
   field vs module-answer) is preferred.

## AS-BUILT (TBD)

*To be filled in after implementation.*

## Determinism rules for 012 (must hold)

- The `write` step is Tier-1 byte-identical: same frozen plan → same STACK.md bytes.
  `written_at` is read from the plan (never from wall-clock at write time); template
  substitution is deterministic; ADR path is read from `adr_path` answer on reproduce
  (no re-scan after init).
- The staleness advisory is Tier-2: its content varies with registry state and is
  NOT byte-identical across runs. This is correct and expected — the advisory is
  explicitly NOT frozen. The gate emits it as a `notify` message, not a file write.
- Research at reproduce: the staleness agent IS invoked on plain reproduce (the
  deliberate exception). Plain init does NOT invoke it (`reproduce_only=True`).
  `--refresh stack-adr` invokes it (subject to OQ-1 resolution).
- No `answers_to_persist` from the staleness step: `answers.toml` is unchanged by
  the advisory. Only the `write` step (the deterministic part) emits persisted
  answers (`written_at`, `adr_path`).
