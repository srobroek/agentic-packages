#!/usr/bin/env bats
#
# Tests for the project-setup scaffold scripts (audit/phase-1, setup-scripts stream).
#
# These scripts run under the PORTABILITY FLOOR: bash 3.2.57 + set -euo pipefail
# + BSD sed/grep. The regressions covered here are exactly the failures that
# aborted the DEFAULT (no-flag) code paths on stock macOS:
#
#   1. project-setup.sh: empty TARGETS[@] array under `set -u` -> the default
#      single-layout run crashed before writing any scaffold.
#   2. apm-discover.sh: empty PROFILES[@] array under `set -u` -> the default
#      `apm-discover.sh` (no --profile) crashed before printing preferences.
#   3. package-add.sh: --name path traversal ('../x', absolute, '..') must be
#      rejected BEFORE any mkdir, and --lang validated against the known set.
#   4. setup-{go,python,rust,ts}.sh: a present-but-FAILING gitnr must fall back
#      to a static .gitignore block instead of leaving a broken/truncated file.
#
# All scripts must run with the *system* bash 3.2 (/bin/bash on macOS), never a
# newer homebrew bash, so the guards are exercised under the real floor.

setup() {
  SCRIPTS="${BATS_TEST_DIRNAME}/../.apm/skills/project-setup/scripts"
  BASH32="/bin/bash"

  # Sandboxed work area.
  WORK="$(mktemp -d "${BATS_TMPDIR:-/tmp}/setup-test.XXXXXX")"
  BIN="$WORK/bin"
  mkdir -p "$BIN"

  # --- Stub external tools so the scripts never touch the network or real
  #     git/apm/gh state. Each stub records nothing; it just satisfies the
  #     command-existence checks and returns benign output. ---

  # git: every subcommand is a no-op success, except `config user.name` which
  # prints a value (used by the LICENSE author line).
  cat > "$BIN/git" <<'GIT'
#!/bin/sh
case "$1" in
  config) echo "Test User" ;;
  remote)
    # `git remote get-url origin` must FAIL so the script does not assume a
    # remote; everything else succeeds quietly.
    case "$2" in
      get-url) exit 1 ;;
      *) exit 0 ;;
    esac
    ;;
  *) exit 0 ;;
esac
GIT
  chmod +x "$BIN/git"
}

teardown() {
  [ -n "${WORK:-}" ] && rm -rf "$WORK"
}

# Fail the test if the captured $output contains the given (case-insensitive)
# substring. Written as an explicit if/return so it actually fails the test
# under Bats >= 1.5 (where a bare `! cmd | pipe` does not — see SC2314).
refute_output_contains() {
  if printf '%s' "$output" | grep -qi -- "$1"; then
    echo "expected output NOT to contain: $1" >&2
    echo "--- output ---" >&2
    printf '%s\n' "$output" >&2
    return 1
  fi
}

# Install a fake `apm` that satisfies apm-discover.sh's command surface.
install_fake_apm() {
  cat > "$BIN/apm" <<'APM'
#!/bin/sh
case "$1" in
  --version) echo "apm 0.0.0-fake" ;;
  marketplace)
    case "$2" in
      list) echo "your-marketplace" ;;
      browse) echo "  (fake) no packages" ;;
      add|update) : ;;
      *) : ;;
    esac
    ;;
  *) : ;;
esac
APM
  chmod +x "$BIN/apm"
}

# Install a fake `gitnr` that is PRESENT but always FAILS (the exact adversarial
# case: command -v gitnr succeeds, but `gitnr create` exits non-zero).
install_failing_gitnr() {
  cat > "$BIN/gitnr" <<'GITNR'
#!/bin/sh
echo "gitnr: simulated template failure" >&2
exit 7
GITNR
  chmod +x "$BIN/gitnr"
}

# ---------------------------------------------------------------------------
# 1. Default project-setup (no --target, single layout) writes the scaffold.
# ---------------------------------------------------------------------------
@test "project-setup: default run (no --target) does not crash and writes scaffold" {
  install_failing_gitnr   # ensure .gitignore goes through the fallback path too
  proj="$WORK/proj"
  mkdir -p "$proj"
  run env PATH="$BIN:$PATH" "$BASH32" "$SCRIPTS/project-setup.sh" \
    --name demo --no-repo --no-git \
    --no-apm-install --no-apm-compile --skip-marketplace-register \
    --dir "$proj"
  [ "$status" -eq 0 ]
  # The empty-TARGETS path must have been taken without an "unbound variable".
  refute_output_contains "unbound variable"
  # Core scaffold files exist.
  [ -f "$proj/AGENTS.md" ]
  [ -f "$proj/.gitignore" ]
  [ -f "$proj/.pre-commit-config.yaml" ]
  [ -d "$proj/docs" ]
  [ -d "$proj/specs" ]
  # No monorepo target dirs were created in single layout.
  [ ! -d "$proj/apps" ]
  [ ! -d "$proj/services" ]
}

