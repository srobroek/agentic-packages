# Research: Modular, Config-Driven project-setup

Phase 0 findings. Every entry is a verified fact (checked against the repo or the
live environment) or a resolved design decision, with the decision it drives.

## Verified environment / repo facts

| # | Fact (verified) | Drives |
|---|---|---|
| 1 | `/usr/bin/python3` is 3.9.6 — no `tomllib`, no `tomli`, no TOML writer. `uv`'s python is 3.14 with `tomllib`. | `uv` is a HARD prerequisite; no system-python/stdlib-TOML fallback (FR-005/B2). |
| 2 | Claude plugin install **copies arbitrary files** (verified under `~/.claude/plugins/cache/`: multi-file py packages like hookify `core/*.py`, `rust-toolchain.toml`, whole subtrees). | `module.py`/helpers/templates/steering all arrive on the plugin channel; resolve via plugin root (FR-033, assumptions). |
| 3 | Plugin marketplace entry schema = `name/version/description/tags/source` only — no install/build/postinstall hook. | Deps come from `uv` at RUNTIME, not an install step (FR-006/H1). |
| 4 | Zero `pyproject.toml` anywhere in the repo. `speckit-dag-hooks` is pure-stdlib and imports its module in tests via `importlib.util.spec_from_file_location` (`test_build_nodes.py:44`). | Import-by-file-path for runner tests AND `module.py`→SDK; no packaged/editable install (Phase-0 #4). |
| 5 | Canonical JSON precedent: `build_nodes.py:560` = `json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"`. | The ONE canonical serializer for the frozen plan (Phase-0 #2). |
| 6 | `graphlib.TopologicalSorter` is stdlib; `build_nodes.py:488` uses `.prepare()` to trigger `CycleError`, reads cycle from `exc.args[1]`; yields ready nodes in predecessor-insertion order. | `order.py` topo recipe + cycle extraction (Phase 1.4). |
| 7 | `release-please-config.json` has `tag-separator: "-"` + `include-component-in-tag: true` → single-dash `project-setup-v0.2.0`. Spec H3 wants `--`. | Per-package `tag-separator: "--"` override needed (Phase 5.2; unowned-until-now). |
| 8 | `build_inventory.py:82` discovers skills only via `(.apm/skills)/*/SKILL.md` and classifies skill-vs-bundle on that; render-docs has zero `.claude-plugin` awareness. | Native-root migration MUST land an inventory fix atomically or the repo check-artifacts gate goes red (Phase 5.2). |
| 9 | APM caches git checkouts under `~/.cache/apm/git/checkouts_v1/<hash>/...` (partial/`__p` clones observed). | Mirror the cache model; do NOT assume a usable `checkouts_v1/<sha>` module-root path verbatim (Phase 2). |
| 10 | `apm-discover.sh` already resolves the preferences index via `env > project ./indexes/ > bundled $SCRIPT_DIR/../indexes/` and persists JSON with `json.dumps(sort_keys=True)`. | Generalize this precedence to module search-path + config layering (Phase 1.6/2). |
| 11 | `package-add.sh:50-66` rejects `name` containing `/`, `..`, leading `/`, backslash BEFORE any mkdir; the old bats suite pins 6 such tests. | `package-add` module must port these guards verbatim (Phase 4.11); runner adds `files_written ⊆ project_dir` guard. |
| 12 | The four language overlays call `gitnr create gh:Python|gh:Node|...` where `gh:` = toptal/gitignore.io (the spec's OUT-OF-SCOPE source); only the monolith base uses `ghg:` = github/gitignore (CC0, in-scope). | SC-005 gitignore parity targets each overlay's STATIC FALLBACK heredoc, NOT legacy gitnr output (Phase 4.5). |

## Resolved cross-component contracts (from the coherence review)

The seven subsystems, designed independently, disagreed on every shared
contract. Resolutions (full text in `contracts/`):

- **Frozen-plan schema**: 4 incompatible shapes found → ONE `ExecutionPlan`
  model, builder=manifest-validator, reader=SDK, others consume. One canonical
  serializer (fact #5). Plan lives in `~/.cache`, never in committed
  `.project-setup/`.
- **module.toml schema (FR-009 vs Section I)**: spec-internal contradiction →
  **Section I wins**; FR-009 restated; `FORBIDDEN_FIELD` rejects
  `priority`/`title`/`entrypoint`/`required_answers`.
- **Determinism-tier vocabulary**: module-level `kind` vs step-level `kind` →
  tier is **step-scoped** (derived from step kind); module-level `kind` dropped.
- **Structured-error envelope**: defined 4× → ONE `contracts.py` owner; add
  `module_ids: list` for collision/cycle multi-id errors.
- **Provenance enum**: `{default,flag,home,agent-steered}` was incomplete →
  add `project` (committed re-run value) + `derived` (module-computed). Modules
  emit only `default|derived|agent-steered`; persistence assigns `flag|home|project`.
- **Module result JSON**: `files` vs `files_written` → **`files_written`** everywhere.
- **Cache/path ownership**: triple-defined → `paths.py` is sole owner of all
  path + cache constants; `sources-discovery` owns only the fetch under it.
- **Locator parsing**: double-defined → `sources/locator.py` is sole owner;
  config consumes structured records.
- **Collision rule (FR-011 vs FR-036)**: same-root-kind = hard `ID_COLLISION`;
  cross-precedence = reported shadow (higher wins, logged).
- **Import mechanism**: `importlib.util.spec_from_file_location` (fact #4) for
  both runner tests and `module.py`→SDK; SDK vendored as one file at a known
  plugin-root path.

## Resolved pipeline-ordering bugs

- **Diff/confirm circularity**: disk-drift was to be read from a module's
  *post-execution* output, but confirm must run *pre-write*. → Tier-1 python
  steps gain a `--inspect` dry pass that emits proposed `files_written`+`diffs`
  WITHOUT writing; confirm built from that; real write follows on confirmation,
  with inspect==write guaranteed for Tier-1.
- **Topo vs validate double-raise**: two subsystems both raised on cycle,
  short-circuiting "all problems at once" (FR-017). → `order.py` is pure +
  non-raising; `validate.py` is the only gate, accumulates
  cycle+missing-requires+missing-answer+missing-tool, reports all at once, then orders.
- **Final resolved-answer map unowned**: → `answers.resolve_final_answers()`
  is the single coercion point both validate and plan-freeze consume.

## Open items deferred to /speckit.tasks or flagged

- Coordinate Phase 5.2 (inventory + tag-separator fix) with the parallel
  native-root migration the user flagged — verify together, avoid double-edit.
- `gitignore-generate` on-demand fetch needs an offline network stub/cassette so
  CI stays hermetic; nested `uv run` in tests needs cache pre-warm / `--offline`.
- Whether `--inspect` is a manifest-declared capability or a universal executor
  contract (lean: universal — every Tier-1 python step must support it).

## Phase 5 cutover sequencing (VERIFIED blocker — do not delete old tree yet)

Checked during Phase 5: the parallel native-root tooling migration has NOT
landed. As of this point, `.apm/scripts/build_inventory.py` still discovers
skills ONLY via `.apm/skills/<skill>/SKILL.md` (line ~97), NO package has a
`.claude-plugin/plugin.json`, and `release-please-config.json` still has
`tag-separator: "-"`. Therefore:

- The new runner+modules live at `skills/project-setup/` and COEXIST with the
  legacy `.apm/skills/project-setup/` tree. Both present = nothing breaks; the
  build/inventory gate still sees the legacy skill.
- **T050 (delete `.apm/skills/` tree) MUST NOT run until T051 lands** (inventory
  taught to discover `skills/*/SKILL.md` + read `.claude-plugin/plugin.json`, and
  the `<name>--v<version>` tag-separator override). Deleting now → inventory
  classifies project-setup as skill-less → whole-repo check-artifacts gate goes
  red. This is the atomically-coupled pair the plan called out.
- Decision: finish the additive runner/modules/SKILL.md/tests now; hold the
  cutover (T050+T051) to do atomically once the parallel native-root effort
  lands, and verify together. project-setup is the first native-root package, so
  it is the forcing function for that tooling fix.
