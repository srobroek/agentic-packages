# Gates & Review Checkpoints — project-setup

Grounding survey for the Feature 002 gate calibration. Concrete, opinionated,
feeds the spec. Read the foundations below before the gate table — they constrain
every recommendation.

## Foundations (what actually exists in code)

The mechanics below are load-bearing; the gate proposals exploit or repair them.

- **The gate primitive is bare.** `executor.run_gate_step` (`runner/executor.py:396`)
  renders one `message` string and calls `io.confirm(...) -> bool`. A `kind=gate`
  step in the frozen plan is just `{id, kind, message}`. There is no whole-plan
  preview, no batching, no captured rationale, no per-gate default — a gate is a
  single yes/no on a single string.
- **`io.confirm` defaults to NO.** `TerminalIO.confirm` (`runner/io_adapter.py:155`)
  prompts `[y/N]` and returns `True` only on an explicit `y/yes`. Empty input or
  garbage → `False` (skip). This is the right safe-default and the policy below
  leans on it.
- **The per-file write-confirm loop is reproduce-mode ONLY.** `run_pipeline`
  (`runner/pipeline.py:406-424`) runs the `--inspect` dry pass + `build_drift_report`
  + `apply_reproduce` only when `mode == "reproduce"`. The **init** path
  (`pipeline.py:425-462`) runs every step directly with `inspect=False` and **no
  confirm pass**. So on a fresh project today, github-repo creates the repo and
  apm-install installs N packages with **zero** confirmation. That asymmetry is the
  single biggest gap this survey targets.
- **Gates have no non-interactive handling at all.** `ask_non_interactive`
  (`io_adapter.py:136`) exists for *inputs*, but `run_gate_step` always calls
  `io.confirm`. A `--non-interactive` TerminalIO run that hits a gate calls
  `input()` and **blocks on stdin → CI deadlock**. Any gate added MUST come with an
  explicit non-interactive resolution or it bricks CI.
- **Real blast radius, verified in module code:**
  - github-repo runs `gh repo create <org>/<name> --public|--private --source .`
    (`modules/github-repo/module.py:172`). Public-repo creation is irreversible
    namespace + visibility.
  - apm-install composes `[agentic_packages] + 4 hardcoded baseline MCP` and runs
    `apm install --target claude,codex,agent-skills <packages>`
    (`modules/apm-install/module.py:142-177`), each installing arbitrary
    code/hooks. Supply-chain surface.
  - lang-ts runs `nuxi@latest init`, `create-vite`, `bun init`, and `bun/pnpm
    install` (`modules/lang-ts/module.py:147-212`) — network fetch + mass file
    write from an external generator the runner does not control.
  - Tier-2 stack-resolver (roadmap, `memory.md`) will persist **agent-researched
    version pins** then a python step writes them into a manifest — a hallucinated
    or typosquatted pin is a live supply-chain hole.
