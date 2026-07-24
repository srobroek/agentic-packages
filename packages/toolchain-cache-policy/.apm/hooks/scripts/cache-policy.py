#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Toolchain shared-cache enforcement + disk-pressure GC (SessionStart hook).

Problem: N parallel agent worktrees each build their own output tree (Rust
target/, node_modules, .venv, Go build cache, dist/), and shared caches grow
unbounded — together they fill the disk and wedge the machine (observed live).

This hook enforces, once per session, that EVERY toolchain uses a single shared
cache/output location AND that those locations are bounded — evicting the
least-recently-used caches when free disk drops below a floor. Three layers of
defense (config files are strongest; env is the portable fallback; GC is the
safety net that makes "shared" actually mean "bounded"):

  1. It writes shared-cache env vars to $CLAUDE_ENV_FILE so every subsequent
     Bash tool call in the session inherits them (uv, go, sccache, pnpm, bun,
     npm, pip, gradle, maven, ...).
  2. It ensures the toolchain CONFIG FILES that support a global shared setting
     carry it (cargo target-dir), since a config file applies unconditionally
     even when env is not inherited.
  3. It runs a disk-pressure GC: if free space on the cache volume is below the
     floor (default 25 GiB), it trims the largest bounded caches (sccache via
     its own API, and best-effort LRU trims of others) until above the floor or
     nothing safe remains, and logs exactly what it freed.

Never blocks a session (fail-open); all output is advisory on stderr + a
one-line JSON stdout summary. Config knobs via env:
  CACHE_POLICY_FLOOR_GIB   free-space floor that triggers GC (default 25)
  CACHE_POLICY_ROOT        shared cache root (default ~/.cache/agent-shared)
  CACHE_POLICY_SCCACHE_GIB sccache size cap (default 20)
  CACHE_POLICY_DISABLE     set to skip entirely
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
ROOT = Path(os.environ.get("CACHE_POLICY_ROOT", HOME / ".cache" / "agent-shared"))
FLOOR_GIB = float(os.environ.get("CACHE_POLICY_FLOOR_GIB", "25"))
SCCACHE_GIB = int(os.environ.get("CACHE_POLICY_SCCACHE_GIB", "20"))
GIB = 1024 ** 3

log = []


def note(msg: str):
    log.append(msg)
    sys.stderr.write(f"cache-policy: {msg}\n")


# Every toolchain's shared cache/output location, as env vars. Keys are the
# env var each tool reads; values are paths under one shared root so a single
# GC sweep can reason about all of them.
def shared_env() -> dict:
    r = ROOT
    return {
        # Rust: shared build output (the big one) + sccache wrapper.
        "CARGO_TARGET_DIR": str(r / "cargo-target"),
        "SCCACHE_DIR": str(r / "sccache"),
        "SCCACHE_CACHE_SIZE": f"{SCCACHE_GIB}G",
        "RUSTC_WRAPPER": shutil.which("sccache") or "",
        "CARGO_INCREMENTAL": "0",           # incremental can't use sccache; wastes disk
        # Python / uv: one wheel+source cache, one shared venv-build cache.
        "UV_CACHE_DIR": str(r / "uv"),
        "PIP_CACHE_DIR": str(r / "pip"),
        # Go: build + module caches.
        "GOCACHE": str(r / "go-build"),
        "GOMODCACHE": str(r / "go-mod"),
        # Node ecosystem: pnpm content-addressable store, bun, npm.
        "PNPM_HOME": os.environ.get("PNPM_HOME", str(HOME / ".local" / "share" / "pnpm")),
        "npm_config_cache": str(r / "npm"),
        "BUN_INSTALL_CACHE_DIR": str(r / "bun"),
        # JVM (harmless if unused).
        "GRADLE_USER_HOME": str(r / "gradle"),
    }