@test "project-setup: --help strips comment prefix via BSD-safe sed" {
  run env PATH="$BIN:$PATH" "$BASH32" "$SCRIPTS/project-setup.sh" --help
  [ "$status" -eq 0 ]
  # BSD sed must have stripped the leading "# " — no leading hash on the title.
  printf '%s\n' "$output" | grep -q "project-setup — universal project scaffold"
  ! printf '%s\n' "$output" | grep -q "^# project-setup"
}

@test "project-setup: value-taking flag with no value fails fast" {
  run env PATH="$BIN:$PATH" "$BASH32" "$SCRIPTS/project-setup.sh" --name
  [ "$status" -ne 0 ]
  printf '%s' "$output" | grep -q -- "--name needs a value"
}

# ---------------------------------------------------------------------------
# 2. apm-discover with no --profile does not crash (empty PROFILES[@]).
# ---------------------------------------------------------------------------
@test "apm-discover: no --profile run reaches preferences without unbound-variable crash" {
  install_fake_apm
  run env PATH="$BIN:$PATH" APM_PACKAGE_PREFERENCES_FILE="$WORK/nonexistent.json" \
    "$BASH32" "$SCRIPTS/apm-discover.sh" --skip-marketplace-register
  [ "$status" -eq 0 ]
  refute_output_contains "unbound variable"
  refute_output_contains "PROFILES"
  printf '%s' "$output" | grep -q "Preferred package choices:"
}

@test "apm-discover: --help strips comment prefix via BSD-safe sed" {
  run env PATH="$BIN:$PATH" "$BASH32" "$SCRIPTS/apm-discover.sh" --help
  [ "$status" -eq 0 ]
  printf '%s\n' "$output" | grep -q "Resolve APM"
  # The "# Usage:" line must have its hash stripped.
  printf '%s\n' "$output" | grep -q "^Usage:"
}

# ---------------------------------------------------------------------------
# 3. package-add path-traversal + lang validation, BEFORE any mkdir.
# ---------------------------------------------------------------------------
@test "package-add: --name '../x' is rejected before mkdir" {
  proj="$WORK/mono"
  mkdir -p "$proj/packages"
  run env PATH="$BIN:$PATH" "$BASH32" "$SCRIPTS/package-add.sh" \
    --name '../x' --lang ts --dir packages
  [ "$status" -ne 0 ]
  printf '%s' "$output" | grep -q "path separator"
  # Nothing must have been created outside packages/.
  [ ! -e "$proj/x" ]
  [ ! -e "$WORK/x" ]
}

@test "package-add: absolute --name is rejected" {
  run env PATH="$BIN:$PATH" "$BASH32" "$SCRIPTS/package-add.sh" \
    --name '/etc/passwd' --lang ts
  [ "$status" -ne 0 ]
  printf '%s' "$output" | grep -q "path separator"
}

@test "package-add: bare '..' --name is rejected" {
  run env PATH="$BIN:$PATH" "$BASH32" "$SCRIPTS/package-add.sh" \
    --name '..' --lang ts
  [ "$status" -ne 0 ]
  printf '%s' "$output" | grep -q "plain package name"
}

@test "package-add: embedded '..' --name is rejected" {
  run env PATH="$BIN:$PATH" "$BASH32" "$SCRIPTS/package-add.sh" \
    --name 'foo..bar' --lang ts
  [ "$status" -ne 0 ]
  printf '%s' "$output" | grep -q -- "'\.\.'"
}

@test "package-add: unknown --lang is rejected before creating the dir" {
  proj="$WORK/mono2"
  mkdir -p "$proj/packages"
  run env PATH="$BIN:$PATH" "$BASH32" "$SCRIPTS/package-add.sh" \
    --name web --lang cobol --dir packages
  [ "$status" -ne 0 ]
  printf '%s' "$output" | grep -q "must be one of: ts, rust, python, go"
  # The package directory must NOT have been created.
  [ ! -d "$proj/packages/web" ]
}

@test "package-add: --name with no value fails fast" {
  run env PATH="$BIN:$PATH" "$BASH32" "$SCRIPTS/package-add.sh" --name
  [ "$status" -ne 0 ]
  printf '%s' "$output" | grep -q -- "--name needs a value"
}

