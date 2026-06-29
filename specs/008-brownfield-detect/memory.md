# Feature 008 — Brownfield Detect and Adopt (memory)

Authored in one session (2026-06-28). Verified against shipped code on
`feat/project-setup-modular-redesign` at HEAD `7779c27`. The "don't trust a
subagent's reading" discipline held: all pipeline and enablement citations were
verified by direct file reads.

## Scope decision (what 008 is)

008 = **a default-enabled Tier-2 module (`brownfield-detect`) that runs its agent
step in a new pre-interview Stage 3c, scans lockfiles/manifests to infer the repo's
existing stack, emits a structured decision that pre-fills `proposed_enabled` and
per-module answer defaults, and guards behind a hard `init_only` gate. It writes
ZERO files. Its entire output is agent-steered answers folded into the standard
002 enablement channel and the per-module answer layers.** It is roadmap rank #6.

## VERIFIED CODE FACTS (read these first)

Facts verified by direct file reads; the load-bearing pipeline facts were read
line-by-line.

### Fact 1 — The enablement channel is `proposed_enabled: list[str] | None` at pipeline stage 3b

`pipeline.py:371-420` (stage 3b): `committed_enabled` is read from `answers.toml`
in reproduce; `proposed_enabled` is sourced from `io.ask({"key": "enabled",
"type": "list", ...})` in init (`pipeline.py:381-403`). Both feed
`resolve_enabled_modules(manifests, committed_enabled=..., proposed_enabled=...,
mode=...)` at `pipeline.py:405-410`. The brownfield agent's module proposal must
land in `proposed_enabled` before line 405. **This is the only channel** —
`resolve_enabled_modules` does not accept a third source.

### Fact 2 — Stage 5b `run_agent_phase` runs AFTER the interview and validate-closed

`pipeline.py:474-492`: stage 5 (validate_closed) is at line 466, then stage 5b
(run_agent_phase) at line 483. Stage 4 (interview) is at `pipeline.py:432-453`.
The standard agent phase runs AFTER interviews are done and manifests already
filtered. A brownfield agent step in Stage 5b CANNOT influence which modules are
included in the interview — the filtered `manifests` list is already computed at
line 420.

### Fact 3 — `_interview_module` uses `current` dict as the default layer

`pipeline.py:448-453`: for each manifest, `current = dict(home_answers.get(id, {}))`;
`current.update(committed_answers.get(id, {}))`. Then `_interview_module(manifest,
current, io, non_interactive)` is called. `_interview_module` at `pipeline.py:173-175`
uses `current_answers.get(key, inp.default)` as the default for each input. So
injecting a per-module brownfield answer into `current` before this call is the
correct attach point for pre-fills — no new interview primitive needed.

### Fact 4 — `resolve_enabled_modules` validates proposed ids against discovered manifests

`enablement.py:78-95`: iterates `raw_selection`, and for each id not in `all_ids`
appends a `UNKNOWN_MODULE` error; valid ids accumulate in `explicit_selection`.
Brownfield must only emit module ids that are actually discovered. The agent
steering doc must instruct the agent to emit only ids from the provided discovered
module list (passed as context).

### Fact 5 — No `brownfield-detect` module directory exists today

`packages/project-setup/skills/project-setup/modules/` (verified): `agents-md`,
`apm-install`, `codex-config`, `core-identity`, `dirs-scaffold`, `git-init`,
`github-repo`, `gitignore-generate`, `justfile-write`, `lang-go`, `lang-python`,
`lang-rust`, `lang-ts`, `license-write`, `package-add`, `precommit-setup`,
`quality-hooks`, `speckit-bridge`. No `brownfield-detect`. Fully net-new.

### Fact 6 — `default_enabled=true` is legal for bundled modules (001 FR-035)