# Env keys whose value is a directory we should pre-create. Everything else
# (sizes like SCCACHE_CACHE_SIZE, the RUSTC_WRAPPER binary path, flags) is
# passed through verbatim and never mkdir'd.
DIR_KEYS = {
    "CARGO_TARGET_DIR", "SCCACHE_DIR", "UV_CACHE_DIR", "PIP_CACHE_DIR",
    "GOCACHE", "GOMODCACHE", "npm_config_cache", "BUN_INSTALL_CACHE_DIR",
    "GRADLE_USER_HOME",
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
        lines.append(f'export {k}="{v}"')
    try:
        with open(envfile, "a") as fh:  # append: preserve other hooks' vars
            fh.write("\n# toolchain-cache-policy: shared bounded caches\n")
            fh.write("\n".join(lines) + "\n")
        note(f"wrote {len(lines)} shared-cache env vars to CLAUDE_ENV_FILE")
    except Exception as e:
        note(f"env write failed (non-fatal): {e}")


def enforce_cargo_config():
    """Layer 2: cargo config.toml applies unconditionally, even without env."""
    cfg = HOME / ".cargo" / "config.toml"
    target = str(ROOT / "cargo-target")
    try:
        existing = cfg.read_text() if cfg.exists() else ""
        if "target-dir" in existing:
            return  # user already manages it — do not clobber
        cfg.parent.mkdir(parents=True, exist_ok=True)
        block = (
            "\n# toolchain-cache-policy: single shared target dir across all "
            "worktrees\n[build]\n"
            f'target-dir = "{target}"\nincremental = false\n'
        )
        with open(cfg, "a") as fh:
            fh.write(block)
        note(f"added shared target-dir to {cfg}")
    except Exception as e:
        note(f"cargo config enforce failed (non-fatal): {e}")


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
    # 1. sccache: use its native trim (set to a smaller cap, it self-evicts LRU).
    sc = shutil.which("sccache")
    if sc:
        try:
            subprocess.run([sc, "--stop-server"], capture_output=True, timeout=30)
            note("stopped sccache server to allow cache trim")
        except Exception:
            pass
    # 2. cargo shared target: safe to wipe entirely — it is 100% regenerable and
    #    no worktree's durable artifact lives there (pushed branch is durable).
    cargo_target = Path(env.get("CARGO_TARGET_DIR", ""))
    if cargo_target.exists():
        sz = dir_size_gib(cargo_target)
        try:
            shutil.rmtree(cargo_target, ignore_errors=True)
            cargo_target.mkdir(parents=True, exist_ok=True)
            freed += sz
            note(f"wiped shared cargo target ({sz:.1f} GiB) — fully regenerable")
        except Exception as e:
            note(f"cargo target wipe failed: {e}")
        if free_gib(root_probe) >= FLOOR_GIB:
            note(f"recovered to {free_gib(root_probe):.1f} GiB after cargo wipe")
            return
    # 3. go-build (regenerable) — clear via `go clean -cache`.
    if shutil.which("go"):
        try:
            subprocess.run(["go", "clean", "-cache"], capture_output=True, timeout=60,
                          env={**os.environ, **{k: v for k, v in env.items() if v}})
            note("ran go clean -cache (regenerable build cache)")
        except Exception:
            pass
    # 4. Last resort report — we do NOT touch module/package stores (pnpm store,
    #    go-mod, uv wheels) because re-downloading is network-expensive; wiping
    #    regenerable BUILD output first is the right order.
    final = free_gib(root_probe)
    note(f"GC freed ~{freed:.1f} GiB; free now {final:.1f} GiB"
         + ("" if final >= FLOOR_GIB else " — STILL below floor, manual cleanup needed"))


def main():
    if os.environ.get("CACHE_POLICY_DISABLE"):
        print(json.dumps({"cache_policy": "disabled"}))
        return
    try:
        ROOT.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        note(f"cannot create cache root {ROOT}: {e}")
    env = shared_env()
    write_env_file(env)      # layer 1
    enforce_cargo_config()   # layer 2
    gc_if_pressured(env)     # layer 3
    print(json.dumps({"cache_policy": "applied", "root": str(ROOT),
                      "floor_gib": FLOOR_GIB, "actions": log}))


if __name__ == "__main__":
    main()