- **Module `--inspect` is already a faithful dry-run.** Every blast-radius module
  honors `--inspect` and emits a `would …` preview (github-repo:148, apm-install:148,
  lang-ts's `inspect` branches). The whole-plan preview gate is therefore *cheap*:
  the data already exists, it just isn't aggregated or shown before init writes.

---

## 1. Gate opportunities

Eight gates, ranked by value. Each is specified for both runtimes (Claude +
Codex) since both drive the same `io.confirm`/`agent_step` boundary.

### G1 — Whole-plan preview (pre-execution, init mode) — **HIGH**

- **Gates:** the entire execution phase in init mode, before any module runs.
- **Trigger / blast radius:** init mode today writes with no aggregate review
  (`pipeline.py:425`). The user has answered an interview but has never seen the
  *consequences* as one list: which modules will run, what each writes/creates/
  installs, which are network/irreversible.
- **UX shown:** the frozen plan rendered as an ordered checklist — for each module
  in topo order, its steps and the one-line `--inspect` preview (reuse the existing
  `would …` strings; run the inspect pass in init too). Flag side-effect class per
  line: `[writes file]`, `[network]`, `[creates remote]`, `[installs N pkgs]`,
  `[runs external generator]`. **Captured:** one confirm to proceed, or abort.
  Optionally "proceed but skip module X".
- **Non-interactive:** print the plan to the log (informational) and proceed.
  This gate does NOT block CI — its value is *visibility*, and the consequential
  sub-actions are individually gated by G3/G4/G5 which carry their own CI policy.
- **Hardness:** **soft-auto-approvable** (informational in CI, confirm in TTY).
- **Failure/abuse mode:** preview drifts from reality if a module's `--inspect`
  lies about what `--no-inspect` does (github-repo/apm-install previews are
  hand-written strings, not derived). Mitigate: previews must be generated from the
  same code path, not a parallel literal.
- **Value:** HIGH — it closes the init/reproduce asymmetry and is the user's only
  whole-picture checkpoint. Cheapest high-value gate because the inspect data
  already exists.

### G2 — Consolidated dependency-install approval (the supply-chain gate) — **HIGH**

- **Gates:** apm-install's `apm install` and (future) every researched-pin manifest
  write, as ONE batched approval.
- **Trigger / blast radius:** installing N APM packages = running N packages' code,
  hooks, MCP servers; the baseline list is hardcoded
  (`apm-install/module.py:36-41`) and a user-supplied `agentic_packages` string is
  prepended unvalidated. Plus Tier-2 researched pins. This is the highest-trust
  action in the tool.
- **UX shown:** the **full, unabbreviated** package list — every
  `name@marketplace` on its own line, plus each resolved version pin where known,
  so a human can eyeball for typosquats (`mcp-context7` vs `mcp-context-7`,
  `srobroek-agentic` vs `srobroek-agnetic`). Group: "baseline (always)" vs
  "you/agent selected". **Captured:** single yes/no for the batch; reject = skip
  apm-install, continue the rest.
- **Non-interactive:** **hard-gate → default to the SAFE action = SKIP the install**
  and emit the exact manual command (apm-install already prints
  `apm install … <packages>` on skip, `module.py:159`). CI gets a deterministic,
  non-installing run + a copy-paste command. Never auto-approve a network
  code-install in CI.
- **Hardness:** **hard-gate** (TTY confirm; CI safe-skip).
- **Failure/abuse mode:** a malicious `agentic_packages` answer slips a typosquat
  past a tired user who reflexively confirms. Mitigate: never truncate names; sort
  baseline vs selected so the *short, reviewable* selected set stands out; (future)
  cross-check pins against the registry-verify rule from `memory.md`.
- **Value:** HIGH — this is the named supply-chain gate; the whole Tier-2
  pinning story depends on it existing.

### G3 — Public-repo-creation confirm — **HIGH**

- **Gates:** github-repo's create call **only when `public=true`**.
- **Trigger / blast radius:** `gh repo create … --public`
  (`github-repo/module.py:171`) publishes a namespace to the world irreversibly;
  a fresh repo may contain a leaked default, a wrong org, or a name squat. Private
  creation is low-stakes and reversible (delete), so it is NOT gated here.
- **UX shown:** `Create PUBLIC GitHub repo <org>/<name>? This is world-visible and
  the name is claimed immediately.` **Captured:** yes/no; no = skip creation,
  print the manual `gh` command (module already does, `module.py:117`).
- **Non-interactive:** **hard-gate → SAFE action = do NOT create the public repo.**
  CI that genuinely wants a public repo must pass an explicit
  `--allow-public-repo` flag (or answer `public=true` *and* a separate
  `confirm_public=true` input) — opt-in, never default-yes.
- **Hardness:** **hard-gate** for public; **none** for private.
- **Failure/abuse mode:** user fat-fingers `public=true` in the interview and a
  half-baked repo goes public. The gate is the catch. Abuse: a CI job set to
  auto-confirm everything — defeated by requiring the explicit flag rather than a
  global "yes to all".
- **Value:** HIGH — irreversible + public + cheap to gate.

### G4 — External-generator-run confirm — **MED**

- **Gates:** lang-* framework scaffolds: `nuxi init`, `create-vite`, `bun/pnpm
  init`, and the package-manager `install` (`lang-ts/module.py:147-212`; analogous
  in lang-go/rust via cargo/uv).
- **Trigger / blast radius:** these reach the network, execute a third-party
  generator the runner cannot make deterministic, and **mass-write** files
  (`nuxi init . --force` can overwrite). Distinct from G2: this is *code execution
  of a scaffolder*, not package install.
- **UX shown:** `lang-ts will run 'nuxi@latest init . --force' (network; may
  overwrite files in <dir>). Proceed?` Name the exact command + the `--force`
  hazard. **Captured:** per-generator yes/no; no = skip the scaffold, keep the
  deterministic file writes (tsconfig etc.) that don't need it.
- **Non-interactive:** **soft-auto-approvable** — language overlays are opt-in
  (the user already enabled lang-ts), so in CI proceed by default BUT respect a
  `--no-external-generators` flag that flips it to safe-skip. Rationale: blocking
  every CI scaffold run would make the tool useless for its main job; the opt-in
  enablement is the consent.
- **Hardness:** **soft-auto-approvable.**
- **Failure/abuse mode:** `nuxi init … --force` clobbers an existing partial
  scaffold the user wanted to keep. Mitigate: the modules already skip when
  `nuxt.config.ts`/`vite.config.ts`/`package.json` exists — the gate is the
  backstop for the first-run-into-nonempty-dir case.
- **Value:** MED — network + overwrite is real, but enablement already implies
  intent, so a hard gate would be fatigue.

### G5 — Destructive / reconcile-overwrite confirm (re-run) — **MED**

- **Gates:** in reproduce mode, any diff whose `kind` is `modify`/overwrite on a
  file with **local edits the runner would clobber** — especially shared files
  (root workspace `package.json`) and `reconcile=true` modules.
- **Trigger / blast radius:** reproduce already confirms each write
  (`reproduce.apply`), but a plain `modify` confirm doesn't distinguish "appending
  to a file you haven't touched" from "overwriting your hand-edits". The latter is
  silent data loss.
- **UX shown:** when the on-disk content diverges from what the frozen plan last
  wrote, escalate the confirm: `OVERWRITE — <path> has local changes that will be
  lost. Show diff? [y]/skip/diff.` **Captured:** confirm / skip / show-diff.
- **Non-interactive:** **hard-gate on true overwrite → SAFE action = SKIP that
  file** (preserve local edits), record it as a skipped diff, continue. CI never
  silently destroys local work. Append-if-absent and create-new stay
  soft/auto-proceed.
- **Hardness:** **hard-gate** for destructive overwrite of modified files; **soft**
  for clean modify; **none** for create/append-if-absent.
- **Failure/abuse mode:** the runner can't always tell "user edit" from "previous
  run by a different module version" — over-gating annoys, under-gating destroys.
  Mitigate: gate only when on-disk ≠ last-frozen-output AND the new write differs.
- **Value:** MED — protects the re-run/clone path, which is where data loss hides;
  lower than G1-G3 only because the per-file confirm loop already exists to build on.

### G6 — Agent-decision review (Tier-2 stack/pin) — **HIGH**

- **Gates:** every `kind=agent` decision that feeds a downstream write — the
  stack-resolver's framework + companion-lib + version-pin choice, before the
  deterministic python step writes the manifest (`memory.md` Tier-2 pattern).
- **Trigger / blast radius:** the agent *researches and picks* — model judgment,
  not determinism. A wrong/hallucinated pin becomes a frozen, replayed,
  supply-chain artifact. This is the consent point between Tier-2 judgment and
  Tier-1 writes.
- **UX shown:** the structured decision + **rationale + sources**: `Chose Nuxt 3.x
  + Pinia 2.x; pinned nuxt@3.14.2 (verified on registry 2026-06-27), pinia@2.2.6.
  Rationale: <agent's reasoning>. Sources: <context7/whats-new refs>.` **Captured:**
  accept / edit-a-pin / reject-and-re-research. Accepted decision is frozen with
  `agent-steered` provenance (the merge path is verified, `memory.md`).
- **Non-interactive:** **hard-gate → SAFE action = do NOT write unverified
  researched pins.** In CI, the *frozen* decision from a prior init run replays
  with zero network (per the determinism rule); a *fresh* research with no human
  to confirm must NOT auto-write — fail closed with "run interactively once to
  freeze the stack decision". Pairs with the registry-verify rule: a pin that
  fails verification is rejected regardless of gate.
- **Hardness:** **hard-gate at init** (first research); **none on reproduce**
  (frozen replay is already consented).
- **Failure/abuse mode:** rubber-stamping a plausible-looking hallucinated pin.
  Mitigate: show the registry-verification status inline; never present an
  unverified pin as accepted.
- **Value:** HIGH — this is the whole point of Tier-2 having a gate; without it the
  agent silently authors supply-chain manifests.

### G7 — Cross-module conflict review — **MED**

- **Gates:** detected conflicts where two enabled modules write the same shared
  file or contradict each other (e.g. two language overlays both editing root
  `package.json` / `.pre-commit-config.yaml`; a precommit hook appended twice;
  conflicting gitignore intents).
- **Trigger / blast radius:** the validate-closed gate covers
  missing/requires/cycle/tools but **not** semantic write-collisions on shared
  files. Last-writer-wins silently produces a Frankenstein config.
- **UX shown:** `lang-ts and lang-python both modify .pre-commit-config.yaml /
  package.json. Order: lang-ts → lang-python. Proceed, reorder, or disable one?`
  List the contended paths + the resolved order. **Captured:** proceed / disable
  module / (advisory) reorder.
- **Non-interactive:** **informational → warn and proceed** in deterministic topo
  order. The order is already deterministic (topo sort), so CI is reproducible;
  this gate is about *surfacing* the collision to a human, not blocking. (Escalate
  to G5's hard-overwrite gate only if a collision is actually destructive.)
- **Hardness:** **informational** (soft warn); escalates to hard only via G5.
- **Failure/abuse mode:** false positives on benign append-if-absent collisions
  (both append to gitignore, both guarded by markers — harmless) → fatigue.
  Mitigate: only flag collisions where both writes are non-idempotent or one
  overwrites.
- **Value:** MED — real for multi-overlay/monorepo setups (package-add); low
  for the common single-language project.

### G8 — Secret-detected abort — **HIGH** (assurance, near-zero cost)

- **Gates:** the interview / answer-persist boundary when a value looks like a
  secret (API key, token, private key, `gh` PAT pasted into an input).
- **Trigger / blast radius:** SKILL.md's non-negotiable secrets guardrail
  (`SKILL.md:96-101`) is currently *prose instruction to the agent*, not an
  enforced checkpoint. A secret persisted into `answers.toml` is committed and
  compromised.
- **UX shown:** `Input <key> looks like a secret (matched <pattern>). It will NOT
  be persisted. Rotate it now — treat it as compromised.` **Captured:** acknowledge;
  the value is dropped, never written.
- **Non-interactive:** **hard-gate → SAFE action = refuse to persist the value and
  fail the input** (MISSING_ANSWER if it was required). Never silently write a
  suspected secret in CI.
- **Hardness:** **hard-gate** (refuse, don't merely warn).
- **Failure/abuse mode:** false positive on a non-secret high-entropy string blocks
  a legit value. Mitigate: scope the matcher to known key shapes (`ghp_`, `sk-`,
  `-----BEGIN`, `AKIA`), allow an explicit override answer.
- **Value:** HIGH — turns an existing *unenforced* policy into a real
  checkpoint at near-zero cost.

---

## 2. Calibration rule (blast-radius → hardness)

The governing rule, designed to avoid gate fatigue. **A run that does only
reversible, local, deterministic writes must be confirmable in ONE gate (G1) and
must never deadlock CI.** Hardness is assigned by the worst attribute of the
action, scored on three axes:

| Axis | LOW | MED | HIGH |
|---|---|---|---|
| **Reversibility** | trivially undoable (delete a file, `git checkout`) | undoable with effort (delete private repo) | irreversible (public repo, published name, leaked secret) |
| **Reach** | inside `project_dir`, this repo only | shared/root file, local tooling state | network / remote / another machine / supply chain |
| **Determinism** | byte-identical python step | agent-steered, frozen-replayable | non-deterministic external code execution (generator, install) |

**Mapping (the rule):**

- **HARD gate** ⟺ the action is **irreversible OR a supply-chain/code-install
  surface OR destroys existing local work**. Earns it: public-repo create (G3),
  dependency install (G2), agent-researched pin writes (G6), destructive overwrite
  of modified files (G5-destructive), suspected-secret persist (G8). These default
  to the SAFE/skip action in CI.
- **SOFT (auto-approvable)** ⟺ the action is **non-deterministic or reaches the
  network but is reversible AND the user already opted in** by enabling the module.
  Earns it: external generator runs (G4), the whole-plan preview (G1), clean
  (non-destructive) reproduce modifies. Proceed by default in CI; honor an explicit
  `--no-…` flag to flip to safe-skip.
- **NONE (no gate)** ⟺ the action is **reversible AND local AND deterministic**:
  every Tier-1 file write inside `project_dir` (identity, dirs, gitignore, license,
  agents-md, justfile). These are covered by reproduce's per-file confirm and by
  G1's aggregate preview — adding individual gates here is pure fatigue.

**The anti-fatigue ceiling:** at most **one** hard gate fires per blast-radius
class per run, and they are **batched** where they share a class (G2 batches all
installs into one prompt; G6 batches the stack decision into one review). The
common path — a private repo with deterministic scaffolding and an opt-in language
overlay — should surface **G1 (one preview) + at most G4 (one generator confirm)**,
not a dozen prompts.

---

## 3. Non-interactive / CI policy

Driven by the verified deadlock risk: gates have **no** non-interactive handler
today (`run_gate_step` always calls `io.confirm` → `input()`). The policy:

**Core rule — hard gates fail to the SAFE action, never to auto-approve.** "Safe"
= the action that does *not* take the irreversible/consequential consequence. So a
hard gate in CI **skips the consequential step** and continues; it does not
proceed and it does not hang.

Resolution by hardness:

| Hardness | TTY behavior | `--non-interactive` / CI behavior |
|---|---|---|
| **hard** | prompt `[y/N]`, default No | **safe-skip** the gated step, record it skipped, print the manual command, continue. Opt-in to *perform* it requires an explicit per-action flag (`--allow-public-repo`, `--allow-install`, `--allow-stack-write`) — never a blanket "yes". |
| **soft** | prompt `[Y/n]`, default Yes | **auto-proceed**, unless a `--no-<thing>` flag is set, which flips to safe-skip. |
| **informational** | print, no prompt | print to log, proceed. |

Implementation requirements this implies:

1. **Add a non-interactive path to `run_gate_step`** mirroring `ask_non_interactive`
   (`io_adapter.py:136`): a `confirm_non_interactive(item)` that returns the
   *hardness-appropriate default* (False for hard, True for soft) **without calling
   `input()`**. Without this, every gate added is a CI deadlock.
2. **Gate steps in the frozen plan must carry their hardness** — extend the
   `{id, kind, message}` shape with `hardness` and an optional `allow_flag` so the
   non-interactive resolver is data-driven, not hardcoded in the executor.
3. **`io.confirm` already defaults to No** — reuse it as the hard-gate TTY default;
   only soft gates need a `[Y/n]` variant.
4. **A skipped hard gate is a first-class outcome, not a failure** — the run
   succeeds, the step is reported skipped with its manual command (consistent with
   the existing "single module failure is non-fatal" rule, `SKILL.md:104`). CI gets
   a green, deterministic, non-consequential run.
5. **Frozen-replay bypasses init-only gates.** G6 (and any init-time research gate)
   does NOT re-fire on plain reproduce — the frozen decision is already consented.
   Only `--refresh` re-triggers the research + its gate.

---

## 4. Anti-patterns (gates NOT to add)

1. **Per-file confirm in init mode.** Reproduce already has the per-file loop;
   replicating it for init would mean a yes/no per scaffold file (a dozen+ prompts
   for the base bundle). G1's single aggregate preview is the correct altitude.
   *Trap: mistaking "init has no confirm" for "init needs per-file confirm" — it
   needs ONE plan-level confirm.*
2. **Gating deterministic local writes** (identity, dirs, gitignore, license,
   justfile, agents-md). Reversible + local + byte-identical = zero gate. A gate
   here trains users to reflexively mash `y`, which then defeats G2/G3 when they
   matter. *The fatigue that disarms the real gates.*
3. **Re-confirming the interview.** The user already answered each input;
   re-prompting "you chose bun, confirm?" per answer duplicates the interview and
   adds nothing. The whole-plan preview (G1) is the single confirmation that the
   *answers as a whole* are right.
4. **Gating every agent step.** Only Tier-2 agent decisions that **feed a write**
   need a gate (G6). An agent step that merely records a README intro string or a
   non-consequential note does not — gating it makes the agent feel
   interrogated and adds prompts with no blast radius behind them.
5. **A global "confirm everything / yes-to-all" toggle.** It looks convenient but
   collapses the hardness distinction — one `--yes` would auto-approve the public
   repo, the install, and the pin write together, exactly the actions that must
   stay individually opt-in. Per-action allow flags (§3) instead of a master switch.
6. **Network-reachability / tool-version pre-gates.** Don't gate "you're about to
   use the network" or "gh is version X" as standalone prompts. Missing tools are
   already handled by validate-closed (`MISSING_REQUIRED_TOOL`) and modules
   warn+continue on tool failure (`SKILL.md:104`). A separate "about to touch the
   network" gate is noise layered on top of G2/G4 which already name the specific
   network action.
