#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Self-test for cache-policy.py (spec 002 scaling). Fixture-driven, no real
caches touched — uses a temp CACHE_POLICY_ROOT + temp CLAUDE_ENV_FILE."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "cache-policy.py")
passed = 0
failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok   {name}")
    else:
        failed += 1
        print(f"  FAIL {name}  {detail}")


def run(root, envfile, floor, extra=None):
    env = {**os.environ, "CACHE_POLICY_ROOT": root, "CACHE_POLICY_FLOOR_GIB": str(floor)}
    if envfile:
        env["CLAUDE_ENV_FILE"] = envfile
    env.update(extra or {})
    p = subprocess.run(["uv", "run", "--quiet", SCRIPT],
                       input='{"hook_event_name":"SessionStart"}',
                       capture_output=True, text=True, env=env, timeout=120)
    try:
        out = json.loads(p.stdout.strip().splitlines()[-1])
    except Exception:
        out = {}
    return out, p


with tempfile.TemporaryDirectory() as td:
    root = os.path.join(td, "shared")
    envfile = os.path.join(td, "env.sh")
    Path(envfile).write_text("")

    # 1. env layer writes all shared-cache exports
    out, _ = run(root, envfile, floor=0)
    check("returns applied", out.get("cache_policy") == "applied", str(out))
    content = Path(envfile).read_text()
    for key in ("CARGO_TARGET_DIR", "UV_CACHE_DIR", "GOCACHE", "GOMODCACHE",
                "npm_config_cache", "BUN_INSTALL_CACHE_DIR", "SCCACHE_DIR"):
        check(f"env has {key}", f"export {key}=" in content)
    check("env points cargo target under root", root in content)

    # 2. no GC above floor
    out, _ = run(root, envfile, floor=0)
    check("no GC when above floor", not any("PRESSURE" in a for a in out.get("actions", [])))

    # 3. GC wipes regenerable cargo target under pressure, recreates it empty
    junk = Path(root) / "cargo-target" / "junk"
    junk.mkdir(parents=True, exist_ok=True)
    (junk / "big").write_bytes(b"x" * (5 * 1024 * 1024))
    out, _ = run(root, envfile, floor=10 ** 9)  # impossible floor -> force GC
    acts = " ".join(out.get("actions", []))
    check("GC detected pressure", "PRESSURE" in acts, acts)
    check("GC wiped cargo target", "wiped shared cargo target" in acts, acts)
    check("cargo target recreated empty", (Path(root) / "cargo-target").is_dir()
          and not any((Path(root) / "cargo-target").iterdir()))

    # 4. disable knob
    out, _ = run(root, envfile, floor=0, extra={"CACHE_POLICY_DISABLE": "1"})
    check("disable knob skips", out.get("cache_policy") == "disabled", str(out))

    # 5. fail-open: no CLAUDE_ENV_FILE still returns applied (env layer skipped)
    out, _ = run(root, None, floor=0)
    check("no CLAUDE_ENV_FILE -> still applied (fail-open)", out.get("cache_policy") == "applied")

print()
print(f"cache-policy self-test: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
