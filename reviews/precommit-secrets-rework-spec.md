# Pre-commit + secrets-scan rework — locked spec

Status: **approved, in build**. Captured from the hook-audit grill (2026-06-26).
Goal: minimal impediment for autonomous agents + tool-agnostic secret enforcement.

## Decision summary

Secret scanning moves from a per-commit PreToolUse client hook to the **git
`pre-push` hook managed by the `pre-commit` framework**, because:

- Agents commit constantly but push rarely → far less cumulative latency.
- A secret is still caught before it leaves the machine (push is the boundary).
- `.pre-commit-config.yaml` is **committed**, so the policy travels with the repo
  and fires on *any* tool's `git push` (Claude, Codex, human, script) — this is
  what "repo config, not client config" requires.

### Honest enforcement limits (acknowledged, not solved)

The git-hook model enforces against our agent **and any contributor who ran
`pre-commit install`**. It does NOT stop:

- a fresh clone that never ran `pre-commit install` (git never auto-wires
  `.git/hooks/` — by design; no client config can close this),
- `git push --no-verify` / `git commit --no-verify`.

True "no one can push secrets regardless of tool" is only achievable
**server-side** (GitHub push protection / secret scanning), which is a GitHub
setting, not a shippable file. project-setup documents enabling it; that is the
real backstop. The local hooks are fast feedback + best-effort, not a guarantee.

## Stages

### Commit stage (fast, auto-fix where possible)

Universal hygiene (`pre-commit-hooks`):
- trailing-whitespace, end-of-file-fixer
- check-merge-conflict, check-added-large-files
- check-yaml, check-json, check-toml, check-case-conflict
- detect-private-key (cheap obvious-key subset; complements push gitleaks)
- check-shebang-scripts-are-executable, check-executable-has-shebang

Lint:
- shellcheck — **commit stage, changed shell files only**

Formatters (one per language, language-detected, changed-files only):

| Language          | Formatter                      |
|-------------------|--------------------------------|
| Python            | `ruff format` + `ruff check --fix` |
| Shell             | `shfmt`                        |
| JS/TS/JSON/CSS    | `biome` (Rust-fast, one tool)  |
| Markdown/YAML     | `prettier` (biome weak here)   |
| Go                | `gofumpt`                      |
| Rust              | `cargo fmt` (rustfmt)          |
| TOML              | `taplo fmt`                    |

biome-for-JS + prettier-for-MD/YAML plays to each tool's strength (biome ~10–20×
faster on the JS bulk; prettier covers MD/YAML which biome doesn't).

### Pre-push stage (heavier, lint-not-fix)

- secrets-scan: gitleaks/trufflehog over the **pushed commit range**.
- Go/Rust slow linters (`golangci-lint`, `clippy`) — too slow for commit.

### Deliberately NOT in pre-commit

Full test suites, slow type-checks, network-bound checks → CI only.

## Build pieces

1. **secrets-scan (retarget, one package)**
   - `scan.sh`: add `--range` mode (`git diff <remote>..<local>` — the staged
     diff is empty at push time) + `--only-verified` on the trufflehog path;
     distinguish scanner *error* from a *finding* (error → warn-and-allow, not
     block, matching the no-scanner path). Keep `--staged`/`--working`, the
     0/1/2 exit contract, and `SECRETS_SCAN_SKIP`.
   - **Remove** the PreToolUse `git commit` client hook.
   - Ship a `repo: local`, `stages: [pre-push]` hook fragment calling
     `scan.sh --range`, for project-setup to merge into `.pre-commit-config.yaml`.
   - Skill (manual scan) stays.

2. **hooks-precommit-gate (new, tiny client hook)**
   - PreToolUse on `git commit` AND `git push`.
   - Block ONLY when `.pre-commit-config.yaml` exists but the framework is not
     wired (`.git/hooks/pre-commit` / `pre-push` missing) → "run `pre-commit
     install`". Also block `--no-verify`. Silent in repos with no config.
   - type:hooks, cross-tool JSONs, bash-3.2 floor, shellcheck-clean, bats tests.

3. **project-setup**
   - Detect+install `pre-commit` (uv/pipx/brew).
   - Write `.pre-commit-config.yaml` (stages above; formatters conditional on
     detected languages).
   - `pre-commit install -t pre-commit -t pre-push`.
   - Add `secrets-scan` + `hooks-precommit-gate` to the install set.
   - Document the fresh-clone `pre-commit install` requirement and the
     server-side-only enforcement limit.

## Interaction with hooks-quality (hook #16, pending review)

`hooks-quality` currently runs formatters as a PostToolUse advisory. Once
pre-commit owns auto-formatting, hooks-quality should stop duplicating that role
(resolve when hook #16 is reviewed) — one formatter system, one config.
