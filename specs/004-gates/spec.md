# Feature Specification: Gates & Review Checkpoints

**Feature Branch**: `feat/project-setup-modular-redesign` (continues) → likely a
dedicated `feat/gates` branch

**Created**: 2026-06-28

**Status**: **Draft (2026-06-28)** — authored after 003 shipped, folding
`specs/002-agentic-features/gates-analysis.md` (the eight-gate calibration) into a
buildable spec. Scope confirmed by the user: **all eight gates G1–G8**, nothing
deferred. The gate primitive, the two-phase plan, the gate-blocking `apply`, and
the init inspect→confirm→write path that 004 builds on are all **already shipped
and green** (003 + the f1e7269 init-confirm fix); 004 is **enrichment + four new
subsystems**, not a rewrite. Open questions (OQ-1 … OQ-7, all design-detail) are in
`memory.md`; none block authoring `plan.md`.

**Input**: `specs/002-agentic-features/gates-analysis.md` — the grounding survey
that enumerated eight gates ranked by blast radius, the blast-radius→hardness
mapping, the CI/non-interactive policy, and the anti-patterns. 003 deliberately
shipped on the **bare** `kind=gate` primitive and flagged the rich gate as 004
(003 spec Out of Scope; `memory.md` Assumption 1). This is that spec.

## Overview

The 001 migration built the generic runner + modules. The 002 enablement layer
added agent-led module selection. The 003 stack-resolver shipped the first Tier-2
module and, in doing so, declared the first real `kind=gate` step — the pin-table
gate — on the **bare** gate primitive: a single `message` string, `io.confirm`
(default No), and a non-interactive SAFE-skip (since f1e7269). 003 explicitly left
the *rich* gate machinery to 004.

This feature implements the eight-gate calibration from `gates-analysis.md`. It has
two halves:

> **The foundation** — gate steps gain a `hardness` field (`hard` | `soft` |
> `informational`) and per-action opt-in/opt-out flags, so the non-interactive
> resolver is **data-driven** (read from the frozen plan) instead of the one
> hardcoded "always SAFE-skip" rule in `run_gate_step` today. A conditional `when`
> predicate lets a gate fire only for the consequential case (public repo, not
> private).
>
> **Eight gates** — G1 whole-plan preview, G2 batched supply-chain install, G3
> public-repo-creation, G4 external-generator run, G5 destructive-overwrite, G6 the
> upgraded Tier-2 pin-review, G7 cross-module conflict, G8 secret-detected abort.

The governing constraint is **anti-fatigue**: a run that does only reversible,
local, deterministic writes must be confirmable in ONE gate (G1) and must never
deadlock CI. Hardness is assigned by the worst attribute of the action (the
three-axis blast-radius rule), and at most **one** hard gate fires per blast-radius
class per run, batched where they share a class.

**Why this matters now (the verified gap 002 named).** On a fresh project today,
the **init** path runs every step with no aggregate review (`pipeline.py` init
branch), so github-repo creates the repo and apm-install installs N packages with
a per-file write-confirm but **no whole-picture checkpoint and no supply-chain
batch confirm**. Gates have **no hardness data** — `run_gate_step` resolves *every*
non-interactive gate to SAFE-skip, which is correct for a hard gate but wrong for a
soft one (it would skip an opt-in language scaffold the user clearly wants in CI).
004 closes both: the aggregate preview (G1) and the hardness-driven resolver.

## Current state (verified — citations, do not re-derive)

All file:line references verified against shipped code on
`feat/project-setup-modular-redesign` at authoring (HEAD `7779c27`).

- **The gate-step shape is bare.** `StepSpec` (`runner/manifest.py:68-73`) is
  `{id, kind, steering, message}` — no `hardness`, no flags. The parser
  (`manifest.py:447-473`) validates only that a `kind=gate` step has a `message`.
  Plan serialization (`plan.py:151-169`) explicitly **"keeps only
  id/kind/steering/message"** when freezing — so any new field must be threaded
  through *both* the parser and this serializer or it is silently dropped.
- **The non-interactive resolver is one hardcoded rule.** `run_gate_step`
  (`executor.py:409-450`) renders the message, and in `non_interactive` mode
  **always** SAFE-skips (`return False`, `executor.py:443-449`) without consulting
  any per-gate data. This is the correct default for a *hard* gate but cannot
  express *soft* (proceed-in-CI) or *informational* (never-prompt) without the
  hardness field. TTY mode always prompts via `io.confirm` (`[y/N]`, default No —
  `io_adapter.py:146-156`); there is no `[Y/n]` soft variant.
- **Gate-blocking apply already works (003 FR-012).** `reproduce.apply`
  (`reproduce.py:262-343`) sets a module-scoped `gate_blocked` flag on a declined
  gate (`reproduce.py:319-324`) that skips the module's subsequent `kind=python`
  writes (`reproduce.py:277-283`). 004 reuses this unchanged — a declined hard gate
  already blocks the write it guards.
