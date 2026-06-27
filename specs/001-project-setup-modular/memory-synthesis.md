# Memory Synthesis: project-setup modular redesign

Compact planning summary. Greenfield memory state (no durable memory, no
governing constitution). Settled via a `grill-me` session; full decision
rationale in `memory.md`.

## What we're building

Replace the ~1106-line `project-setup.sh` monolith with a **runner + modules**
architecture:

- **Runner = the whole skill.** Generic Python launched via `uv`. Pipeline:
  resolve sources → fetch/cache → discover modules → manifest-driven interview →
  topo-order → validate-closed gate → execute → persist answers. Zero project
  specifics.
- **Everything else is a module** (git, github, dirs, pre-commit, license,
  gitignore, AGENTS.md, codex-config, justfile, apm-install, speckit-bridge,
  lang overlays, quality-hooks, package-add, and `core-identity`). Module =
  `module.toml` + Python entrypoint. "Base" = the `default_enabled` bundle.

Delivered as ONE build (no phases). "Data-out-first" survives only as build
order: extract modules, then wire the runner.

## Binding decisions (from grill-me)

- **All Python; shell dropped.** Bash-3.2/BSD floor, shellcheck, bats no longer
  apply. Tests = pytest via `uv run` (precedent: `speckit-dag-hooks`).
- **`uv` = hard prerequisite.** Fail loud, never auto-install, no stdlib
  fallback. Deps declared (pyproject) + PEP 723 inline.
- **TOML** for all human-authored config (home config, every `module.toml`,
  `.project-setup/*`); **JSON** for the internal merged plan (canonical/sorted).
- **Ordering:** explicit `before`/`requires`/`after` by id → stable topo sort in
  Python. NO `priority`. Cycles/missing-requires = hard error pre-execution.
- **Module search precedence:** env `PROJECT_SETUP_MODULES_DIR` > project
  `./.project-setup/modules/` > home `~/.config/project-setup/modules/` >
  fetched dynamic sources > bundled base.
- **Dynamic sources first-class** (git repo/path/local, APM-style locator +
  optional ref; floating `main` allowed). Fetch→cache BEFORE discovery;
  proceed-on-failure offline. APM-packaged modules OUT of scope. Arbitrary code
  execution accepted (same trust as APM/plugins).
- **Two-tier determinism, version-relative:** Tier-1 scripted = byte-identical
  (SC-001 applies here only); Tier-2 agent-steered = marked, instructed,
  consistent-not-identical, decisions persisted. "Same answers → same result"
  holds only when module versions unchanged.
- **Persistence:** committed `.project-setup/sources.toml` (sources+refs +
  advisory `[meta] skill_version`) and `answers.toml` (per-module
  `[module.<id>]` sections + `source` provenance). Clone reproduces from
  committed files alone; fetched bytes cached (gitignored), not vendored.
- **Defaults layering:** module default < home default < project answer; user
  choice overrides all. Home = personal catalog + defaults, NEVER authoritative.
- **Modes:** `sources.toml` absent → init (interview, write files); present →
  reproduce/update (fetch, load, diff/confirm). Re-run = always diff-and-confirm,
  per-item, never silent replay. Modules declare reconcile capability so re-run
  can fix drift (not just skip-if-exists).
- **gitignore:** vendored github/gitignore (CC0) templates + on-demand fetch
  from github/gitignore. No live toptal API.
- **Distribution:** stay in-repo (separate-repo idea floated then reverted); APM
  + Claude plugin marketplace (both already registered). Plugin install only
  copies files → deps come from `uv` at runtime, not an install hook.
- **Native-root layout (Claude plugin best practice):** required
  `.claude-plugin/plugin.json`; skill at `skills/project-setup/SKILL.md` (migrate
  OFF `.apm/skills/`); scripts via `${CLAUDE_PLUGIN_ROOT}/...`; no symlinks; tags
  `<name>--v<version>`. NOTE: zero of 117 existing packages use this yet —
  project-setup is the first; repo-wide tooling (marketplace builder, docgen,
  release tags) is being migrated by SEPARATE parallel work, verify together.
- **SKILL.md:** thin on config, thick on process/guardrails (ensure uv, run
  end-to-end, sourcing, interview, diff/confirm, tier execution, "done",
  validity checks, safe execution, secrets guardrail).

## Module structure (settled)

- **Anatomy:** `modules/<noun-verb-id>/` = `module.toml` + fixed `module.py` (+
  optional helper `*.py`, `steering/` progressive-disclosure docs, `templates/`,
  `test_*.py` pytest by convention).
- **Invocation (Model B):** `uv run module.py --plan <frozen> --step <id>`;
  PEP 723 per-module deps (no shared-venv conflicts); reads frozen inputs from
  disk (agent is a trigger, never an input source); emits structured JSON result.
- **`module.toml`:** `[meta]` (repository, author); `[module]` (id `<noun>-<verb>`,
  name, version, description, reconcile); `[order]` (requires/after/before, topo,
  no priority); `[tools]` (required only — fallback lives in code); `[[inputs]]`
  (key, type, prompt, choices, default, required → drives interview, persists as
  answers); `[[steps]]` (ordered; kind = python | agent(+steering) | gate(+message)).
- **Input types:** string | text | int | bool | choice | multichoice | path |
  list. NO secret type — skill instructs agent to refuse secrets + tell user to
  rotate (compromised) + never persist.
- **Rules:** `default_enabled` = first-party base bundle ONLY (remote modules
  never auto-enable); id collision across roots = HARD ERROR (no silent shadow;
  override via config/answers); NO `produces`/`creates` (drift/conflict from
  runtime JSON result); per-part tiers via step `kind`.
- **Enforcement:** runner/module-level fail-fast ONLY (no Claude hook —
  runtime-agnostic). Three gates: plan-generator validate-closed (all problems
  at once), module-entry (frozen plan + input schema), result (JSON shape). All
  emit structured `{error_code, module_id, expected, received, how_to_fix}`.
- **`[[inputs]]` naming:** "inputs" in the manifest (declarations) → "answers"
  when persisted (resolved values); matches workflow.yml `inputs:` precedent.

## Reuse, don't reinvent

- Generalize `apm-discover.sh`'s env>project>bundled precedence to the module
  search path + config layering.
- Mirror APM's declare-source + refetch reproducibility (apm.yml committed,
  apm_modules gitignored) for `sources.toml` + cached fetches.
- Port (not lift) the 4 lang overlays + monolith steps into Python modules.
- speckit bridge delegates to the existing `speckit` package.

## Verified facts that forced decisions

- `/usr/bin/python3` = 3.9.6 (no tomllib/tomli) — why "PATH python3 stdlib only"
  was insufficient and `uv` became the prerequisite.
- Claude plugin entry schema = name/description/version/tags/source only — no
  install/build hook — why deps must come from `uv` at runtime.
- CI already runs pytest via `uv run`; `speckit-dag-hooks` is a pure-Python
  package precedent. APM caches git checkouts under `~/.cache/apm/git/`.
- No PyPI library GENERATES gitignores (only matchers) — why vendored CC0 +
  github/gitignore fetch.

## Open decisions

None blocking. All architecture forks resolved in the grill-me session and
encoded in `spec.md` (sections A–H, FR-001..FR-031).
