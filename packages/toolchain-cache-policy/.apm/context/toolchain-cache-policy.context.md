# Toolchain Cache Policy

Shared, bounded download and compiler caches across worktrees and clones.
Repository outputs remain repository-scoped or worktree-local.

ENFORCEMENT
MUST Claude SessionStart writes shared-cache env to `CLAUDE_ENV_FILE`:
  sccache, uv/pip, Go build/modules, npm/pnpm/Bun/Deno, pre-commit/Ruff,
  golangci-lint, Gradle, NuGet, Trivy, and Restic.
MUST Codex SessionStart cannot persist process environment changes. It runs
  the same disk-pressure eviction and injects context telling the user to
  configure the cache variables in the Codex launcher or direnv.
MUST Maven keeps its native user-level `~/.m2/repository`; no portable
  directory-only environment variable exists across supported Maven versions.
MUST Cargo final/link output is absent from this policy. Worktrunk creates one
  absolute `dirname(git-common-dir)/target` per repository.
NOT Set `CARGO_TARGET_DIR` or a global Cargo `[build].target-dir`.

BOUNDED, NOT JUST SHARED
MUST A shared cache still grows unbounded without eviction -- that is the trap
  that fills disks despite sharing. The hook runs a disk-pressure GC: below the
  free-space floor (default 25 GiB, `CACHE_POLICY_FLOOR_GIB`) it evicts
  regenerable sccache and Go build-cache output, then stops when above the
  floor.
NOT Evict module/package DOWNLOAD stores (pnpm store, go-modules, uv wheels, npm)
  under pressure. Only report if compiler-cache eviction is insufficient.

WORKTREE OUTPUT
MUST Regenerable build output (Rust `target/`, `node_modules`, `.venv`,
  `dist/`, `__pycache__`) is not redirected into a machine-global writable
  directory. Rust target output is repository-scoped; other mutable output is
  worktree-local and reclaimable with the checkout.

KNOBS (env)
DEFAULT `CACHE_POLICY_FLOOR_GIB` free-space floor (25) · `CACHE_POLICY_ROOT`
  explicit root override · `DEVELOPMENT_CACHE_HOME` managed root
  (`~/.cache/development` fallback) · `CACHE_POLICY_SCCACHE_GIB` sccache cap
  (20) · `CACHE_POLICY_DISABLE` skip entirely.

FAIL-OPEN
MUST The hook never blocks a session. Missing tools, unwritable paths, or a GC
  that cannot reach the floor all degrade to an advisory stderr line + a JSON
  stdout summary; the session proceeds.
