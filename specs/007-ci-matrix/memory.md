# Feature 007 — CI Matrix Sized to Stack (memory)

Authored in one session from the roadmap rank #5 entry + direct reading of the
runner, SDK, and relevant modules. Everything here is verified against shipped code
on `feat/project-setup-modular-redesign` at HEAD `7779c27` unless marked otherwise.

## Scope decision (what 007 is)

007 = **a new standalone `ci-github-actions` module** that follows the exact Tier-2
pattern (003 Settled Decision B): agent emits a frozen `ci_plan`; gate shows the
rendered workflow YAML before write; python validates commands against real justfile
recipes + package.json scripts, renders canonical YAML via `idempotent_write`. It
is roadmap rank #5 and depends on 003 (stack answers) + 004 (hard gate enrichment).

The module is cross-cutting by design: it reads the full frozen answer set from all
active lang-* overlays, not just one language. It is `default_enabled = false` so
projects that manage their own CI are unaffected.

## VERIFIED CODE FACTS that shape the spec (read before implementing)

All verified by direct read; no subagent trust.

### Fact 1 — No CI workflow module exists anywhere

`packages/project-setup/skills/project-setup/modules/` contains 18 module
directories. None is named `ci-github-actions` or any CI variant. This module is
100% net-new — no migration, no port.

### Fact 2 — justfile-write skeleton recipes are well-defined

`modules/justfile-write/module.py:27-49` — `_JUSTFILE` constant defines these
exact recipe names: `default`, `test`, `lint`, `build`, `dev`, `clean`. The `lint`
recipe runs `pre-commit run --all-files` (`:34`). All other recipe bodies are
`@echo "TODO: ..."` stubs. The python write step can parse this file for recipe
names by scanning for lines matching `^<name>:` (a simple line-prefix scan; no
justfile parser library needed).

### Fact 3 — `use_just` is the justfile-write input key

`modules/justfile-write/module.toml:19` — `key = "use_just"`, `type = "bool"`,
`default = true`. The CI module reads this from the frozen plan to decide whether
to validate commands against a justfile and whether to include `just`-prefixed
commands in the output.

### Fact 4 — lang-python frozen answers the CI module reads

`modules/lang-python/module.py:281-286` in the `_do_write` handler:
- `python_version` (str, default "3.13")
- `framework` (str, default "none")
- `pinned_deps` (list)
- `dev_deps` (list)
- `ruff_version` (str)

The CI module only needs `python_version`; the rest are for the lang-python write
step but are available in the frozen plan.

### Fact 5 — lang-ts frozen answers the CI module reads

`modules/lang-ts/module.toml:19-38` — inputs:
- `package_manager` (choice: `bun`/`pnpm`, default `bun`)
- `framework` (string, default `"plain"`)
- `target` (string, optional)
- `ui_kit` (string, optional)

The CI module reads `package_manager` to determine the correct TS install/test
command for the generated job.

### Fact 6 — `FrozenInputs.mode` is available for network gating

`runner/sdk.py:87-91` — `.mode` property returns `"init"` or `"reproduce"`.
The CI module gates any network activity (none planned for reproduce) on this
property, matching the lang-python pattern (`modules/lang-python/module.py:296`).
In practice the CI module has NO network calls in its python step — all content
is from the frozen plan.

### Fact 7 — Gate shape: hardness + allow_flag + init_only are available

`runner/manifest.py:60-71` (spec 004 deliverable):
- `hardness: str = "hard"` (default)
- `allow_flag: str | None = None`
- `skip_flag: str | None = None`
- `when: str | None = None`
- `init_only: bool = False`

The CI gate uses `hardness="hard"`, `allow_flag="allow-ci-write"`, `init_only=true`.
This exactly mirrors the lang-* `pins` gate (`modules/lang-python/module.toml:47-50`
and `modules/lang-ts/module.toml:55-62`).

### Fact 8 — `{decision}` token in gate messages is rendered at freeze time

`runner/plan.py:159-168` (003 AS-BUILT point 2) — `build_plan` replaces `{decision}`
in a gate message with `render_answer_block(mod_answers)`. This gives the CI gate its
full `ci_plan` rendered for human review without any changes to the runner.

### Fact 9 — `idempotent_write(reconcile=True)` is the right primitive

`runner/sdk.py:182-257` — `reconcile=True` means overwrite if content differs
(returns `kind="modify"`), create if absent (returns `kind="create"`), skip if
identical (returns `kind="skip"`). CI YAML should always match the frozen plan, so
`reconcile=True` is correct (unlike justfile which uses `reconcile=False` to
preserve hand-edits).

### Fact 10 — `verify_pins` only supports `"pypi"` and `"npm"`

`runner/sdk.py:356-362` — the ecosystem check rejects anything not in
`{"pypi", "npm"}`. **No GitHub Actions version probe exists.** Action major pinning
is purely agent-knowledge at init; there is no SDK support for live GH API queries
and adding one is disproportionate (Settled Decision D).

### Fact 11 — `after` in `[order]` is the correct ordering mechanism

`modules/lang-python/module.toml:16` uses `after = ["gitignore-generate",
"precommit-setup"]`. The CI module uses the same mechanism:
`after = ["justfile-write", "lang-python", "lang-ts", "lang-go", "lang-rust"]`.
This ensures the two-phase plan has all lang-* answers frozen before the CI agent
step runs in Phase A.

