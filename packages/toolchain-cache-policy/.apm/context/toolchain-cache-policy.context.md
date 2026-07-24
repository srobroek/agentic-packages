# Toolchain Cache Policy

Shared, bounded build/cache locations across all worktrees and clones. Stops N
parallel agent worktrees from each growing a multi-GB build tree and filling
the disk.

ENFORCEMENT (three layers, strongest first)
MUST Config files own the shared location where the toolchain supports it —
  they apply unconditionally, even when a subprocess does not inherit env.
  `~/.cargo/config.toml` `[build] target-dir` is the canonical example; the
  SessionStart hook adds it if absent (never clobbers a user-set value).
MUST Env layer: the SessionStart hook writes shared-cache env to
  `CLAUDE_ENV_FILE` so every subsequent Bash call inherits it — `CARGO_TARGET_DIR`,
  `SCCACHE_DIR`, `UV_CACHE_DIR`, `PIP_CACHE_DIR`, `GOCACHE`, `GOMODCACHE`,
  `npm_config_cache`, `BUN_INSTALL_CACHE_DIR`, `GRADLE_USER_HOME`, plus
  `RUSTC_WRAPPER=sccache` and `CARGO_INCREMENTAL=0`.
MUST Static invariants also live in `settings.json` `env` (no expansion there —
  literal values only) for the ones that never change per machine.

BOUNDED, NOT JUST SHARED
MUST A shared cache still grows unbounded without eviction — that is the trap
  that fills disks despite sharing. The hook runs a disk-pressure GC: below the
  free-space floor (default 25 GiB, `CACHE_POLICY_FLOOR_GIB`) it evicts
  REGENERABLE build output first (cargo target, `go clean -cache`, sccache
  trim), in that order, and stops when above the floor.
NOT Evict module/package DOWNLOAD stores (pnpm store, go-mod, uv wheels, npm)
  under pressure — re-downloading is network-expensive; wiping regenerable
  BUILD output is always the right first move. Only report if build-output
  eviction is insufficient.

WORKTREE OUTPUT
MUST Regenerable build output (Rust `target/`, `node_modules`, `.venv`,
  `dist/`, `__pycache__`) is reclaimable as soon as a git-kind node reports and
  pushes — the durable artifact is the pushed branch, not the build tree. The
  orchestrate wipe-worktree wisp reclaims the checkout at merge; build output
  can go earlier.

KNOBS (env)
DEFAULT `CACHE_POLICY_FLOOR_GIB` free-space floor (25) · `CACHE_POLICY_ROOT`
  shared root (`~/.cache/agent-shared`) · `CACHE_POLICY_SCCACHE_GIB` sccache cap
  (20) · `CACHE_POLICY_DISABLE` skip entirely.

FAIL-OPEN
MUST The hook never blocks a session. Missing tools, unwritable paths, or a GC
  that cannot reach the floor all degrade to an advisory stderr line + a JSON
  stdout summary; the session proceeds.
