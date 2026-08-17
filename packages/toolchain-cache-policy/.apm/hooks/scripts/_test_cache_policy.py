#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Self-test for cache-policy.py (spec 002 scaling). Fixture-driven, no real
caches touched — uses a temp CACHE_POLICY_ROOT + temp CLAUDE_ENV_FILE."""
import json
import os
import shlex
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


def run(root, envfile, floor, extra=None, args=None):
    env = {**os.environ, "CACHE_POLICY_FLOOR_GIB": str(floor)}
    env.pop("CACHE_POLICY_ROOT", None)
    if root:
        env["CACHE_POLICY_ROOT"] = root
    if envfile:
        env["CLAUDE_ENV_FILE"] = envfile
    env.update(extra or {})
    p = subprocess.run([sys.executable, SCRIPT, *(args or [])],
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
    for key in ("UV_CACHE_DIR", "GOCACHE", "GOMODCACHE", "npm_config_cache",
                "pnpm_config_store_dir", "BUN_INSTALL_CACHE_DIR", "SCCACHE_DIR",
                "GRADLE_USER_HOME", "NUGET_PACKAGES", "GOLANGCI_LINT_CACHE",
                "TRIVY_CACHE_DIR", "RESTIC_CACHE_DIR"):
        check(f"env has {key}", f"export {key}=" in content)
    check("env never sets a global cargo target", "CARGO_TARGET_DIR" not in content)
    check("Go modules use the managed directory name",
          f"export GOMODCACHE={shlex.quote(root + '/go-modules')}" in content)

    quoted_root = os.path.join(td, "shared cache")
    quoted_envfile = os.path.join(td, "quoted-env.sh")
    Path(quoted_envfile).write_text("")
    run(quoted_root, quoted_envfile, floor=0)
    quoted_content = Path(quoted_envfile).read_text()
    check("env shell-quotes cache paths",
          f"export GOMODCACHE={shlex.quote(quoted_root + '/go-modules')}"
          in quoted_content)

    # Rust incremental output is disabled only when sccache will replace it.
    fake_bin = Path(td) / "bin"
    fake_bin.mkdir()
    fake_sccache = fake_bin / "sccache"
    fake_sccache.write_text("#!/bin/sh\nexit 0\n")
    fake_sccache.chmod(0o755)
    sccache_envfile = os.path.join(td, "sccache-env.sh")
    Path(sccache_envfile).write_text("")
    run(root, sccache_envfile, floor=0, extra={"PATH": str(fake_bin)})
    sccache_content = Path(sccache_envfile).read_text()
    check("sccache configures the Rust compiler wrapper",
          f"export RUSTC_WRAPPER={shlex.quote(str(fake_sccache))}"
          in sccache_content)
    check("sccache disables incompatible Cargo incremental output",
          "export CARGO_INCREMENTAL=0" in sccache_content)

    no_sccache_envfile = os.path.join(td, "no-sccache-env.sh")
    Path(no_sccache_envfile).write_text("")
    run(root, no_sccache_envfile, floor=0, extra={"PATH": ""})
    no_sccache_content = Path(no_sccache_envfile).read_text()
    check("missing sccache leaves RUSTC_WRAPPER unset",
          "RUSTC_WRAPPER" not in no_sccache_content)
    check("missing sccache leaves Cargo incremental behavior unchanged",
          "CARGO_INCREMENTAL" not in no_sccache_content)

    # The managed machine cache root is the default unless explicitly overridden.
    development_root = os.path.join(td, "development")
    default_envfile = os.path.join(td, "default-env.sh")
    Path(default_envfile).write_text("")
    out, _ = run(
        None,
        default_envfile,
        floor=0,
        extra={"DEVELOPMENT_CACHE_HOME": development_root},
    )
    check("DEVELOPMENT_CACHE_HOME is the default root",
          out.get("root") == development_root, str(out))

    fallback_home = os.path.join(td, "fallback-home")
    fallback_envfile = os.path.join(td, "fallback-env.sh")
    Path(fallback_envfile).write_text("")
    out, _ = run(
        None,
        fallback_envfile,
        floor=0,
        extra={"HOME": fallback_home, "DEVELOPMENT_CACHE_HOME": ""},
    )
    check("home cache is the final fallback",
          out.get("root") == os.path.join(fallback_home, ".cache", "development"),
          str(out))

    # 2. no GC above floor
    out, _ = run(root, envfile, floor=0)
    check("no GC when above floor", not any("PRESSURE" in a for a in out.get("actions", [])))

    # 3. GC wipes regenerable sccache under pressure, recreates it empty
    junk = Path(root) / "sccache" / "junk"
    junk.mkdir(parents=True, exist_ok=True)
    (junk / "big").write_bytes(b"x" * (5 * 1024 * 1024))
    out, _ = run(root, envfile, floor=10 ** 9)  # impossible floor -> force GC
    acts = " ".join(out.get("actions", []))
    check("GC detected pressure", "PRESSURE" in acts, acts)
    check("GC wiped sccache", "wiped sccache" in acts, acts)
    check("sccache recreated empty", (Path(root) / "sccache").is_dir()
          and not any((Path(root) / "sccache").iterdir()))

    # 4. disable knob
    out, _ = run(root, envfile, floor=0, extra={"CACHE_POLICY_DISABLE": "1"})
    check("disable knob skips", out.get("cache_policy") == "disabled", str(out))

    # 5. fail-open: no CLAUDE_ENV_FILE still returns applied (env layer skipped)
    out, _ = run(root, None, floor=0)
    check("no CLAUDE_ENV_FILE -> still applied (fail-open)", out.get("cache_policy") == "applied")

    # 6. invalid knobs fail open with a valid summary
    invalid_envfile = os.path.join(td, "invalid-env.sh")
    Path(invalid_envfile).write_text("")
    out, p = run(root, invalid_envfile, floor="not-a-number",
                 extra={"CACHE_POLICY_SCCACHE_GIB": "not-a-number"})
    check("invalid knobs fail open", p.returncode == 0
          and out.get("cache_policy") == "applied", str(out))

    # 7. Codex receives valid context instead of an unusable Claude env file
    codex_envfile = os.path.join(td, "codex-env.sh")
    Path(codex_envfile).write_text("")
    out, p = run(root, codex_envfile, floor=0, args=["--codex"])
    hook_output = out.get("hookSpecificOutput", {})
    check("Codex hook exits successfully", p.returncode == 0, str(out))
    check("Codex hook uses SessionStart output contract",
          hook_output.get("hookEventName") == "SessionStart", str(out))
    check("Codex hook reports environment limitation",
          "does not persist environment changes" in
          hook_output.get("additionalContext", ""), str(out))
    check("Codex hook does not write Claude env file",
          Path(codex_envfile).read_text() == "")

print()
print(f"cache-policy self-test: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
