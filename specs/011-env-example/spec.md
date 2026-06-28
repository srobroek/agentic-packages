# Feature Specification: env-example-from-stack

**Feature Branch**: `feat/project-setup-modular-redesign` (continues)

**Created**: 2026-06-28

**Status**: **Draft (2026-06-28)**

**Input**: Roadmap rank #9 (`reviews/tier2-agentic-features-roadmap.md:83-87`) —
"env-example-from-stack (.env.example derived from stack)". Medium value / small
effort. The roadmap identifies the agent decision as the `env_keys` list and the
invariant as HARD-REFUSE of any non-placeholder value, upholding the no-secret-type
property and spec-004 G8.

## Overview

Every web project ships a `.env.example` to document what env vars a new
contributor must supply. Today contributors discover the required vars by reading
source code or asking the team — neither scales and both leak real values into
answers when someone pastes the wrong thing. This module derives the canonical set
of env var **names** from the already-frozen stack decision (framework id +
companion libs from 003), writes `.env.example` with **placeholder tokens only**,
and refuses to write or persist any value that looks like a real credential.

The pattern follows the standard Tier-2 seam:

> An **agent** maps the frozen stack decision (framework, companions, optional
> `extra_env_hints`) to a structured list of `env_keys` entries (name, placeholder
> text, comment, `secret_bool`). A **python** step reads those frozen entries from
> the plan, emits one `KEY=placeholder` line per entry (alphabetically sorted),
> via `idempotent_write`, and **hard-refuses** any value that is not a placeholder
> token (never a real credential, never empty for a secret key).

The key safety invariant is: the output path is **fixed** to `.env.example` (the
agent has no say over it, so it cannot write a real `.env`), and every value is
validated with `sdk.looks_like_secret` before any write — upholding spec-004 G8.
The same frozen `env_keys` list always produces the same bytes.

