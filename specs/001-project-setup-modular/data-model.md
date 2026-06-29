# Data Model: Modular, Config-Driven project-setup

Companion to [plan.md](./plan.md). Defines the runtime dataclasses, the on-disk
file shapes, and the full module-migration map.

## Core dataclasses (runner library)

All live in the runner library; `contracts.py` owns the shared ones.

```
# contracts.py — imported by every subsystem
SetupError      { error_code: str, module_id: str | None, module_ids: list[str],
                  expected: str, received: str, how_to_fix: str }   # JSON-serializable
ERROR_CODES     = { UV_MISSING, ID_COLLISION, DEPENDENCY_CYCLE, MISSING_REQUIRES,
                    MISSING_ANSWER, MISSING_REQUIRED_TOOL, FORBIDDEN_FIELD,
                    UNKNOWN_FIELD, INPUT_VALUE_INVALID, MANIFEST_MALFORMED,
                    PLAN_MALFORMED, RESULT_SHAPE, PATH_ESCAPE, FETCH_FAILED }
Provenance      = enum { default, flag, home, project, derived, agent-steered }
ModuleResult    { schema_version: int, module_id: str, step_id: str,
                  status: 'ok'|'error', files_written: list[str], diffs: list[Diff],
                  answers_to_persist: dict[str, {value, source: Provenance}],
                  warnings: list[str], message: str, error: SetupError | None }

# manifest.py
ModuleManifest  { meta: {repository, author},
                  module: {id, name, version, description, reconcile: bool,
                           default_enabled: bool | None},        # tri-state (FR-035)
                  order: {requires: list, after: list, before: list},
                  tools: {required: list[str]},
                  inputs: list[InputSpec], steps: list[StepSpec] }
InputSpec       { key, type: InputType, prompt, choices: list|None,
                  default: Any|None, required: bool }
InputType       = enum { string, text, int, bool, choice, multichoice, path, list }
StepSpec        { id, kind: 'python'|'agent'|'gate',
                  steering: str|None,      # kind=agent
                  message: str|None }      # kind=gate

# plan.py — the frozen plan (one shared model; builder=validator, reader=sdk)
ExecutionPlan   { schema_version: int, mode: 'init'|'reproduce',
                  modules: dict[str, PlanModule], order: list[str] }   # NO absolute paths in Tier-1 fields
PlanModule      { id, version, reconcile: bool, steps: list[StepSpec],
                  answers: dict[str, Any],          # coerced ONCE
                  module_rel_root: str }            # relative to plugin root, not absolute
```

## On-disk file shapes (committed)

`.project-setup/sources.toml`
```toml
[meta]
skill_version = "0.3.0"            # advisory; clone on mismatch warns, proceeds

[[source]]
locator = "github.com/me/mods"     # owner/repo[/subdir]
ref      = "main"                  # floating allowed
subdir   = "modules"               # optional
```

`.project-setup/answers.toml`  (per-module section + parallel per-key provenance)
```toml
[module.core-identity]
name    = "acme-api"
org     = "acme"
license = "mit"

[module.core-identity.source]      # per-key provenance
name    = "flag"
org     = "home"
license = "project"

[module.gitignore-generate]
templates = ["macos", "linux", "python"]
[module.gitignore-generate.source]
templates = "derived"
```

## Runtime artifacts (NOT committed; in `~/.cache/project-setup/`)

- `git/<cache-key>/` — fetched source checkouts (mirrors APM's cache model)
- `plan.json` — the frozen execution plan passed as `uv run module.py --plan ...`
  (canonical: `json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)+"\n"`)

## Module migration map (Phase 4)

Tier is per-step (`python`=Tier-1 byte-identical, `agent`=Tier-2, `gate`=confirm).
"R" = reconcile capability. Order via `requires`/`after`.

| Module id | default | R | Tier(s) | Key inputs | order | Notes |
|-----------|:---:|:---:|---|---|---|---|
| `core-identity` | ✓ | – | answers-only | name, org, description, layout(choice), license(choice), public(bool), create_repo(bool), init_git(bool) | — | upstream of most; no filesystem step (zero-step allowed — see Phase-0 amend) |
| `git-init` | ✓ | – | python | init_git | requires core-identity | `git init`; macOS provenance-xattr clear; **Codex read-only preflight** |
| `github-repo` | ✓ | – | python | create_repo, public, org, name, description | after git-init | gh-api.py→gh; ensure origin; failures→warn |
| `dirs-scaffold` | ✓ | ✓ | python | layout, targets | requires core-identity | exact legacy DIRS[] (21) + monorepo TARGETS (15) golden fixtures |
| `agents-md` | ✓ | ✓ | python | layout | after dirs-scaffold | single/monorepo heredocs → templates/ (preserve text quirks) |
| `codex-config` | ✓ | ✓ | python | — | after dirs-scaffold | `.codex/config.toml` skeleton (the trivial reference module built first) |
| `justfile-write` | ✓ | ✓ | python | use_just(bool) | — | template heredoc |
| `license-write` | ✓ | – | python | license, author | requires core-identity | apache-2.0 / mit templates (year/author vary → SC-001 carve-out) |
| `gitignore-generate` | ✓ | ✓ | python | templates(multichoice), dynamic_fetch(bool) | after dirs-scaffold | vendored CC0 + on-demand github/gitignore; **parity target = static-fallback heredoc** |
| `precommit-setup` | ✓ | ✓ | python | — | after dirs-scaffold | exact legacy hook set + vendored close-keywords copy + `pre-commit install` |
| `apm-install` | ✓ | – | python+gate | agentic_packages, baseline_mcp, selected_*, compile_claude | after all capability modules | unions every module's apm deps; ports run_apm chain; install/compile/patch/audit |
| `speckit-bridge` | – | – | python | spec_mode(choice none/lightweight/full) | after apm-install | delegates to speckit pkg setup-speckit.sh (subprocess) |
| `lang-ts` | – | ✓ | python | target, package_manager, framework, ui_kit | after gitignore-generate, precommit-setup | NOT byte-identical (runs installers); preserve gitignore grep-markers |
| `lang-python` | – | ✓ | python | python_version, framework | after gitignore-generate, precommit-setup | ruff/pytest/pyright; `__pycache__` marker |
| `lang-go` | – | ✓ | python | module_path, app_kind | after gitignore-generate, precommit-setup | `*.test` marker; module from git remote |
| `lang-rust` | – | ✓ | python | crate_kind, workspace | after gitignore-generate, precommit-setup | `/target` marker; clippy/rustfmt |
| `quality-hooks` | ✓ | ✓ | python | quality_languages(list) | after lang-* | sorted-unique `.agents/hooks/quality-languages` (defaults via interview layering, NOT cross-module reach) |
| `package-add` | – | – | python | name, lang, dir | (standalone) | **path-traversal guards** (reject `..`/abs/sep); workspace-root detection |

Golden-file fixtures to capture verbatim from the monolith: `DIRS[]` (lines
265–286), monorepo `TARGETS` (288–306), both AGENTS.md heredocs (478–585),
default `core@srobroek-agentic` + 4 baseline MCP packages (82–87), pre-commit
config (377–434).