# ---------------------------------------------------------------------------
# 4. gitnr-present-but-FAILS fallback writes a valid .gitignore (per overlay).
# ---------------------------------------------------------------------------

# Helper: run a language overlay in a fresh dir with a failing gitnr, and assert
# the static fallback block landed and no gitnr error text leaked into the file.
assert_gitnr_fallback() {
  local script="$1" marker="$2" seed="$3"
  install_failing_gitnr
  local d="$WORK/gi-$RANDOM"
  mkdir -p "$d"
  # Seed .gitignore so the idempotency guard does not short-circuit, but does
  # not already contain the language marker.
  printf '%s\n' "$seed" > "$d/.gitignore"
  ( cd "$d" && env PATH="$BIN:$PATH" "$BASH32" "$SCRIPTS/$script" >/dev/null 2>&1 )
  # The static fallback marker is present...
  grep -q "$marker" "$d/.gitignore"
  # ...and the gitnr failure text never leaked into the file...
  ! grep -q "simulated template failure" "$d/.gitignore"
  # ...and no literal backslash-n artifact from a botched echo -e.
  ! grep -q '\\n' "$d/.gitignore"
}

@test "setup-go: failing gitnr falls back to a valid static .gitignore" {
  assert_gitnr_fallback "setup-go.sh" '/vendor/' '# seed'
}

@test "setup-rust: failing gitnr falls back to a valid static .gitignore" {
  install_failing_gitnr
  # Stub cargo: real `cargo init` would seed a .gitignore containing /target,
  # which trips the overlay's idempotency guard and skips the gitignore step
  # entirely. We want to exercise the fallback, so cargo must be a no-op.
  cat > "$BIN/cargo" <<'CARGO'
#!/bin/sh
exit 0
CARGO
  chmod +x "$BIN/cargo"
  d="$WORK/gi-rust"
  mkdir -p "$d"
  printf '# seed\n' > "$d/.gitignore"   # no /target marker yet
  ( cd "$d" && env PATH="$BIN:$PATH" "$BASH32" "$SCRIPTS/setup-rust.sh" >/dev/null 2>&1 )
  grep -qF '*.pdb' "$d/.gitignore"
  grep -qF 'target' "$d/.gitignore"
  ! grep -q "simulated template failure" "$d/.gitignore"
}

# python/ts overlays call uv/bun before the gitignore step, so exercise only the
# gitignore behavior by pre-creating the inputs those steps look for and letting
# the early steps no-op. We seed pyproject.toml / package.json so uv/bun are not
# invoked, but keep the language marker out of .gitignore.
@test "setup-python: failing gitnr falls back to a valid static .gitignore" {
  install_failing_gitnr
  # stub uv so `uv add --dev ...` and `uv init` never run real installs
  cat > "$BIN/uv" <<'UV'
#!/bin/sh
exit 0
UV
  chmod +x "$BIN/uv"
  d="$WORK/gi-py"
  mkdir -p "$d/src/gi_py"
  : > "$d/src/gi_py/__init__.py"
  printf 'ruff\n' > "$d/pyproject.toml"   # ruff marker present -> skip ruff append
  printf '# seed\n' > "$d/.gitignore"      # no __pycache__ marker yet
  ( cd "$d" && env PATH="$BIN:$PATH" "$BASH32" "$SCRIPTS/setup-python.sh" >/dev/null 2>&1 )
  grep -q '__pycache__' "$d/.gitignore"
  ! grep -q "simulated template failure" "$d/.gitignore"
}

@test "setup-ts: failing gitnr falls back to a valid static .gitignore" {
  install_failing_gitnr
  # stub bun so `bun init` / `bun install` / `bun add` never run real installs
  cat > "$BIN/bun" <<'BUN'
#!/bin/sh
exit 0
BUN
  chmod +x "$BIN/bun"
  d="$WORK/gi-ts"
  mkdir -p "$d"
  printf '{}\n' > "$d/package.json"        # skip package.json init
  printf '{}\n' > "$d/tsconfig.json"       # skip tsconfig add
  printf '# seed\n' > "$d/.gitignore"      # no node_modules marker yet
  ( cd "$d" && env PATH="$BIN:$PATH" "$BASH32" "$SCRIPTS/setup-ts.sh" --framework plain >/dev/null 2>&1 )
  grep -q 'node_modules' "$d/.gitignore"
  ! grep -q "simulated template failure" "$d/.gitignore"
}