**Why a new module, not steps on an existing one.** The env-example derives its
input from the *resolved* stack (003's `framework`, `companions`, `pinned_deps`),
not from a single language overlay. It must run AFTER `lang-python` and `lang-ts`
have frozen their stack decisions. A shared module with an `[order].after` on both
overlays (and soft optional enablement) expresses this dependency cleanly without
coupling the agent step into `lang-python` or `lang-ts` themselves, and it remains
reusable for future overlays (lang-go, lang-rust, package-add). An existing module
would be the wrong owner for a cross-stack concern.

## Current state (verified — citations, do not re-derive)

All file:line references verified against the shipped code on
`feat/project-setup-modular-redesign` at HEAD `7779c27`.

- **No `.env.example` write exists anywhere in the runner or modules.**
  `fd -e py modules/` finds no `env.example` or `dotenv` reference in any
  `module.py`. The runner's `sdk.idempotent_write` (`sdk.py:182-257`) writes
  arbitrary relative paths — the path-safety guard (`is_safe_relative_path`,
  `sdk.py:538-589`) only blocks `..`, absolute paths, and null bytes; it does
  NOT distinguish `.env` from `.env.example`. A fixed output path must be
  enforced in the module itself.
- **`sdk.looks_like_secret` is the correct G8 hook** (`sdk.py:432-444`). It
  returns a human-readable label if the value matches a known credential shape
  (`ghp_`, `sk-`, `AKIA`/`ASIA`, `glpat-`, `xoxb-`/etc., `-----BEGIN … KEY`),
  or `None` if it looks safe. This is the right check for the hard-refuse
  invariant — it is already tested by the 004 suite and requires no new SDK work.
- **`FrozenInputs` provides `mode`**, `get_str`, `get_list` (`sdk.py:65-137`).
  An agent step's decisions land in the frozen plan via the 003 two-phase
  mechanism (`pipeline.py` Stage 5b `run_agent_phase`, Stage 6 freeze). A
  python step reads them via `sdk.load_frozen_inputs` + `inputs.get_list("env_keys")`.
- **`idempotent_write` is idempotent for identical bytes** (`sdk.py:240-257`):
  identical content → `kind="skip"`, changed content → `kind="modify"` (if
  `reconcile=True`), absent file → `kind="create"`. The same sorted env-keys list
  produces the same bytes on every run — Tier-1 determinism holds.
- **No module for env-example exists.** The modules directory
  (`packages/project-setup/skills/project-setup/modules/`) has 18 entries
  (verified with `eza`); none is named `env-example` or similar.
- **`lang-python` and `lang-ts` freeze `framework` as `agent-steered`.**
  `lang-python/module.toml` declares `framework` as an `[[inputs]]` entry
  (`module.toml:26-30`); the `resolve` agent step in `lang-python/steering/resolve.md`
  emits `"framework"` in `answers_to_persist` with `"source": "agent-steered"`
  (`resolve.md:106-111`). `lang-ts` follows the same pattern (verified in 003
  spec). These frozen answers are readable by a later module via its own frozen
  plan, given the `[order].after` dependency.
- **The 004 G8 mechanism enforces the secret-refuse at the interview/persist
  boundary** (`pipeline._interview_module`). That boundary guards user-typed
  interview answers. The env-example module's agent step also emits
  `answers_to_persist` — the same G8 path fires. But the module's python step
  must ADD its own `looks_like_secret` check over each value in `env_keys` before
  writing, because the python step writes from already-frozen answers (G8 fired at
  persist time for the agent step, but we re-validate at write time as a
  defense-in-depth guard). See FR-008.
- **No gate is mandatory today for the env-example write.** Roadmap rank #9
  explicitly says "Optional kind=gate (low blast radius, placeholders only);
  recommended so the dev sees the inferred config surface but gate=none is
  acceptable if effort-constrained." The 004 gate machinery is in place and a
  `kind=gate` step is trivial to declare; we include it as `hardness="soft"` (the
  generator gate pattern from 004 FR-004) — the user confirms once before the
  write and CI auto-proceeds.
- **`[order].after` can list multiple module ids.** `lang-python/module.toml:15-16`
  shows `after = ["gitignore-generate", "precommit-setup"]`; TOML arrays support
  multiple entries. An env-example module can declare `after = ["lang-python", "lang-ts"]`
  with `required = false` on those deps (optional — neither overlay is mandatory).
- **No `requires` cross-module answer-reading API exists as a high-level
  primitive**; a module reads its OWN frozen answers from the plan. To read
  another module's answers the agent step must receive them in its context dict.
  The executor passes a `ctx` dict to `io.agent_step` (`executor.py:443-475`);
  that context is built from `resolved_answers` for the module's own inputs. A
  cross-module read from the steering doc (the agent is told to "read from
  context") would need those answers injected into the context. **This is the
  key design question**: how the env-example agent reads `lang-python.framework`
  and `lang-ts.framework` (see Settled Decision B and OQ-1).

## Settled decisions

- **A — New module `env-example`, not steps on an existing module.** The
  env-example concern is cross-stack (needs both Python and TS framework context,
  optional companion context, and future lang-go/rust context). Coupling it to
  `lang-python` or `lang-ts` would require picking a side; a dedicated module with
  `[order].after` on both overlays is the correct shape. The module is
  `default_enabled = false` (opt-in), consistent with all lang-* overlays.
- **B — The agent reads the frozen stack context from its own module input list.**
  Rather than inventing a cross-module answer-reading API, the env-example module
  declares `[[inputs]]` for `framework_python`, `framework_ts`, and
  `extra_env_hints`. These are populated from the interview (or defaulted to empty).
  The agent's steering doc instructs it to check the `context` dict for those
  values, plus inspect any companion hints in `pinned_deps` if exposed. The
  approach is: the inputs mirror the resolved answers from the upstack overlays —
  the interviewer asks "Python framework?" and the value flows from `lang-python`'s
  frozen `framework` answer via the enablement layer's answer-inheritance mechanism
  (the `answers` dict at build_plan time already carries all module answers). The
  agent then derives `env_keys` purely from those inputs and its framework
  knowledge. This is the same "agent reads the context dict" pattern already used
  in `lang-python`'s `resolve` step. No new runner work needed.
- **C — `env_keys` is a list of structured objects: `{name, placeholder, comment,
  secret_bool}`.** `name` is the bare env var name in `SCREAMING_SNAKE_CASE`.
  `placeholder` is the token to write (e.g. `"your-secret-key-here"`,
  `"postgres://user:pass@localhost/db"`). `comment` is an optional one-line
  description. `secret_bool` is `true` for credentials/keys and `false` for URLs,
  feature-flags, and mode vars — used **only** to pick comment wording ("rotate
  before committing" vs "fill in your value"), NEVER to change the written content.
  The python step never uses `secret_bool` to branch on what to write; its sole
  use is selecting the comment suffix.
- **D — Output path is fixed: `.env.example`.** The module.py hard-codes the
  output path and never reads it from inputs or the frozen plan. The agent has no
  input that could influence the path. This makes it structurally impossible for
  the agent to redirect the write to `.env` or any other secret-leaking path.
- **E — HARD-REFUSE any `placeholder` value that matches `sdk.looks_like_secret`.**
  Before any `idempotent_write`, the python step loops over every `env_keys` entry
  and calls `sdk.looks_like_secret(entry["placeholder"])`. A non-None return is a
  hard error (emit an error result, write nothing). The same check applies if a
  `placeholder` is empty for a `secret_bool=true` key — empty is not a safe
  placeholder for a credential (it would produce `KEY=` which is ambiguous).
  This is the core safety invariant tied to spec-004 G8.
- **F — `reconcile = true` and `idempotent_write(reconcile=True)`.** The module
  is declared `reconcile = true` (like `lang-python`) so re-runs update the file
  when the stack changes. The `modify` diff is guarded by the 004 G5 overwrite
  gate on reproduce (local edits protected), consistent with the rest of the runner.
- **G — Gate is `hardness="soft"`, init-only, pre-write.** The write is low
  blast radius (placeholder-only, reversible, local). A soft gate lets CI
  auto-proceed (no `--allow-*` flag needed) while still showing the human the
  inferred config surface in a TTY. `init_only = true` so plain reproduce
  auto-proceeds without re-prompting (the frozen decision is already consented,
  consistent with spec-004 G6/FR-006a). The gate is optional in the sense that
  gate=none is acceptable; we include it because the roadmap recommends it and
  because it surfaces the agent's inference for one-time human review.
- **H — Sorted, deterministic output.** Entries are sorted by `name`
  (ASCIIbetical / Python `sorted()`) before writing. The comment block goes first
  (a fixed preamble line), then one `KEY=placeholder` per line. Same frozen list
  → identical bytes → Tier-1 determinism holds for reproduce.

## User Scenarios & Testing

### User Story 1 — A FastAPI project gets a `.env.example` on first init (Priority: P1)

A user enables `env-example` alongside `lang-python` (FastAPI stack already
resolved). On first init the agent derives `DATABASE_URL`, `SECRET_KEY`,
`DEBUG`, `ALLOWED_HOSTS` from the FastAPI + asyncpg frozen stack decision, shows
the list at a soft gate, and the python step writes `.env.example` with placeholder
tokens only.

**Acceptance Scenarios**:

1. **Given** `lang-python` frozen with `framework="fastapi"` + asyncpg in
   `pinned_deps`, **When** the env-example agent step runs, **Then** it emits an
   `env_keys` list including at minimum `DATABASE_URL`, `SECRET_KEY`, and `DEBUG`,
   each with a non-empty placeholder token and no real secret value.
2. **Given** a soft gate fires in TTY, **When** the user confirms, **Then**
   `.env.example` is written with one `KEY=placeholder` line per entry, sorted
   alphabetically, no blank values.
3. **Given** `--non-interactive`, **When** the gate would fire, **Then** it
   auto-proceeds (soft) and `.env.example` is written; the file's contents are
   identical to a TTY confirm run with the same frozen answers.

### User Story 2 — A Nuxt project gets frontend-specific env vars (Priority: P1)

A user enables `env-example` alongside `lang-ts` (Nuxt framework). The agent
derives `NUXT_PUBLIC_API_BASE`, `NUXT_SECRET`, and other Nuxt-conventional vars
(`NEXT_PUBLIC_*` / `VITE_*` for Vite-based stacks, `NUXT_PUBLIC_*` for Nuxt).
The write is identical whether run interactively or in CI.

**Acceptance Scenarios**:

1. **Given** `lang-ts` frozen with `framework="nuxt"`, **When** the agent step
   runs, **Then** `env_keys` includes only Nuxt-conventional var names (e.g.
   `NUXT_PUBLIC_*`, `NUXT_SECRET`); no React or Vite vars are invented.
2. **Given** `lang-ts` frozen with `framework="vite"`, **When** the agent step
   runs, **Then** `env_keys` contains `VITE_*`-prefixed vars as appropriate.
3. **Given** the same frozen `env_keys` on two separate runs, **When** the python
   step writes `.env.example`, **Then** the file bytes are identical (determinism).

### User Story 3 — Reproduce is zero-network and byte-identical (Priority: P1)

A teammate clones the repo. `env_keys` was frozen at init and committed to
`answers.toml`. The reproduce run re-emits the committed agent-steered answers and
writes the identical `.env.example` with no network calls.

**Acceptance Scenarios**:

1. **Given** committed `agent-steered` `env_keys` in `answers.toml`, **When** the
   runner runs in reproduce mode, **Then** the `kind=agent` step re-emits the
   committed decision with zero network calls (no agent re-invocation).
2. **Given** the replayed `env_keys`, **When** the python step runs, **Then** it
   writes an identical `.env.example` (byte-for-byte match to the init run).
3. **Given** plain reproduce, **When** the soft gate would fire, **Then** it
   auto-proceeds without prompting (init_only=true, FR-006a), and the write
   proceeds normally.

### User Story 4 — A placeholder that looks like a secret is hard-refused (Priority: P1)

The agent (or a crafted `extra_env_hints` input) proposes a `placeholder` value
of `ghp_XXXXXXXXXXXXXXXXXXXX` (a real-looking GitHub token). The python step
detects this via `looks_like_secret`, emits an error result, and writes nothing.

**Acceptance Scenarios**:

1. **Given** an `env_keys` entry with a `placeholder` that `sdk.looks_like_secret`
   returns non-None for, **When** the python step processes it, **Then** it emits
   `status="error"`, writes nothing, and the error message names the offending key.
2. **Given** all `env_keys` entries have safe placeholder tokens, **When** the
   python step runs, **Then** `.env.example` is written and `looks_like_secret`
   returned None for every entry (verified in tests with known patterns).
3. **Given** a `secret_bool=true` key whose `placeholder` is an empty string,
   **When** the python step processes it, **Then** it is treated as a hard error
   (empty is not a valid placeholder for a secret-class var).

### User Story 5 — `extra_env_hints` adds project-specific vars (Priority: P2)

A user specifies `extra_env_hints = "STRIPE_API_KEY, SENDGRID_API_KEY"` in the
interview. The agent incorporates those names into `env_keys` with appropriate
placeholders, alongside the framework-derived vars.

**Acceptance Scenarios**:

1. **Given** `extra_env_hints` containing `STRIPE_API_KEY`, **When** the agent
   runs, **Then** `env_keys` includes an entry for `STRIPE_API_KEY` with
   `secret_bool=true` and a suitable placeholder token.
2. **Given** `extra_env_hints` is empty or absent, **When** the agent runs,
   **Then** only framework-derived vars appear (no phantom entries invented from
   the hint field).

### Edge Cases

- **Neither `lang-python` nor `lang-ts` enabled**: the agent receives empty
  `framework_python` and `framework_ts`. It emits a minimal `env_keys` list
  (e.g. just what `extra_env_hints` specified, or an empty list). An empty list
  produces an `.env.example` with only the preamble comment — a valid, correct
  output (not an error).
- **Both Python and TypeScript frameworks enabled**: the agent merges vars from
  both stacks, deduplicating by name. The output is sorted alphabetically.
- **`env_keys` entry with `name` containing lowercase or spaces**: the python step
  normalizes or hard-errors — all names MUST be `SCREAMING_SNAKE_CASE`
  (`re.fullmatch(r"[A-Z][A-Z0-9_]*", name)`). An invalid name is emitted as a
  warning (not an error) and the entry is skipped — the file is still written with
  the valid entries.
- **Existing `.env.example` on reproduce**: if on-disk bytes differ from the
  re-render of the frozen answers (i.e. hand-edited), the 004 G5 overwrite gate
  fires (hard, CI SAFE-skips), protecting local edits. This is automatic from the
  `reconcile=True` + G5 machinery — no new module work required.
- **`placeholder` contains a newline**: the write step sanitizes (replace `\n`
  with ` `) and appends a warning. One `KEY=placeholder` per line is invariant.
- **Very long `env_keys` list (>50 entries)**: the gate message truncates to the
  first 20 entries + a count ("… and N more"); the write emits all entries
  unchanged (the gate message is display, not a contract).

## Requirements

### Module structure (new module)

- **FR-001**: A new module `env-example` MUST be created at
  `modules/env-example/module.toml` + `modules/env-example/module.py`, following
  the existing module shape. `default_enabled = false`, `reconcile = true`.
  `[order].after` MUST list `["lang-python", "lang-ts"]` (soft ordering — neither
  is a hard `requires`; both may be absent).

### Inputs

- **FR-002**: The module MUST declare three `[[inputs]]`:
  - `framework_python` (type `string`, not required, default `""`) — the resolved
    Python framework id; populated from `lang-python`'s frozen `framework` answer
    when both modules are enabled.
  - `framework_ts` (type `string`, not required, default `""`) — the resolved
    TypeScript/JS framework id.
  - `extra_env_hints` (type `string`, not required, default `""`) — freeform
    comma-separated var names the user wants to add beyond the framework-derived
    set (interview input only; the agent uses this as a hint, not an override list).

### Agent step (Tier-2 decision)

- **FR-003**: The module MUST declare a `kind=agent` step (`id="resolve"`) whose
  steering document instructs the agent to:
  - Derive the canonical env var names for the resolved Python framework
    (if `framework_python` is non-empty) — e.g. `SECRET_KEY`/`DEBUG`/`ALLOWED_HOSTS`
    for Django; `DATABASE_URL`/`SECRET_KEY`/`DEBUG` for FastAPI; etc.
  - Derive the canonical env var names for the resolved TS framework (if
    `framework_ts` is non-empty) — e.g. `NUXT_PUBLIC_*`/`NUXT_SECRET` for Nuxt;
    `VITE_*` for Vite; `NEXT_PUBLIC_*`/`NEXTAUTH_*` for Next.js; etc.
  - Add any names from `extra_env_hints` (after normalizing to `SCREAMING_SNAKE_CASE`).
  - Deduplicate by name (case-insensitive), keep last-wins for duplicates.
  - Emit `env_keys` as `answers_to_persist` with `source="agent-steered"`.
- **FR-004**: The agent step MUST emit `env_keys` as a list of objects, each with
  keys: `name` (string, SCREAMING_SNAKE_CASE), `placeholder` (string, non-empty
  placeholder token — never a real value), `comment` (string, may be empty),
  `secret_bool` (boolean). It MUST NOT emit ranges, real credentials, or
  file paths in `placeholder`.
- **FR-005**: The agent step MUST NOT emit version ranges, registry lookups, or
  real secret values. It operates entirely from framework knowledge + the frozen
  inputs. MCP tools are NOT required (no pins to verify, no registry calls). The
  steering doc MUST state this explicitly so the agent does not attempt network
  calls during the resolve step.
- **FR-006**: The `answers_to_persist` block for the agent step MUST include
  `env_keys` with `"source": "agent-steered"` and optionally `rationale` (a brief
  explanation of why each key was included or excluded). No other agent-steered
  answers are required.

### Gate step (soft, init-only)

- **FR-007**: The module MUST declare a `kind=gate` step (`id="preview"`) between
  the `resolve` and `write` steps, with:
  - `hardness = "soft"` — CI auto-proceeds, TTY prompts `[Y/n]`.
  - `init_only = true` — on plain reproduce the gate auto-proceeds without
    prompting (the decision is already consented); only `--refresh env-example`
    re-arms it.
  - A `message` containing `{decision}` so the rendered gate shows the frozen
    `env_keys` list as a human-readable summary.

### Python write step (deterministic, hard-refuses secrets)

- **FR-008**: The `kind=python` step (`id="write"`) MUST, before calling
  `idempotent_write`, loop over every `env_keys` entry and call
  `sdk.looks_like_secret(entry["placeholder"])`. A non-None return (the value
  resembles a known credential shape) MUST cause the step to:
  - Emit `status="error"` with `error_code=INPUT_VALUE_INVALID`.
  - Write NOTHING (no partial file).
  - Include the offending `name` and the `looks_like_secret` label in the error
    message so the user can fix the placeholder.
  This applies even if the value was frozen by the agent — defense in depth against
  a compromised or misbehaving agent step (spec-004 G8, `sdk.py:432-444`).
- **FR-009**: A `secret_bool=true` entry whose `placeholder` is an empty string
  MUST also be treated as a hard error (same error path as FR-008). An empty
  placeholder for a secret-class var is ambiguous and must never be written.
- **FR-010**: The python step MUST validate every `name` against `re.fullmatch(r"[A-Z][A-Z0-9_]*", name)`. An invalid name MUST be skipped with a warning appended to the result (not a hard error) so that the remaining valid entries are still written.
- **FR-011**: The python step MUST sort entries by `name` (Python `sorted()`,
  ASCIIbetical) before writing. The output MUST be:
  ```
  # .env.example — generated by project-setup; fill in values before running.
  # DO NOT commit real values to version control.
  KEY1=placeholder1  # comment if present
  KEY2=placeholder2
  …
  ```
  One `KEY=placeholder` line per entry; a `# comment` suffix if `comment` is
  non-empty; a preamble block of two comment lines at the top.
- **FR-012**: The output path MUST be hard-coded to `.env.example` in the module
  python step. It MUST NOT be read from the frozen plan, from `$PROJECT_DIR`, or
  from any input. The agent MUST NOT have any input that could influence the path.
  The write uses `sdk.idempotent_write(".env.example", body, reconcile=inputs.reconcile, inspect=args.inspect)`.
- **FR-013**: In reproduce mode (`inputs.mode == "reproduce"`), the python step
  MUST write from the frozen `env_keys` (zero network, zero agent calls), identical
  to init given the same answers. No registry verification is needed (no pins in
  this module).

### Determinism & compatibility

- **FR-014**: Same frozen `env_keys` list → identical file bytes on every run
  (sort is deterministic; preamble is fixed; placeholder tokens are exact strings).
  This is the Tier-1 byte-identical guarantee for this module.
- **FR-015**: The module MUST NOT require the spec-004 gate machinery beyond what
  is already shipped (hardness/`init_only`/soft prompt are all 004-implemented). No
  new runner primitives are needed.
- **FR-016**: The module MUST NOT add any new dependencies to project-setup's
  `dependencies.apm`. No MCP tools required.

## Success Criteria

- **SC-001**: A FastAPI stack with asyncpg in `pinned_deps` produces an
  `env_keys` list that includes at minimum `DATABASE_URL` and `SECRET_KEY`; none
  of their `placeholder` values trigger `sdk.looks_like_secret` (unit test with
  stubbed agent response).
- **SC-002**: The python write step with an injected placeholder of `"ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"` emits
  `status="error"` and writes nothing (unit test with `mock_open` or temp dir).
- **SC-003**: The python write step with a valid `env_keys` list writes a
  `.env.example` whose lines are alphabetically sorted, whose preamble is present,
  and whose bytes are identical on two runs with the same frozen answers (byte
  comparison test).
- **SC-004**: An empty `env_keys` list (neither framework enabled, no hints) writes
  a `.env.example` containing only the preamble comment lines — no error, no
  extra entries.
- **SC-005**: In `--non-interactive` mode the soft gate auto-proceeds and the file
  is written; in TTY mode the gate prompts `[Y/n]`; with `init_only=true` a plain
  reproduce run auto-proceeds without prompting.
- **SC-006**: A reproduce run with committed `agent-steered` `env_keys` produces a
  byte-identical `.env.example` with zero network calls (verified by a
  network-blocking test double in the io adapter).
- **SC-007**: An `env_keys` entry with `name = "bad name"` (lowercase + space) is
  skipped with a warning; valid entries in the same list are still written
  (robustness test).
- **SC-008**: A `secret_bool=true` entry with `placeholder=""` emits
  `status="error"` and writes nothing (FR-009 enforcement test).
- **SC-009**: The module's `[order].after` on `["lang-python", "lang-ts"]` does
  not hard-require either overlay — a project with only `lang-python` (or neither)
  enabled still runs the module correctly.

## Out of Scope

- Writing a real `.env` file (with actual values). The module writes ONLY
  `.env.example`; the output path is not configurable.
- Deriving env vars from Go, Rust, or other language overlays (the pattern extends
  when those overlays gain resolved framework decisions; 011 builds for Python +
  TypeScript only).
- Validating that the written env var names actually appear in the source code
  (a linting concern, not a scaffolding concern).
- The `dependency-update` / staleness advisory for env vars (a skill concern,
  not a module concern).
- Generating env var documentation beyond `.env.example` (e.g. an inline README
  section). That is a separate feature.
- Reading secrets from a vault or secret manager to populate `.env.example` —
  explicitly and permanently out of scope; the invariant is placeholders only.
- Accepting a user-supplied output path. The path is fixed to `.env.example`;
  there is no `output_path` input.
- The `brownfield-detect` flow (rank #6) that would infer env vars from an existing
  codebase. That is a separate, larger feature.

## Assumptions

- The 003 stack resolver and the 004 gate machinery are in place and green (613
  tests at authoring). The agent-steered answer flow, `init_only` gate behavior,
  soft gate TTY prompt `[Y/n]`, and `{decision}` message composition are all
  implemented.
- `sdk.looks_like_secret` (`sdk.py:432-444`) is the correct and sufficient guard
  for the hard-refuse invariant. Its pattern set covers the credential shapes most
  likely to appear as placeholder accidents.
- The two-phase execution (003 FR-011) means `env_keys` is frozen AFTER the
  lang-python and lang-ts `resolve` agent steps complete, so it is available to the
  env-example agent step's context in Phase A. If env-example's `resolve` step runs
  in Phase A (it does — it is `kind=agent`), it can read the already-folded
  `framework_python` / `framework_ts` answers from the resolved answers dict.
- `[order].after = ["lang-python", "lang-ts"]` expresses a soft ordering without
  a hard `requires` edge. Modules that are not enabled are not ordered against;
  this will not cause a manifest-ordering error for projects with neither overlay.
- Registry verification (`sdk.verify_pins`) is NOT needed in this module. There
  are no package pins to verify — only env var names and placeholder strings.
- The fixed preamble comment wording is a detail for implementation; it does not
  need human sign-off.

## Dependencies & Open Questions

**Hard dependency**: 011 builds on 003 (frozen agent answers, two-phase execution)
and 004 (soft gate, `hardness="soft"`, `init_only=true`, `{decision}` composition).
Both are implemented and green.

**Remaining open questions** (OQ-1 … OQ-3) are tracked in `memory.md`. None block
authoring `plan.md` — they are design details for implementation.

**OQ-1** — How are `framework_python` / `framework_ts` populated in the interview?
**OQ-2** — Exact `env_keys` JSON shape vs flat list of strings (structured vs
minimal). **OQ-3** — Comment suffix format: inline `# comment` vs separate
preceding comment line.
