# Feature 006 — AGENTS.md Architecture Section (memory)

Authored in one session after reading the full house style (spec 003/004 memory and
spec files), the existing `agents-md` module, the runner SDK, the lang-python Tier-2
resolver pattern, and the roadmap entry. This file is the durable record of HOW the
spec was reasoned and WHAT needs the user's input before implementation. All facts
are verified against shipped code on `feat/project-setup-modular-redesign` at HEAD
`7779c27` unless marked otherwise.

## Scope decision (what 006 is)

006 = **extending the existing `agents-md` module with a Tier-2 agent step
(`resolve-arch`) that authors a project-specific Architecture & Conventions section,
a hard `init_only` gate (`arch-gate`), and a `kind=python` splice step — plus two
new SDK primitives (`splice_between_sentinels`, `scan_top_level_dirs`) that are
net-new.** No new module is created. No runner/executor/pipeline changes are needed.
The feature is entirely within the module and the SDK.

## Verified code facts the spec relies on

These were checked by direct read, not subagent digest. Do not re-derive.

- **The base `write` step is one `kind=python` step on `agents-md`**
  (`modules/agents-md/module.toml:39-41`). No agent/gate steps exist today.
- **The `## Architecture` placeholder is a static comment** in both templates
  (`templates/single.md:22-24`, `templates/monorepo.md:22-24`). Neither contains
  sentinel markers.
- **`idempotent_write` replaces the WHOLE file** (`runner/sdk.py:182-257`). There is
  no existing "replace-only-a-span" path. `splice_between_sentinels` is fully net-new.
- **`scan_top_level_dirs` does not exist** (`runner/sdk.py:1-657` has no directory
  scanner). Net-new.
- **Cross-module reads work today**: `sdk.load_frozen_inputs(plan_path, module_id=X)`
  simply looks up module X in the frozen plan. No restriction; already used by
  lang-python's write step.
- **The `kind=agent` Phase-A / reproduce-replay contract is in place** (spec 003
  AS-BUILT): `reproduce.run_agent_phase` replays committed `agent-steered` answers
  zero-network. The new `resolve-arch` step participates in Phase A without any
  runner changes.
- **The `init_only` gate bypass is in place** (spec 004 AS-BUILT, `runner/manifest.py:
  69-71`): `StepSpec.init_only: bool = False`. On plain reproduce, `run_gate_step`
  auto-proceeds for `init_only=True` gates. The `arch-gate` uses this exactly like
  `lang-python`'s `pins` gate (`modules/lang-python/module.toml:43-49`).
- **The `{decision}` token substitution is in place** (`runner/plan.py:159-168`):
  a gate message containing `{decision}` is expanded with `render_answer_block
  (mod_answers)` at freeze time. The `arch-gate` message uses this to show the
  agent's proposed text.
- **The 3-line `_load_sdk` shim pattern** is what all current modules use (spec 005
  OQ-1 resolved). 006 follows it.
- **`agents-md` `order.after = ["dirs-scaffold"]`** (`module.toml:15`): dirs-scaffold
  runs first, so top-level dirs are present on disk when `splice` runs.
- **The `dirs-scaffold` module runs before `agents-md`** (`module.toml:15-16`). The
  tree scan at splice-time therefore reflects the real project structure, not an
  empty dir.

## KEY DESIGN DECISION — no runner changes

The temptation was to plumb "project-wide context" (all module answers accessible
from one dict) through the runner for the agent step. That is explicitly out of scope
(spec Out of Scope). The clean pattern is:

- The agent steering doc lists exactly which frozen input keys to read and from which
  module.
- `module.py` calls `load_frozen_inputs(plan_path, "lang-python")` and
  `load_frozen_inputs(plan_path, "lang-ts")` (if enabled) to gather cross-module
  answers before invoking the agent.
- The agent receives a structured context dict (via `io.agent_step(steering_path,
  ctx)`) — not raw file reads, not the plan.json.

This is consistent with the existing `executor.run_agent_step` contract
(`executor.py:443-475`): the `ctx` dict passed to `io.agent_step` is built from the
module's resolved answers. The implementer needs to verify that the ctx dict passed
to `io.agent_step` can include cross-module answers collected by `module.py` before
the runner invokes the step — or whether the ctx is constructed solely by the runner.
See OQ-1.

## SENTINEL DESIGN

The sentinel pair chosen is:

```
<!-- BEGIN ps:architecture -->
<!-- END ps:architecture -->
```

The `ps:` namespace (`ps` = project-setup) reserves this marker for runner-authored
sections. Future specs can add `<!-- BEGIN ps:ci-matrix -->` etc. for other sections
the runner owns. The `splice_between_sentinels` SDK primitive is generic and reusable
by future specs that need the same pattern (e.g. spec 005 roadmap item for CI
matrix, rank #5).

The splice contract (what FR-001/002/003 specify):

```
[before-begin-line]
<!-- BEGIN ps:architecture -->
<body — replaced entirely by splice>
<!-- END ps:architecture -->
[after-end-line]
```

The `body` argument to `splice_between_sentinels` does NOT include the marker lines
themselves. The function handles the newlines: `BEGIN\n<body>\nEND\n` is the canonical
form. The idempotent check compares only the `body` content between the markers.

## PHANTOM-PATH GUARD — implementation note

The guard in `_do_splice` is a regex pass over `architecture_md` that looks for
Markdown table rows matching the pattern `` | `<dirname>/` `` (or similar path
patterns) and checks each dirname against `scan_top_level_dirs()`. This is heuristic
— the guard strips rows that look like path references, not all rows. The implementer
should decide the exact matching rule (see OQ-2). The spec's requirement (FR-007) is
behavioral: strip rows that reference non-existent top-level dirs, warn, proceed.

## OPEN QUESTIONS — resolved or genuinely open

### OQ-1 — How does `module.py` supply cross-module answers to the agent ctx dict? (LOW — verify before impl)

The runner's `run_agent_step` (`executor.py:443-475`) constructs the `ctx` dict from
the module's resolved answers and passes it to `io.agent_step(steering_path, ctx)`.
The question is whether the `module.py` has any pre-agent hook, or whether the ctx
must be built entirely by the runner from the frozen plan.

**Lean:** The simplest approach is to have the `resolve-arch` steering doc instruct
the agent to call the SDK's `load_frozen_inputs` for sibling module IDs via a
structured query passed in the context. Alternatively, the `resolve-arch` step's
agent context could include cross-module answers if the executor allows module-level
ctx augmentation. **Read `executor.py:443-475` in full before implementing FR-009.**
If the ctx is purely runner-constructed, the steering doc workaround is to pass
sibling-module answer keys in the context via the module's own `[[inputs]]` mirror
entries (copying the relevant answers into `agents-md`'s own input namespace before
the agent step). This is a known pattern (the agent step only ever sees the module's
own answer namespace through `ctx`).

**Resolution path:** Check whether the runner passes the whole `final_answers` dict
or only the module's slice. If it passes only the module slice, the implementer
should add `[[inputs]]` pass-through entries to `module.toml` for the framework/lang
keys (defaulting to empty strings), which the interview will populate from prior
module answers via the standard answer-propagation mechanism, or the implementer adds
a `from` key in `[[inputs]]` to alias cross-module values (if that's a runner
feature). If no aliasing exists, use `module.py` to pre-populate a combined context
dict that the steering doc can reference. This is LOW priority because it doesn't
block the spec shape.

### OQ-2 — Exact phantom-path detection rule for the path table filter (LOW)

The spec says "strip table rows that reference a top-level directory not in the
scan set." The exact matching rule matters: is it `| \`dirname/\` |` only (explicit
trailing slash), or any backtick-quoted path whose first segment is a dirname?

**Lean:** Match rows of the form `| \`<name>/` ` or `| \`<name>/... ` (first
path segment followed by `/`). Extract the first path segment, strip backticks and
leading/trailing whitespace, check against `scan_top_level_dirs()`. This covers the
standard path-table format the agent is instructed to use. False negatives (the agent
wrote `src/my-package` without backticks) are acceptable — the guard is a safety net,
not a parser.

### OQ-3 — Should `splice_between_sentinels` live in `sdk.py` or in a new `agents-md`-local helper? (LOW)

