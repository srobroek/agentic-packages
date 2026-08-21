#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Shared download/compiler caches plus disk-pressure GC (SessionStart hook).

Package-manager downloads and content-addressed compiler results should be
shared across worktrees. Mutable dependencies and branch-derived output must
not be redirected into a machine-global writable directory.

This hook writes safe cache locations to Claude's session environment and
evicts only regenerable compiler caches when free disk drops below a floor.
Codex cannot persist hook environment changes, so its target-specific mode
emits valid SessionStart context describing the launcher/direnv setup:

  1. $CLAUDE_ENV_FILE receives cache variables for sccache, Python, Go, Node,
     Deno, Gradle, and NuGet.
  2. Disk-pressure GC removes sccache and the Go build cache.

Cargo target output is intentionally absent. Worktrunk materializes an absolute
repository-scoped target in each linked checkout because Cargo cannot derive
that path from a static global config.

Never blocks a session (fail-open). Config knobs via env:
  CACHE_POLICY_FLOOR_GIB   free-space floor that triggers GC (default 25)
  CACHE_POLICY_ROOT        explicit shared cache root override
  DEVELOPMENT_CACHE_HOME   managed shared cache root (default)
  CACHE_POLICY_SCCACHE_GIB sccache size cap (default 20)
  CACHE_POLICY_DISABLE     set to skip entirely