The 001 spec enforced that non-bundled (third-party source) modules cannot set
`default_enabled=true`. Bundled modules (under `modules/`) CAN. Confirmed by
reading `sources/discover.py` (not re-read in this session; inherited from 002 spec
"Current state" which stated: "`default_enabled=true` on a non-bundled module is
already a hard error"). Brownfield is bundled, so `default_enabled=true` is valid.

### Fact 7 — The `init_only=true` gate pattern is established in `lang-python/module.toml`

`lang-python/module.toml:42-49`: the `pins` gate declares `hardness = "hard"`,
`allow_flag = "allow-stack-write"`, `init_only = true`. This is the exact shape
brownfield's gate will follow. Confirms the 004 pattern is exercised in an
existing module.

### Fact 8 — G8 secret guardrail fires at the interview/persist boundary for ALL modules

`pipeline.py:207-216`: `_interview_module` calls `looks_like_secret(value)` for
every collected input value regardless of which module. Brownfield's pre-filled
answers flow through `_interview_module` on the downstream overlay modules — G8
fires on those answers automatically. Brownfield's own agent step emits answers via
`answers_to_persist` (not through `_interview_module`) — those are folded by
`merge_module_answers_to_persist` at stage 8, which does NOT have a `looks_like_secret`
check. **This means the steering prohibition (FR-010) + the Stage 3c helper
filtering are the primary defenses for brownfield's own emitted answers; G8 is the
secondary catch for pre-filled answers on downstream modules.**

### Fact 9 — `run_agent_phase` currently iterates ALL enabled module manifests

`reproduce.run_agent_phase` is invoked at `pipeline.py:484-492`. It must be
extended to skip the brownfield module (which already ran in Stage 3c). The skip
condition: check the module id against a set of already-run-agent-steps passed in
from the pipeline. This is a small additive change — the helper gains an optional
`skip_ids: set[str]` parameter.

## Ordering tension (the trickiest design point)

The core challenge: brownfield's agent step must influence both (a) which modules
are in the interview and (b) what defaults those modules' interviews see. But the
standard Phase A agent pass (Stage 5b) runs after the interview. Therefore:

**Three-stage ordering around the interview:**
1. **Stage 3b**: Enablement resolution (base defaults + committed/proposed).
   At this point `proposed_enabled` = None (empty) if brownfield has not run yet.
2. **Stage 3c (NEW)**: Brownfield early-agent phase. Runs brownfield's agent step,
   produces `{proposed_enabled: [...], brownfield_answers: {mod_id: {key: val}}}`.
   Injects `proposed_enabled` into the stage-3b output (re-runs enablement with
   brownfield's proposal), filters manifests to the updated enabled set.
3. **Stage 4**: Interview, with brownfield_answers as an extra default layer.

The "re-run enablement" approach at Step 2 is the simplest: stage 3b already
accepts `proposed_enabled`; running it twice (once with None, once with brownfield's
proposal) is safe and idempotent (both calls are pure, no writes). The first call
gives the base set; if brownfield proposes additions, a second call merges them.
The result replaces `enabled_ids` and the filtered `manifests` list.

Alternative considered: inject brownfield's proposed_enabled directly into `io`
so the existing single stage-3b `io.ask("enabled")` call returns it. Rejected:
this would mutate the IO adapter from inside the pipeline, which is fragile and
makes the flow hard to test.

**Chosen approach**: a `run_brownfield_phase(manifests, ...)` helper in `pipeline.py`
that, if `brownfield-detect` is in the discovered manifest list, (a) runs its agent
step synchronously (not via the full `run_agent_phase`), (b) extracts the
`proposed_enabled` + `brownfield_answers` from the result, (c) re-calls
`resolve_enabled_modules` with the updated proposal, and (d) returns the updated
`(enabled_ids, manifests, brownfield_answers)` tuple. In reproduce mode: no-op
(the committed answers already carry everything).

## OPEN QUESTIONS — resolve during planning/implementation

Each is written so it can be answered without re-reading the spec.

### OQ-1 — Stage 3c placement: single synchronous invocation vs re-using `run_agent_phase`? (HIGH — architectural)

**Context**: Settled Decision B says a new `run_brownfield_phase` helper runs before
Stage 4. The question is the exact invocation shape.

Option A: The helper calls `io.agent_step(steering_path, context)` directly
(bypassing the Phase-A machinery). Simpler; brownfield is a known single-step
module.
Option B: The helper calls a stripped-down version of `run_agent_phase` for
brownfield only, reusing the reproduce-vs-init branching already in that function.

**Lean: Option B.** `run_agent_phase` already handles the init-vs-reproduce
branching (init invokes the agent; reproduce replays committed answers). Reusing it
(with a `module_ids: set[str]` filter) keeps the brownfield replay logic in one
place. In reproduce mode the function detects that brownfield's answers are already
in `final_answers` and returns immediately — the no-op path is already there.

**Why it needs human input**: Option A is simpler to write but diverges from the
003 replay contract (the replay logic would be duplicated). Option B reuses the
contract but requires threading the brownfield decision back into the pipeline
before Stage 4, which is a slightly tricky handoff. The human should confirm
which approach they want before implementation — it affects `pipeline.py` structure
non-trivially.

**Your lean**: Option B (reuse run_agent_phase with a filter). The 003 determinism
contract is load-bearing; duplicating the replay logic is risky.

### OQ-2 — `brownfield_skip` as a declared input on base modules: where does it live? (MED)

**Context**: Settled Decision D says brownfield emits `brownfield_skip=true` as an
answer for a base module (e.g. gitignore-generate) and that module reads it to
emit a skip result. The question is HOW it is declared.

Option A: Each base module that supports brownfield-skip adds
`[[inputs]] key="brownfield_skip" type="boolean" default=false required=false`
to its own `module.toml`. The module's `module.py` reads it via
`inputs.get_bool("brownfield_skip", False)`.

Option B: `brownfield_skip` is a runner-level convention — no declaration in
`module.toml`. The brownfield module emits it; the runner checks it before invoking
a module's steps. The module doesn't need to know.

**Lean: Option A.** It keeps skip logic inside the module (consistent with the
principle that modules are self-contained) and makes the skip behavior visible in
the manifest. Option B hides the skip in the runner and makes module behavior
depend on runner logic — the opposite of the module-encapsulation principle. The
cost is adding a `[[inputs]]` entry to ~3 base modules (git-init, license-write,
gitignore-generate); this is acceptable.

**Why it needs human input**: Option B is simpler for the runner and avoids
touching existing module files. The human should confirm whether touching existing
modules' `module.toml` is acceptable (it is backward-compatible but crosses
module-ownership boundaries that other specs may also be editing).

**Your lean**: Option A (declare in module.toml). More explicit; aligns with the
module-encapsulation principle. The ~3 module.toml edits are minor.

### OQ-3 — All-or-nothing gate vs selective acceptance (LOW)

**Context**: Settled Decision I says declining the gate clears ALL proposals.
FR-013 specifies this. But a user who agrees on `lang-python` but disagrees on
skipping `gitignore-generate` has no recourse except to decline the whole gate and
then manually re-enable via the `io.ask("enabled")` prompt.

Option A: All-or-nothing (current spec). Simpler; consistent with how other
gates work (a declined gate does not partially apply).
Option B: Multi-select per-proposal accept/decline. Richer UX; requires a new
gate UI variant (a multi-select confirm). This is out of scope for 008.

**Lean: Option A** (as specced). The escape hatch is: decline → interview runs
with no pre-fills → user manually selects modules and overrides answers at the
interview. Not ideal but workable. Multi-select gate UI is deferred.

**Why it's noted here**: if the human wants Option B, it is a significant scope
increase that requires a new gate UI primitive. Flag it explicitly.

### OQ-4 — `--no-brownfield` disable flag vs `brownfield_skip` reset (LOW)

**Context**: There is currently no way to say "I want to re-run setup but
NOT apply brownfield inference" without editing `answers.toml`. The spec says
use `--refresh brownfield-detect` (which re-scans) but that does not disable it.

Option A: No disable flag (current spec). If the user dislikes brownfield
proposals, they decline the gate. If they want to permanently disable brownfield,
they edit `answers.toml` to set `proposed_enabled = []` and `brownfield_skip=false`
for all modules.

Option B: Add `--no-brownfield` CLI flag that forces brownfield's no-op path
(bypasses Stage 3c entirely). This is analogous to `--no-external-generators` (G4).

**Lean: Option A** for this spec. `--no-brownfield` is a quality-of-life addition
that can be a small follow-up (like a spec 008a) if it proves needed in practice.
The gate decline already gives a one-time escape.

**Why it's noted here**: the human may feel strongly that a disable flag is
necessary before 008 ships. Flag it as a potential scope addition.

## ASSUMPTIONS made (flagged so they can be corrected)

1. The Stage 3c `run_brownfield_phase` approach is the minimal runner change — a
   single helper added to `pipeline.py` that calls `run_agent_phase`-style logic
   for one module before Stage 4. The 003/004 agent and gate primitives are used
   unchanged.
2. `brownfield_skip` declared on base module.toml files is backward-compatible:
   `required=false` + `default=false` means existing tests of those modules pass
   unchanged (the input is absent → default false → no skip).
3. The corroboration weight heuristic (>=2 independent signals) is sufficient for
   the prompt-injection mitigation. A more formal weight system (e.g. a TOML-driven
   signal catalog in the steering doc) is possible but not required in 008.
4. The brownfield steering doc instructs the agent to operate from a context dict
   of `{path: first_N_lines}` for each scanned file (not arbitrary full-file
   reads) to bound context size. The exact scanning approach (max lines per file,
   max files) is a steering detail, not a spec-level decision.
5. Brownfield-detect running on a non-empty repo where ALL signals point to an
   already-committed `answers.toml` (i.e. reproduce mode) is handled by the
   reproduce no-op path — the module does not re-scan on reproduce.
6. The `proposed_enabled` list emitted by brownfield only adds to the base enabled
   set — it does not remove from it. Brownfield cannot disable a base
   `default_enabled=true` module (only the `brownfield_skip` signal can cause a
   skip at the step level within an already-enabled module).

## Determinism rules (must hold, inherited from 001/002/003)

- On reproduce: brownfield's Stage 3c is a no-op; the committed `proposed_enabled`
  and `brownfield_answers` replay from `answers.toml`; zero file scan; zero agent
  call.
- On init with brownfield confirmation: the decision freezes as `agent-steered`
  answers; subsequent init re-runs (plain reproduce) replay byte-identically.
- On init with brownfield decline: no brownfield answers are written; the run is
  indistinguishable from a run where brownfield-detect does not exist.
- `--refresh brownfield-detect`: re-runs the agent step (re-scans the project
  directory), presents an old-vs-new diff gate, re-persists on confirm.

## AS-BUILT (TBD)

_To be filled in once implementation is complete._