The spec places it in `sdk.py` as a shared primitive, anticipating reuse by the CI
matrix spec (rank #5) and any other spec that needs sentinel-bounded section writes.

**Lean:** `sdk.py` is the correct home. It is stdlib-only, pure Python, no module-
specific logic. Future specs that add their own sentinel-bounded sections in
AGENTS.md or other files benefit from a shared, well-tested implementation. The
function signature is generic enough to be reusable.

If the implementer prefers to keep `sdk.py` minimal, a `_sentinel.py` helper in the
runner (alongside `sdk.py`) is acceptable; `sdk.py` would then re-export it. Either
way it must be reachable via `import sdk; sdk.splice_between_sentinels(...)`.

## ASSUMPTIONS made (flagged for correction)

1. The `dirs-scaffold` ordering guarantee (Assumption in spec) is correct because
   `module.toml:15` (`after = ["dirs-scaffold"]`) is already in place. If dirs-scaffold
   is somehow not ordered before the splice step at execution time, `scan_top_level_dirs`
   would return a mostly-empty set and most path rows would be stripped. The ordering
   must be verified by the implementer.
2. HTML-comment sentinels (`<!-- BEGIN/END ps:architecture -->`) are invisible to
   Claude Code and Codex when reading AGENTS.md — they do not consume meaningful
   context tokens and do not confuse the agent guidance. If it turns out that Codex
   renders the markers visibly or agents find them confusing, the marker format should
   be changed before implementation. Test with a real AGENTS.md read.
3. The `agents-md` base `write` step currently uses `reconcile=True`
   (`module.py:89-94`). After this spec, the base write still uses `reconcile=True`
   on the WHOLE file — it will overwrite the sentinel-bounded span with the default
   placeholder template. This means:
   - On a fresh init: `write` → `resolve-arch` → `arch-gate` → `splice` is the
     correct order; the splice overwrites the placeholder markers left by `write`.
   - On reproduce: `write` (reconcile=True) re-writes the whole skeleton (potentially
     overwriting the architecture span if the on-disk AGENTS.md differs from the base
     template) → `splice` re-writes the architecture span from frozen answers.
   This is correct but requires that the `splice` step always runs AFTER `write` and
   that the base templates contain the sentinel markers (FR-008). **If `write` runs
   with reconcile=True on reproduce and the file has been user-edited OUTSIDE the
   sentinel span, the user's edits are lost.** This is an existing behavior of
   `agents-md` (it was already reconcile=True before this spec); 006 does not make it
   worse, but it is worth flagging as a pre-existing sharp edge.

## AS-BUILT (2026-06-28)

Implemented in two phases, both green.

**Phase 1 — SDK primitives (`sdk.py`):** `scan_top_level_dirs(project_dir)` (shallow,
dirs-only, hidden included, missing→empty frozenset) + `splice_between_sentinels(rel_path,
begin, end, body, *, project_dir, inspect, missing="append"|"error", warnings)` (span
replace; create/modify/skip; malformed begin-without-end → skip+warn; missing-markers →
append after `## Architecture` heading). 13 unit tests in `test_sdk_splice.py`.

**Phase 2/3 — agents-md module:** module.toml gained the resolve-arch(agent) →
arch-gate(gate, hard, allow-arch-write, init_only) → splice(python) steps + two inputs;
module.py refactored to STEP_HANDLERS dispatch (`_do_write` = the existing skeleton,
`_do_splice` = phantom-strip + splice); both templates' `<!-- ARCHITECTURE… -->`
placeholder → `<!-- BEGIN/END ps:architecture -->` sentinels; new
`steering/resolve-arch.md`. 15 tests in `test_module_agents_md.py` (SC-003 span-write,
SC-004 phantom-strip, SC-007 missing-marker append, idempotent skip, inspect-no-write).

**Deferred (honest gap):** SC-001 (agent answer flows to splice via run_pipeline),
SC-005 (reproduce zero-network byte-identical), SC-006 (--refresh / declined gate),
SC-008 (--non-interactive ±--allow-arch-write) are RUNNER-LEVEL — they need a
`run_pipeline` + ScriptedIO harness with a synthetic agents-md plugin, not the direct
`module.py --step splice` invocation `test_module_agents_md.py` uses. The underlying
machinery (Phase-A agent → freeze → gate → Phase-B python, the `init_only` reproduce
bypass, the hard-gate CI safe-skip) is ALREADY proven end-to-end by
`test_two_phase_resolver.py` for the stack resolver — agents-md uses the identical
runner path, so these SCs are covered by construction, not by an agents-md-specific
runner test. A dedicated agents-md run_pipeline test is a low-value follow-up (it would
re-prove the runner, not the module); tracked here rather than built.

Full suite stayed green (no regression from the additive sdk.py primitives + the
module extension).
