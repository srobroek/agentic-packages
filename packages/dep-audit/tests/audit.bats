#!/usr/bin/env bats
#
# Tests for dep-audit's scripts/audit.sh.
# Portability floor: bash 3.2.57 + BSD sed/grep/awk (stock macOS).
# Run with: bats packages/dep-audit/tests/audit.bats
#
# The scanners are external and may or may not be installed on the host, so
# every test runs the script with a controlled PATH: a per-test stub bin dir
# plus the minimal system bins (/usr/bin:/bin) that the script's own builtins
# need. This makes "scanner present" and "scanner absent" deterministic and
# keeps any real osv-scanner / cargo-audit on the developer's machine out of
# the results.

setup() {
  SCRIPT="${BATS_TEST_DIRNAME}/../scripts/audit.sh"

  PROJ="$(mktemp -d "${BATS_TMPDIR:-/tmp}/dep-audit-proj.XXXXXX")"
  STUB="$(mktemp -d "${BATS_TMPDIR:-/tmp}/dep-audit-stub.XXXXXX")"

  # Minimal real PATH for the script's process substitutions and `command -v`.
  BASE_PATH="/usr/bin:/bin"
}

teardown() {
  rm -rf "$PROJ" "$STUB"
}

# Run audit.sh against $PROJ with PATH = stub dir first, then minimal system.
run_audit() {
  run env PATH="${STUB}:${BASE_PATH}" /bin/bash "$SCRIPT" "$PROJ"
}

# Install an executable stub named $1 whose body is the remaining args, run via
# bash. Example: mk_stub npm 'echo "found 0 vulnerabilities"; exit 0'
mk_stub() {
  local name="$1"
  shift
  {
    printf '%s\n' '#!/usr/bin/env bash'
    printf '%s\n' "$*"
  } >"${STUB}/${name}"
  chmod +x "${STUB}/${name}"
}

# --- parse / portability floor --------------------------------------------

@test "audit.sh parses under /bin/bash (bash 3.2)" {
  run /bin/bash -n "$SCRIPT"
  [ "$status" -eq 0 ]
}

# --- nothing to scan -------------------------------------------------------

@test "empty project with no scanners: clean message, exit 0" {
  run_audit
  [ "$status" -eq 0 ]
  [[ "$output" == *"nothing to audit"* ]]
}

# --- node detection --------------------------------------------------------

@test "package-lock.json present: detects node and invokes npm audit" {
  : >"${PROJ}/package-lock.json"
  mk_stub npm 'echo "found 0 vulnerabilities"; exit 0'
  run_audit
  [ "$status" -eq 0 ]
  [[ "$output" == *"detected: node (npm)"* ]]
  [[ "$output" == *"npm audit"* ]]
  [[ "$output" == *"no HIGH/CRITICAL"* ]]
}

@test "npm audit reports a high vuln: gates with exit 1" {
  : >"${PROJ}/package-lock.json"
  mk_stub npm 'echo "found 2 vulnerabilities (2 high)"; echo "  High  Prototype Pollution"; exit 1'
  run_audit
  [ "$status" -eq 1 ]
  [[ "$output" == *"FAIL"* ]]
  [[ "$output" == *"HIGH/CRITICAL"* ]]
}

@test "node detected but npm absent: reports unavailable, exit 0" {
  : >"${PROJ}/package-lock.json"
  # No npm stub installed.
  run_audit
  [ "$status" -eq 0 ]
  [[ "$output" == *"detected: node (npm)"* ]]
  [[ "$output" == *"not installed"* ]]
  [[ "$output" == *"no scanner was available"* ]]
}

@test "pnpm-lock.yaml takes precedence and uses pnpm audit" {
  : >"${PROJ}/pnpm-lock.yaml"
  : >"${PROJ}/package-lock.json"
  mk_stub pnpm 'echo "No known vulnerabilities found"; exit 0'
  run_audit
  [ "$status" -eq 0 ]
  [[ "$output" == *"detected: node (pnpm)"* ]]
  [[ "$output" == *"pnpm audit"* ]]
  # npm must NOT have been chosen.
  [[ "$output" != *"detected: node (npm)"* ]]
}

@test "bare package.json with no lockfile: flagged, not scanned" {
  : >"${PROJ}/package.json"
  run_audit
  [ "$status" -eq 0 ]
  [[ "$output" == *"no lockfile"* ]]
}

# --- python ----------------------------------------------------------------

@test "requirements.txt present: runs pip-audit when available" {
  : >"${PROJ}/requirements.txt"
  mk_stub pip-audit 'echo "No known vulnerabilities found"; exit 0'
  run_audit
  [ "$status" -eq 0 ]
  [[ "$output" == *"detected: python"* ]]
  [[ "$output" == *"pip-audit"* ]]
}

@test "python detected but pip-audit absent: reports install hint" {
  : >"${PROJ}/pyproject.toml"
  run_audit
  [ "$status" -eq 0 ]
  [[ "$output" == *"detected: python"* ]]
  [[ "$output" == *"pip install pip-audit"* ]]
}

# --- rust ------------------------------------------------------------------

@test "Cargo.lock present but cargo-audit absent: reports install hint" {
  : >"${PROJ}/Cargo.lock"
  run_audit
  [ "$status" -eq 0 ]
  [[ "$output" == *"detected: rust"* ]]
  [[ "$output" == *"cargo install cargo-audit"* ]]
}

# --- go --------------------------------------------------------------------

@test "go.mod present: runs govulncheck when available" {
  : >"${PROJ}/go.mod"
  mk_stub govulncheck 'echo "No vulnerabilities found."; exit 0'
  run_audit
  [ "$status" -eq 0 ]
  [[ "$output" == *"detected: go"* ]]
  [[ "$output" == *"govulncheck"* ]]
}

@test "govulncheck reporting a vulnerability gates with exit 1" {
  : >"${PROJ}/go.mod"
  mk_stub govulncheck 'echo "Vulnerability #1: GO-2024-0001"; exit 3'
  run_audit
  [ "$status" -eq 1 ]
  [[ "$output" == *"FAIL"* ]]
}

# --- bad input -------------------------------------------------------------

@test "non-existent target directory: exit 2" {
  run env PATH="${STUB}:${BASE_PATH}" /bin/bash "$SCRIPT" "${PROJ}/does-not-exist"
  [ "$status" -eq 2 ]
}