- **`{decision}` token composition exists (003 SUBTLETY 1).** `build_plan`
  (`plan.py:159-168`) replaces a `{decision}` literal in a gate message with
  `render_answer_block(mod_answers)` at freeze time. G6 builds on this — the
  upgraded pin gate enriches the *message* (verify-status + rationale + sources),
  not the gate *shape* beyond hardness/flags.
- **Init now uses inspect→confirm→write (f1e7269).** `run_pipeline` Stage 7
  (`pipeline.py:517-539`) runs `build_drift_report` + `apply_reproduce` for both
  modes (Stage 5b `run_agent_phase` + Stage 6 freeze precede it at
  `pipeline.py:488-515`), so the inspect pass — the data G1 needs — already runs in
  init. G1 must **aggregate and show it before the writes**, not generate new
  previews.
- **The gate fires UNCONDITIONALLY in `apply`, on every mode.** `reproduce.apply`
  runs `run_gate(step_dict, mod_id, io, non_interactive=…)` for every `kind=gate`
  step with **no init/reproduce check** (`reproduce.py:319-321`). So on a plain
  *interactive* reproduce the pin-table gate **re-prompts the user**, and in CI it
  SAFE-skips → `gate_blocked` → skips the manifest re-write. 003 implemented the
  *agent-step* zero-network replay (003 FR-009) but **never suppressed the gate
  prompt**. Making the pin gate "init-only" (bypassed on plain reproduce) is
  therefore **new 004 work** (gates-analysis §3 requirement 5), not a 003-preserved
  fact — see Settled Decision G + FR-003/FR-014.
- **G3 — public-repo creation is ungated + irreversible.**
  `github-repo/module.py:178` sets `visibility = "--public" if public else
  "--private"` and runs `gh repo create … --source .`; the `public` answer is an
  interview input. The inspect branch emits `would create GitHub repo <full>`
  (`module.py:155-156`); the skip path prints the manual `gh` command
  (`module.py:125`). There is no confirm before a world-visible namespace claim.
- **G2 — apm-install is the supply-chain surface.** `_BASELINE_MCP`
  (`apm-install/module.py:36`) is hardcoded; the package list is
  `[agentic_packages] + _BASELINE_MCP` (`module.py:148-149`); it runs
  `apm install --target claude,codex,agent-skills <packages>` (`module.py:151-181`),
  each package executing arbitrary code/hooks. The `agentic_packages` interview
  string is **prepended unvalidated**. Inspect emits `would run: <install_cmd_str>`
  (`module.py:155-160`); skip prints the manual command. No batch confirm exists.
- **G4 — lang-* runs external scaffolders inside the write step.** lang-ts runs
  `nuxi@latest init`, `create-vite`, `bun init`, then `bun/pnpm install`
  (`lang-ts/module.py`, ~lines 147-212 per 003 spec). These reach the network and
  mass-write files from a generator the runner does not control. They are **not a
  separate step** today — to gate the scaffolder while keeping deterministic writes
  (the G4 requirement), the write must be split.