### Fact 12 — `dependencies = []` in the `# ///` header is the stdlib-only contract

`modules/justfile-write/module.py:1-4` and `modules/quality-hooks/module.py:1-4` —
the `# /// script` block with `requires-python = ">=3.11"` and `dependencies = []`
declares that the module uses stdlib only. The CI YAML renderer must be pure-stdlib
(no `pyyaml`) to honour this contract.

## OPEN QUESTIONS — resolve during planning/implementation

Each written so it can be answered without re-reading the spec.

### OQ-1 — Should the python step probe GitHub API for action-major confirmation? (MED)

FR-005 directs the agent to use context7/whats-new tools if available; Settled
Decision D records no live GH API probe. **Open:** should there be a stdlib `urllib`
call to `https://api.github.com/repos/{owner}/{repo}/releases/latest` in the python
write step to validate the action major the agent proposed is still current?

**Why it needs human input:** adding a new network endpoint to the python step breaks
the "zero-network on reproduce" principle unless guarded by `inputs.mode == "init"`.
It also requires GitHub API rate-limit handling (unauthenticated = 60 req/hr, easily
exhausted in CI). The lang-* modules use PyPI/npm which return JSON reliably and
don't require auth; GitHub API is a different surface.

**My lean:** NO live probe in the python step. Reasons: (1) the agent already does
MCP-assisted research at init; (2) a live GH API probe in every CI-module write would
hit rate limits in CI pipelines; (3) the `--refresh` path already handles
intentional action-major updates. Keep the python step network-free and let the
agent's steering + context7 carry the version research.

### OQ-2 — How should the `ci_plan` be stored in `answers.toml`? (MED)

The `ci_plan` is a structured document (jobs, matrix, action refs, commands-by-job).
Two options for agent-steered answer storage:

**A — Flat scalar keys** (`ci_plan_jobs`, `ci_plan_action_refs`, `ci_plan_matrix`,
`ci_plan_commands`): each as a JSON-serialized string or list. Consistent with how
`pinned_deps` / `dev_deps` are stored in lang-python (as lists). Easy to inspect in
`answers.toml`.

**B — Single JSON blob** (`ci_plan`): the entire plan as one JSON-encoded string.
Simpler agent contract (one key to emit); harder to inspect/diff in `answers.toml`;
harder to `--refresh` a single aspect.

**My lean: A (flat scalar keys).** Follows the lang-* precedent, is inspectable,
and allows `--refresh ci-github-actions.ci_plan_action_refs` to refresh only the
action refs without re-resolving the full job graph. The implementation maps the
agent's structured output to flat keys during `merge_module_answers_to_persist`.

### OQ-3 — Should the module support a `ci_matrix_versions` input for multi-version matrix? (LOW)

FR-015 specifies matrix trimming to the single frozen `python_version`. A future
`ci_matrix_versions` input could allow the agent (or the user via interview) to
specify `[3.11, 3.12, 3.13]` for a broader matrix. This is out of scope for 007 but
would require: (a) a new `[[inputs]]` key in module.toml, (b) the agent referencing
it, (c) the trimming logic in FR-015 becoming conditional.

**My lean:** Leave it out of scope for 007 (as the spec says). Add a TODO comment
in module.toml and the steering doc so a future spec can add it cleanly. The single-
version matrix is the right default (anti-goal: over-broad matrices burn minutes).

## ASSUMPTIONS made (flagged so they can be corrected)

1. The roadmap's description "validates every command against real justfile
   recipes/manifest scripts" means drop-with-warning (not hard-error) on unknown
   recipes. Hard-erroring would break projects where the justfile hasn't been
   customised yet (the skeleton stubs are `TODO: ...`). Drop-with-warning matches
   the WARN pattern used throughout the lang-* modules.
2. `ubuntu-latest` is acceptable for all generated jobs. Projects with macOS/Windows
   requirements are out of scope; if this is wrong, a `ci_runner` input can be added.
3. The `# ///` stdlib-only constraint (`dependencies = []`) holds for the CI module.
   If `pyyaml` were allowed, the YAML renderer would be simpler; but consistency with
   the rest of the codebase (all modules are stdlib-only) means we must hand-roll the
   renderer (which is straightforward for the CI YAML shape).
4. The agent step has access to the full frozen answer set for ALL active lang-*
   overlays via its context dict (the two-phase plan). If a lang-* module is enabled
   but its agent step has not run before the CI agent step (impossible given Phase A
   ordering), the CI agent would see the pre-Phase-A interview answers only.
   The `after` ordering constraint in `[order]` documents the intended dependency
   but does not enforce agent-step ordering within Phase A — confirm the Phase A
   ordering is stable enough to guarantee this (verify in `runner/reproduce.py`
   `run_agent_phase` before implementing).
5. The gate shows the rendered `ci_plan` (not the final rendered YAML) via the
   `{decision}` token. The final byte-identical YAML is produced by the python step
   AFTER the gate confirms. The gate message contains enough information (jobs,
   matrix, action refs, commands) for meaningful human review without being the exact
   YAML bytes.

## AS-BUILT (TBD)

_Not yet implemented. This section will be filled after implementation to record
refinements, surprising interactions, and deviations from the spec._