"""
from __future__ import annotations

import json
import math
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

GIB = 1024 ** 3


def _float_env(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) and value >= 0 else default


def _int_env(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value >= 0 else default


HOME = Path.home()
ROOT = Path(
    os.environ.get("CACHE_POLICY_ROOT")
    or os.environ.get("DEVELOPMENT_CACHE_HOME")
    or HOME / ".cache" / "development"
)
FLOOR_GIB = _float_env("CACHE_POLICY_FLOOR_GIB", 25)
SCCACHE_GIB = _int_env("CACHE_POLICY_SCCACHE_GIB", 20)

log = []


def note(msg: str):
    log.append(msg)
    sys.stderr.write(f"cache-policy: {msg}\n")


# Safe user-level download and compiler caches. Mutable dependency trees and
# branch-derived output do not belong here.
def shared_env() -> dict:
    r = ROOT
    env = {
        "SCCACHE_DIR": str(r / "sccache"),
        "SCCACHE_CACHE_SIZE": f"{SCCACHE_GIB}G",
        "UV_CACHE_DIR": str(r / "uv"),
        "PIP_CACHE_DIR": str(r / "pip"),
        "PRE_COMMIT_HOME": str(r / "pre-commit"),
        "RUFF_CACHE_DIR": str(r / "ruff"),
        "GOCACHE": str(r / "go-build"),
        "GOMODCACHE": str(r / "go-modules"),
        "GOLANGCI_LINT_CACHE": str(r / "golangci-lint"),
        "npm_config_cache": str(r / "npm"),
        "pnpm_config_store_dir": str(r / "pnpm"),
        "BUN_INSTALL_CACHE_DIR": str(r / "bun"),
        "DENO_DIR": str(r / "deno"),
        "GRADLE_USER_HOME": str(r / "gradle"),
        "NUGET_PACKAGES": str(r / "nuget"),
        "TRIVY_CACHE_DIR": str(r / "trivy"),
        "RESTIC_CACHE_DIR": str(r / "restic"),
    }
    sccache = shutil.which("sccache")
    if sccache:
        env.update({"RUSTC_WRAPPER": sccache, "CARGO_INCREMENTAL": "0"})
    return env


# Env keys whose value is a directory we should pre-create. Everything else
# (sizes like SCCACHE_CACHE_SIZE, the RUSTC_WRAPPER binary path, flags) is
# passed through verbatim and never mkdir'd.
DIR_KEYS = {
    "SCCACHE_DIR", "UV_CACHE_DIR", "PIP_CACHE_DIR", "PRE_COMMIT_HOME",
    "RUFF_CACHE_DIR", "GOCACHE", "GOMODCACHE", "GOLANGCI_LINT_CACHE",
    "npm_config_cache", "pnpm_config_store_dir", "BUN_INSTALL_CACHE_DIR",
    "DENO_DIR", "GRADLE_USER_HOME", "NUGET_PACKAGES", "TRIVY_CACHE_DIR",
    "RESTIC_CACHE_DIR",
}


def write_env_file(env: dict):
    """Layer 1: persist shared-cache env for all subsequent Bash calls."""
    envfile = os.environ.get("CLAUDE_ENV_FILE")
    if not envfile:
        note("CLAUDE_ENV_FILE not set (not a SessionStart context?) — env layer skipped")
        return
    lines = []
    for k, v in env.items():
        if not v:
            continue
        if k in DIR_KEYS:
            try:
                Path(v).mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
        lines.append(f"export {k}={shlex.quote(str(v))}")
    try:
        with open(envfile, "a") as fh:  # append: preserve other hooks' vars
            fh.write("\n# toolchain-cache-policy: shared bounded caches\n")
            fh.write("\n".join(lines) + "\n")
        note(f"wrote {len(lines)} shared-cache env vars to CLAUDE_ENV_FILE")
    except Exception as e:
        note(f"env write failed (non-fatal): {e}")


def free_gib(path: Path) -> float:
    try:
        return shutil.disk_usage(path).free / GIB
    except Exception:
        return float("inf")


def dir_size_gib(path: Path) -> float:
    total = 0
    try:
        for p in path.rglob("*"):
            try:
                if p.is_file():
                    total += p.stat().st_size
            except OSError:
                pass
    except Exception:
        pass
    return total / GIB


def gc_if_pressured(env: dict):
    """Layer 3: the safety net. Shared != bounded without eviction."""
    root_probe = ROOT if ROOT.exists() else HOME
    free = free_gib(root_probe)
    if free >= FLOOR_GIB:
        note(f"free {free:.1f} GiB >= floor {FLOOR_GIB:.0f} GiB — no GC needed")
        return
    note(f"DISK PRESSURE: free {free:.1f} GiB < floor {FLOOR_GIB:.0f} GiB — evicting")

    freed = 0.0
    # sccache is fully regenerable. Stop its server before replacing the cache.
    sc = shutil.which("sccache")
    if sc:
        try:
            subprocess.run([sc, "--stop-server"], capture_output=True, timeout=30)
            note("stopped sccache server before cache eviction")
        except Exception:
            pass
    sccache = Path(env.get("SCCACHE_DIR", ""))
    if sccache.exists():
        sz = dir_size_gib(sccache)
        try:
            shutil.rmtree(sccache, ignore_errors=True)
            sccache.mkdir(parents=True, exist_ok=True)
            freed += sz
            note(f"wiped sccache ({sz:.1f} GiB) — fully regenerable")
        except Exception as e:
            note(f"sccache wipe failed: {e}")
        if free_gib(root_probe) >= FLOOR_GIB:
            note(f"recovered to {free_gib(root_probe):.1f} GiB after sccache wipe")
            return
    # Go's build cache is regenerable; the module download store is not touched.
    if shutil.which("go"):
        try:
            subprocess.run(["go", "clean", "-cache"], capture_output=True, timeout=60,
                          env={**os.environ, **{k: v for k, v in env.items() if v}})
            note("ran go clean -cache (regenerable build cache)")
        except Exception:
            pass
    # Last resort report: never touch module/package stores (pnpm store,
    #    go-modules, uv wheels) because re-downloading is network-expensive; wiping
    #    regenerable BUILD output first is the right order.
    final = free_gib(root_probe)
    note(f"GC freed ~{freed:.1f} GiB; free now {final:.1f} GiB"
         + ("" if final >= FLOOR_GIB else " — STILL below floor, manual cleanup needed"))


def codex_context() -> str:
    actions = "; ".join(log)
    summary = f" Hook actions: {actions}" if actions else ""
    return (
        "toolchain-cache-policy ran at Codex SessionStart. Codex does not "
        "persist environment changes made by hooks, so cache variables were "
        "not exported for later commands. Configure DEVELOPMENT_CACHE_HOME "
        "and the cache variables in the Codex launcher or direnv; Cargo "
        "target output remains repository-scoped."
        + summary
    )


def main():
    codex = "--codex" in sys.argv[1:]
    if os.environ.get("CACHE_POLICY_DISABLE"):
        if codex:
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": (
                        "toolchain-cache-policy is disabled by "
                        "CACHE_POLICY_DISABLE."
                    ),
                }
            }))
        else:
            print(json.dumps({"cache_policy": "disabled"}))
        return
    try:
        ROOT.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        note(f"cannot create cache root {ROOT}: {e}")
    env = shared_env()
    if codex:
        note("Codex cannot persist the Claude environment file; context only")
    else:
        write_env_file(env)
    try:
        gc_if_pressured(env)
    except Exception as e:
        note(f"GC failed (non-fatal): {e}")
    if codex:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": codex_context(),
            }
        }))
    else:
        print(json.dumps({"cache_policy": "applied", "root": str(ROOT),
                          "floor_gib": FLOOR_GIB, "actions": log}))


if __name__ == "__main__":
    main()