- **G8 — the secrets guardrail is prose-only.** `SKILL.md:125-130` ("Secrets
  guardrail (non-negotiable)") instructs the *agent* never to accept/persist a
  secret. It is **not an enforced checkpoint** — nothing in `io_adapter.py`
  (`ask`/`ask_non_interactive`, `:136`) or the persist path matches secret shapes
  or refuses to write them. A pasted `ghp_…` PAT would be persisted to
  `answers.toml`.
- **G5/G7 have no machinery at all.** Reproduce's per-file confirm
  (`reproduce.apply`) does not distinguish "append to an untouched file" from
  "overwrite your hand-edits" (G5). The validate-closed gate (`validate.py`) covers
  missing/requires/cycle/tools but **not** semantic write-collisions on shared files
  across modules (G7). Both are net-new detection.

## Settled decisions

These are binding for this spec. Letters continue a fresh A-series (per-feature, as
003 did).

- **A — The gate-step shape gains `hardness` + opt-in/opt-out flags; the bare gate
  defaults to `hardness="hard"`.** `StepSpec` (`manifest.py`) grows
  `hardness: "hard" | "soft" | "informational"` (default `"hard"`) and two optional
  flag names: `allow_flag` (hard gates: the CLI flag that opts INTO performing the
  action in CI) and `skip_flag` (soft gates: the `--no-…` flag that opts OUT). The
  default `"hard"` makes every gate 003 already declared behave **exactly as today**
  (SAFE-skip in CI) — 004 is backward-compatible by construction. There is **no
  `"none"` hardness value**: "no gate" = no gate step (or a `when`-dropped one,
  Decision D).
- **B — The non-interactive resolver is data-driven by hardness + the active flag
  set.** `run_gate_step` stops hardcoding SAFE-skip and instead resolves from the
  frozen plan's `hardness`/`allow_flag`/`skip_flag` against the CLI flags passed
  down from `cli.py`. The resolution (the CI policy table, gates-analysis §3):
  **hard** → SAFE-skip unless its `allow_flag` is active; **soft** → proceed unless
  its `skip_flag` is active; **informational** → print and proceed, never prompt. No
  path calls `input()` in non-interactive mode (the deadlock the analysis named).
- **C — Per-action opt-in flags only; never a global "yes-to-all".** CI opts into a
  specific hard action with a named flag (`--allow-public-repo` for G3,
  `--allow-install` for G2, `--allow-stack-write` for G6); soft gates opt out with
  `--no-external-generators` (G4). A blanket `--yes`/`--confirm-all` is a **binding
  non-goal** (gates-analysis anti-pattern 5: it collapses the hardness distinction
  and auto-approves the public repo, the install, and the pin write together).
- **D — Conditional gates via a `when` predicate, evaluated at plan-build against
  the module's frozen answers.** A gate step MAY carry `when` — a minimal predicate
  (`key`, `key == value`, `key != value`) over the module's resolved answers. At
  `build_plan` the predicate is evaluated; **false → the gate step is dropped from
  the frozen plan**. This is how G3 is "hard for public, **none** for private"
  (`when = "public == true"`) without a fourth hardness value or per-module branching
  in the executor. Evaluation is deterministic (answers are frozen), so reproduce
  drops/keeps the same gates init did.
- **E — G1 is generated from the SAME inspect code path; it is visibility, not a
  blocker.** The whole-plan preview reuses the existing `build_drift_report` inspect
  pass (already run in init since f1e7269) and the modules' own `would …` preview
  strings — **never** a parallel hand-written literal (the gates-analysis G1 failure
  mode: previews drifting from reality). G1's hardness is **soft/informational**: in
  CI it prints the plan and proceeds; the consequential sub-actions (G2/G3/G4/G6)
  carry their own hard CI policy. G1's value is the single whole-picture checkpoint
  that closes the init/reproduce asymmetry.
- **F — The anti-fatigue ceiling is binding.** At most ONE hard gate fires per
  blast-radius class per run, **batched** where the actions share a class: G2
  batches every install into one prompt; G6 batches the whole stack decision into
  one review. The common path — a private repo with deterministic scaffolding and an
  opt-in language overlay — surfaces **G1 (one soft preview) + at most G4 (one soft
  generator confirm)**, never a dozen prompts. The six gates-analysis anti-patterns
  (per-file init confirm, gating deterministic local writes, re-confirming the
  interview, gating every agent step, a global yes-to-all, network/tool pre-gates)
  are **binding non-goals**.
- **G — Frozen-replay bypasses init-only gates (new 004 mechanism); 003's
  determinism contract is otherwise preserved.** Today the gate fires
  unconditionally in `apply` regardless of mode (`reproduce.py:319-321`) — on plain
  *interactive* reproduce the pin gate currently **re-prompts**. 004 makes an
  init-time research gate (G6) **init-only**: it does not prompt on plain reproduce,
  because the frozen decision is already consented (recorded in `answers.toml`) and
  the agent step already replays zero-network (003 FR-009). Mechanism: an
  `init_only: true` marker on the gate step (parallel to `when`, Decision D) makes
  `run_gate_step` auto-proceed — **not auto-skip** — when the mode is `reproduce`
  and no `--refresh` named the module, so the gate does NOT set `gate_blocked` and
  the deterministic write still replays byte-identically. Only `--refresh`
  re-triggers research + the gate prompt (003 FR-010). 004 does NOT touch the
  two-phase plan, the reproduce-replay, or the gate-blocking semantics — it adds the
  mode-aware bypass and enriches the gate *data* those mechanisms carry.
- **H — G5/G7/G8 are new subsystems with defined attach points.** G5
  (destructive-overwrite) is a divergence check in reproduce's drift/apply: on-disk
  ≠ the deterministic re-render from frozen answers ⟹ local edits present ⟹ a write
  that changes it is a hard-gate (CI safe-skips, preserving local edits). G7
  (cross-module conflict) is a collision detector over the inspect pass's
  `files_written` across modules: ≥2 non-idempotent writers of one path ⟹ an
  informational warn. G8 (secret-detected abort) is a pattern matcher at the
  interview/persist boundary that refuses to persist a value matching a known secret
  shape (a hard gate that fails the input, never silently writes). Each carries the
  hardness the calibration assigns.

## User Scenarios & Testing

**Story → gate → FR → SC traceability** (the foundation FRs underpin every gate):

| Story | Gate | FRs | SC | Priority |
|---|---|---|---|---|
| US1 | G1 whole-plan preview | FR-007, FR-008, FR-009 | SC-003 | P1 |
| US2 | G2 batched install | FR-010, FR-011 | SC-004 | P1 |
| US3 | G3 public-repo | FR-012 (+ FR-006 `when`) | SC-005 | P1 |
| US4 | G4 generator | FR-013 | SC-006 | P2 |
| US5 | G5 overwrite | FR-015, FR-016 | SC-008 | P2 |
| US6 | G6 pin review | FR-014 (+ FR-006a `init_only`) | SC-007 | P1 |
| US7 | G7 conflict | FR-017 | SC-009 | P3 |
| US8 | G8 secret | FR-018, FR-019 | SC-010 | P1 |
| (all) | foundation | FR-001…FR-006a | SC-001, SC-002 | — |
| (all) | compatibility | FR-020, FR-021 | SC-011 | — |

### User Story 1 — One whole-plan preview before a fresh init writes (Priority: P1)

A user finishes the interview for a fresh project (private repo, Python overlay).
Before any file is written or any remote touched, they see the **entire frozen
plan** as an ordered checklist — each module, its steps, the one-line `would …`
preview, and a side-effect class per line (`[writes file]`, `[network]`,
`[creates remote]`, `[installs N pkgs]`, `[runs external generator]`). They confirm
once, and execution proceeds.

**Acceptance Scenarios**:

1. **Given** a frozen init plan, **When** execution begins, **Then** the runner
   renders the aggregate preview from the inspect pass (not a hand-written literal)
   with a side-effect class per line, **before** any write.
2. **Given** the preview in a TTY, **When** the user confirms once, **Then** all
   modules proceed; **When** the user declines, **Then** the run aborts with nothing
   written.
3. **Given** `--non-interactive`, **When** the preview would show, **Then** it is
   printed to the log and execution proceeds (G1 never blocks CI); the consequential
   sub-actions are still individually gated by G2/G3/G4/G6.

### User Story 2 — The supply-chain install is one batched, reviewable confirm (Priority: P1)

apm-install is about to install the baseline MCP packages plus a user-supplied
`agentic_packages` set. The user sees the **full, unabbreviated** package list —
every `name@marketplace` on its own line, grouped "baseline (always)" vs
"you/agent selected" — and confirms the batch once. A typosquat is eyeballable.

**Acceptance Scenarios**:

1. **Given** apm-install enabled, **When** its gate fires, **Then** the message
   lists every package on its own line, grouped baseline vs selected, never
   truncated.
2. **Given** a TTY decline, **Then** the install is skipped, the manual
   `apm install …` command is printed, and the rest of the run continues.
3. **Given** `--non-interactive` with no `--allow-install`, **Then** the install is
   SAFE-skipped (deterministic, non-installing run) and the manual command is
   printed; **Given** `--non-interactive --allow-install`, **Then** the install
   proceeds.

### User Story 3 — A public repo is confirmed; a private one is never gated (Priority: P1)

A user sets `public=true`. Before the irreversible world-visible namespace claim,
they confirm. A different user sets `public=false` (or omits it) and sees **no gate
at all** — private creation is reversible and low-stakes.

**Acceptance Scenarios**:

1. **Given** `public=true`, **When** the plan is built, **Then** the github-repo
   gate step is present (hard, `allow_flag=allow-public-repo`) and fires before the
   create.
2. **Given** `public=false`, **When** the plan is built, **Then** the gate step is
   **dropped** (the `when` predicate is false) and creation proceeds ungated.
3. **Given** `--non-interactive` with `public=true` and no `--allow-public-repo`,
   **Then** the public repo is NOT created and the manual `gh` command is printed;
   **Given** `--allow-public-repo`, **Then** it is created.

### User Story 4 — A soft generator gate proceeds in CI, opts out by flag (Priority: P2)

A lang-ts project enabled the Nuxt scaffolder. In a TTY the user confirms running
`nuxi@latest init` (network; may overwrite). In CI it proceeds by default (the
overlay enablement is the consent) — unless `--no-external-generators` is passed,
which skips the scaffolder while still writing the deterministic files.

**Acceptance Scenarios**:

1. **Given** lang-ts with a framework scaffolder, **When** the generator gate fires
   in a TTY, **Then** the exact command + the overwrite hazard are named and
   confirmed `[Y/n]` (default Yes).
2. **Given** `--non-interactive`, **Then** the scaffolder runs (soft auto-proceed);
   **Given** `--non-interactive --no-external-generators`, **Then** the scaffolder
   is skipped and the deterministic manifest writes still occur.

### User Story 5 — A re-run never silently clobbers local edits (Priority: P2)

A teammate reproduces a project they have hand-edited. A deterministic write would
overwrite a file whose on-disk content diverges from what the frozen plan produces.
The runner escalates: it names the file, offers confirm/skip/diff, and in CI
SAFE-skips that file (preserving the local edits).

**Acceptance Scenarios**:

1. **Given** an on-disk file that differs from the deterministic re-render of the
   frozen answers, **When** a write would change it, **Then** the confirm is
   escalated to a hard overwrite gate (`OVERWRITE — <path> has local changes…`).
2. **Given** `--non-interactive`, **Then** the divergent file is SAFE-skipped
   (local edits preserved), recorded as a skipped diff, and the run continues;
   append-if-absent and create-new are unaffected.

### User Story 6 — The agent's stack decision is a hard, reviewable gate (Priority: P1)

The 003 pin-table gate is upgraded: it shows each pin's `name@version`, its
registry-verification status, the downgrade-from-latest reason, the agent's
rationale, and its sources. It is a hard gate at init (CI safe-skips the write
unless `--allow-stack-write`) and does NOT re-fire on plain reproduce.

**Acceptance Scenarios**:

1. **Given** a resolved stack at init, **When** the pin gate fires, **Then** it
   shows per-pin verify-status + rationale + sources (not just `name@version`).
2. **Given** `--non-interactive` at init with no `--allow-stack-write`, **Then** the
   manifest write is SAFE-skipped (no unverified write); **Given** plain reproduce,
   **Then** the gate does NOT fire (frozen replay, 003 FR-009).

### User Story 7 — Colliding modules are surfaced, not silently merged (Priority: P3)

Two enabled overlays both write a shared file (e.g. root `package.json` /
`.pre-commit-config.yaml`). The runner warns — names the contended path and the
resolved topo order — and proceeds (deterministic, reproducible). It does NOT block.

**Acceptance Scenarios**:

1. **Given** two modules whose inspect pass writes the same path non-idempotently,
   **When** the plan executes, **Then** an informational warning names the path and
   the resolved order.
2. **Given** two modules that both marker-guarded-append to a shared file (benign,
   idempotent), **Then** no warning is raised (no false-positive fatigue).

### User Story 8 — A pasted secret is refused, never persisted (Priority: P1)

A user pastes a `ghp_…` PAT into an input. The runner detects the secret shape,
refuses to persist it, drops the value, and tells the user to rotate it. In CI a
suspected secret is never silently written.

**Acceptance Scenarios**:

1. **Given** an input value matching a known secret shape (`ghp_`, `sk-`,
   `-----BEGIN`, `AKIA`), **When** it is collected, **Then** it is NOT written to
   `answers.toml`; the input fails (MISSING_ANSWER if it was required) and the user
   is told to rotate it.
2. **Given** an explicit override answer for a flagged-but-legitimate
   high-entropy value, **Then** the value is allowed through (false-positive escape
   hatch).

### Edge Cases

- **A gate with no `hardness` field** (every 003-era gate): defaults to `"hard"`,
  so its non-interactive behavior is byte-identical to today's SAFE-skip. No 003
  test changes behavior.
- **A `when` predicate referencing a missing answer**: treated as false (gate
  dropped) — a gate must never fire on an unknown condition. (See OQ-2 for the exact
  missing-vs-falsey rule.)
- **A hard gate whose `allow_flag` is passed in a TTY** (not CI): the flag pre-opts
  in, so the TTY prompt is skipped and the action proceeds (the flag is a standing
  consent, consistent across TTY/CI).
- **G1 + a per-action hard gate both apply**: G1 is the soft aggregate preview; the
  hard gate (G2/G3/G6) still fires at its step. Confirming G1 does NOT auto-confirm
  the hard sub-gates (that would be the yes-to-all anti-pattern).
- **G5 divergence on a file the runner itself last wrote a different version of**
  (module upgraded between runs, not a user edit): the runner cannot always
  distinguish "user edit" from "older module output". Over-gating annoys,
  under-gating destroys — gate only when on-disk ≠ the re-render AND the new write
  differs (see OQ-4 for the exact rule).
- **G8 false positive on a non-secret high-entropy string**: the matcher is scoped
  to known key shapes; an explicit override answer is the escape hatch (US8 #2).
- **An init aborted at the G1 preview**: nothing is written and nothing is persisted
  (persist is stage 8, after execution) — a clean no-op, consistent with declining
  every write.

## Requirements

### Gate primitive enrichment (the foundation)

- **FR-001**: `StepSpec` (`runner/manifest.py`) MUST gain a `hardness` field with
  values `"hard" | "soft" | "informational"`, defaulting to `"hard"` when absent.
  The manifest parser MUST validate the value and emit `MANIFEST_MALFORMED` for an
  unknown hardness, exactly as it validates `kind`.
- **FR-002**: A gate step MAY carry an optional `allow_flag` (a CLI flag name for
  hard gates) and an optional `skip_flag` (a `--no-…` flag name for soft gates).
  Both MUST be parsed by the manifest and **threaded through the frozen-plan
  serializer** (`plan.py` — which today keeps only `id/kind/steering/message`), or
  they are silently dropped.
- **FR-003**: `run_gate_step` MUST resolve its non-interactive outcome from the
  frozen plan's `hardness` + the active CLI flag set (the gates-analysis §3 table),
  not the current hardcoded SAFE-skip: **hard** → SAFE-skip unless its `allow_flag`
  is active (then perform); **soft** → proceed unless its `skip_flag` is active (then
  SAFE-skip); **informational** → print and proceed without prompting. No
  non-interactive path may call `input()`.
- **FR-004**: In a TTY, a **hard** gate MUST prompt `[y/N]` (default No, the
  existing `io.confirm`); a **soft** gate MUST prompt `[Y/n]` (default Yes — a new
  variant); an **informational** gate MUST print and proceed without a prompt. A
  standing `allow_flag`/`skip_flag` passed in a TTY pre-resolves the gate (no prompt).
- **FR-005**: The runner MUST NOT expose a global "confirm everything / yes-to-all"
  flag. CI opt-in MUST be per-action (`--allow-public-repo`, `--allow-install`,
  `--allow-stack-write`, `--no-external-generators`). (Binding non-goal — Settled
  Decision C / anti-pattern 5.)
- **FR-006**: A gate step MAY carry a `when` predicate (`key`, `key == value`, or
  `key != value`) evaluated at `build_plan` against the module's frozen answers; a
  false predicate MUST drop the gate step from the frozen plan. Evaluation MUST be
  deterministic so reproduce keeps/drops the identical set of gates as init.
- **FR-006a**: A gate step MAY carry `init_only: true`. When set, on a plain
  reproduce (mode `reproduce`, the gate's module not named by `--refresh`)
  `run_gate_step` MUST **auto-proceed** (return confirmed, NOT SAFE-skip) without
  prompting — so the gate does not set `gate_blocked` and the deterministic write
  replays byte-identically. This is distinct from a hard gate's CI SAFE-skip: a
  consented frozen decision must not block its own replay. (Today the gate fires
  unconditionally in `apply` regardless of mode — `reproduce.py:319-321`; this is
  the additive mode-aware bypass.)

### G1 — Whole-plan preview

- **FR-007**: In init mode the runner MUST render the entire frozen plan as an
  ordered checklist (module → steps → the one-line `would …` preview) **before any
  write**, generated from the SAME `build_drift_report` inspect pass and the modules'
  own preview strings — never a parallel hand-written literal.
- **FR-008**: Each preview line MUST carry a side-effect class: `[writes file]`,
  `[network]`, `[creates remote]`, `[installs N pkgs]`, `[runs external generator]`,
  derived from the inspect outcome + step kind + the step's declared gate hardness
  (not a hand-maintained per-module table).
- **FR-009**: G1 MUST capture ONE confirm to proceed in a TTY (decline = abort, no
  writes); it MAY offer "proceed but skip module X". G1's hardness is soft/
  informational: in `--non-interactive` it MUST print the plan and proceed (it never
  blocks CI), leaving the consequential sub-actions to their own hard gates.

### G2, G3 — Supply-chain & irreversible-action gates (hard)

- **FR-010**: apm-install MUST declare a **hard** gate (`allow_flag=allow-install`)
  before its install step, whose message lists every package on its own line,
  grouped "baseline (always)" vs "you/agent selected", **never truncated**. A
  declined gate MUST skip the install and print the manual `apm install …` command
  (the module already does on skip, `module.py`); the rest of the run continues.
- **FR-011**: In `--non-interactive`, the install MUST SAFE-skip unless
  `--allow-install` is active; a network code-install MUST NEVER auto-approve in CI.
  (Future researched-pin manifest writes share this blast-radius class and batch
  with G6 — forward-compat note, not built here beyond 003's pin gate.)
- **FR-012**: github-repo MUST declare a **hard** gate
  (`allow_flag=allow-public-repo`, `when = "public == true"`) before the create
  call. Private creation MUST remain ungated (the gate step is `when`-dropped). In
  `--non-interactive` a public repo MUST NOT be created without `--allow-public-repo`;
  the manual `gh` command MUST be printed on skip.

### G4, G6 — External-generator & agent-decision gates

- **FR-013**: The lang-* external scaffolder invocation (`nuxi init`, `create-vite`,
  `bun/pnpm init`) MUST be an independently-gated **soft** step
  (`skip_flag=no-external-generators`) whose message names the exact command and the
  overwrite hazard. A declined gate MUST skip the scaffolder while the deterministic
  manifest writes still proceed (so the scaffolder run must be a step distinct from
  the deterministic write). In `--non-interactive` it proceeds unless
  `--no-external-generators` is active.
- **FR-014**: The 003 lang-* pin-table gate MUST be upgraded to **hard**
  (`allow_flag=allow-stack-write`), with a message showing per-pin `name@version`,
  registry-verification status, downgrade-from-latest reason, the agent's rationale,
  and its sources (extending the existing `{decision}` render). It MUST carry
  `init_only` (FR-006a): on plain reproduce it MUST NOT prompt and MUST NOT block
  the deterministic write (the frozen decision is already consented; the byte-
  identical replay is preserved); only `--refresh` re-triggers the prompt (003
  FR-010). *(This changes the current behavior, where the gate fires
  unconditionally in `apply` on every mode — `reproduce.py:319-321`. It is new 004
  work, not a 003-preserved fact.)*

### G5 — Destructive-overwrite gate (re-run)

- **FR-015**: In reproduce mode, a write whose target on-disk content **diverges
  from the deterministic re-render of the frozen answers** (i.e. the file has local
  edits) AND whose new content differs MUST escalate to a **hard** overwrite gate
  (`OVERWRITE — <path> has local changes that will be lost`; offer confirm/skip/
  diff). create-new, append-if-absent, and clean (non-divergent) modifies MUST stay
  soft/none.
- **FR-016**: In `--non-interactive`, a true destructive overwrite MUST SAFE-skip
  the file (preserve local edits), record it as a skipped diff, and continue —
  CI MUST NEVER silently destroy local work.

### G7 — Cross-module conflict review (informational)

- **FR-017**: The runner MUST detect shared-file write collisions across enabled
  modules — ≥2 modules whose inspect pass writes the same path **non-idempotently**
  — and surface them **informationally**: warn, name the contended path and the
  resolved topo order, and proceed (deterministic, reproducible; it MUST NOT block).
  Benign marker-guarded append-if-absent collisions MUST NOT be flagged (no
  false-positive fatigue); a destructive collision escalates via G5, not G7.

### G8 — Secret-detected abort (hard)

- **FR-018**: At the interview/answer-persist boundary, an input value matching a
  known secret shape (`ghp_…`, `sk-…`, `-----BEGIN…`, `AKIA…`, and the documented
  set) MUST be refused: the value MUST NOT be persisted to `answers.toml`, the input
  MUST fail (MISSING_ANSWER if it was required), and the user MUST be told to rotate
  it. In `--non-interactive` a suspected secret MUST NEVER be silently persisted.
- **FR-019**: G8 MUST enforce the SKILL.md secrets guardrail (`SKILL.md:125-130`) as
  a real, code-level checkpoint, replacing the prose-only instruction. An explicit
  override answer MUST exist as the false-positive escape hatch.

### Compatibility & determinism

- **FR-020**: All eight gates MUST honor the blast-radius→hardness mapping and the
  anti-fatigue ceiling: at most one hard gate per blast-radius class per run, batched
  where shared. The common path (private repo + deterministic scaffold + opt-in
  overlay) MUST surface only G1 + at most G4 — no per-file init confirm, no gating of
  deterministic local writes (binding non-goals, Settled Decision F).
- **FR-021**: 004 MUST NOT change the 003 contract: the two-phase plan, the
  reproduce-replay (zero-network agent step, FR-009), the `--refresh` re-research
  path (FR-010), and the gate-blocking `apply` (declined gate skips the module's
  later writes, FR-012) are preserved. The default `hardness="hard"` MUST make every
  pre-004 gate behave identically (the full 003 suite stays green unchanged).

## Success Criteria

- **SC-001**: A `StepSpec` with `hardness="soft"` and `skip_flag` round-trips
  through the manifest parser and the frozen-plan serializer; an unknown hardness
  value is rejected as `MANIFEST_MALFORMED` (unit test).
- **SC-002**: `run_gate_step` resolves the three hardnesses correctly in
  `--non-interactive`: hard SAFE-skips (and performs with its `allow_flag`), soft
  proceeds (and SAFE-skips with its `skip_flag`), informational prints and proceeds —
  none call `input()` (test with a stdin-blocking IO double).
- **SC-003**: A fresh init renders the whole-plan preview from the inspect pass with
  a side-effect class per line before any write; declining it writes nothing; in CI
  it prints and proceeds (G1 never blocks).
- **SC-004**: apm-install shows the full untruncated package list grouped baseline
  vs selected; CI without `--allow-install` SAFE-skips the install + prints the
  manual command; CI with `--allow-install` installs.
- **SC-005**: With `public=true` the github-repo gate is present and CI safe-skips
  the public create without `--allow-public-repo`; with `public=false` the gate step
  is dropped from the frozen plan and creation proceeds ungated.
- **SC-006**: The lang-* generator gate is soft — CI runs the scaffolder by default
  and SAFE-skips it under `--no-external-generators` while still writing the
  deterministic manifest.
- **SC-007**: The upgraded pin gate shows per-pin verify-status + rationale +
  sources, is hard (CI safe-skips the write without `--allow-stack-write`), and on
  plain reproduce (no `--refresh`) does NOT prompt and does NOT block the byte-
  identical manifest replay (the `init_only` auto-proceed, FR-006a) — only
  `--refresh` re-triggers the prompt.
- **SC-008**: A reproduce write over a file diverging from the frozen re-render
  escalates to the overwrite gate; CI SAFE-skips it and preserves the local edits;
  append/create paths are unaffected.
- **SC-009**: Two modules writing the same path non-idempotently produce one
  informational warning naming the path + order; two marker-guarded appends produce
  none.
- **SC-010**: A `ghp_…`/`sk-…`/`-----BEGIN…`/`AKIA…` input value is never written to
  `answers.toml`, fails the input, and prompts rotation; an overridden value is
  allowed.
- **SC-011**: The full 003 suite stays green unchanged (default `hardness="hard"`
  preserves every pre-004 gate's behavior); no global yes-to-all flag exists.

## Out of Scope

- A structured/interactive gate UI beyond the message string + the soft `[Y/n]`
  variant (e.g. a TUI menu, inline pin-editing at the gate). G6 captures accept/skip;
  "edit-a-pin" inline (gates-analysis G6 "edit") is deferred — a declined gate +
  `--refresh` is the edit path.
- The `apm_deps` union across modules (gates-analysis G2 / apm-install note "future
  scope") — 004 batches what apm-install installs today, not a cross-module dep union.
- Reordering modules from G7 (gates-analysis G7 "reorder") — G7 is informational
  (warn + proceed in topo order) in 004; interactive reorder is deferred.
- A general predicate/expression language for `when` beyond the three minimal forms
  (`key`, `key == value`, `key != value`).
- Go/Rust generator gates (G4 for lang-go/rust via cargo/uv) — the pattern extends
  when those overlays gain scaffolders; 004 builds G4 on lang-ts (and lang-python's
  installer where applicable).
- Changing the 001 manifest schema beyond the additive `hardness`/`allow_flag`/
  `skip_flag`/`when` gate fields, or the discovery/collision *resolution* rules
  (G7 only *detects*, it does not change topo order).

## Assumptions

- The 003 runner (two-phase plan, reproduce-replay, gate-blocking `apply`,
  `{decision}` composition) and the f1e7269 init inspect→confirm→write path are in
  place and green (564 tests at 003 ship).
- The inspect pass's outcomes carry enough to derive G1's side-effect classes and
  G7's `files_written` collision set without a new module-side preview API (verify in
  plan Phase 1; OQ-3).
- `io.confirm` (default No) is the hard-gate TTY default; only a new `[Y/n]` soft
  variant is needed (gates-analysis §3 requirement 3).
- The secret-shape set (`ghp_`, `sk-`, `-----BEGIN`, `AKIA`, …) is sufficient for
  G8's near-zero-cost assurance; the exact list is a data detail (OQ-5).
- `${PLUGIN_ROOT}` / `PROJECT_DIR` env wiring and the import-by-path SDK contract
  (shared-contracts §6) are unchanged.

## Dependencies & Open Questions

**Build-order dependency, resolved:** 004 builds **on** 003 (the gate primitive,
two-phase plan, gate-blocking apply, init-confirm path all shipped). There is no
reverse dependency — 003 ships standalone on the bare gate; 004 enriches it. The
default `hardness="hard"` is the compatibility hinge (FR-021).

**Scope, resolved (user, 2026-06-28):** all eight gates G1–G8 in this spec; nothing
deferred to a 004-followup. The three new subsystems (G5/G7/G8) are in scope.

**Remaining open questions** (OQ-1 … OQ-7, all design-detail / MED-LOW) are tracked
in `memory.md` so they can be resolved during planning/implementation without
re-reading this spec: **OQ-1** the exact `when` grammar; **OQ-2** the `when`
missing-answer rule (false vs error); **OQ-3** the G1 side-effect-classification +
G7 collision-set source (does the inspect outcome carry enough?); **OQ-4** the G5
divergence-detection mechanism (re-render vs recorded prior output); **OQ-5** the G8
secret-shape set + override-answer plumbing; **OQ-6** the G4 step-split mechanics
(scaffold/write ordering vs the module-scoped `gate_blocked`); **OQ-7** the CLI
flag-passing path from `cli.py` to `run_gate_step`. None block authoring `plan.md`.
