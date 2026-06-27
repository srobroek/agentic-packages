#!/usr/bin/env bash
#
# dep-audit: scan the project's lockfiles/manifests for known-vulnerable
# dependencies using each ecosystem's native scanner. Read-only: never
# modifies the project or attempts to fix anything.
#
# Portability floor: bash 3.2.57 + BSD sed/grep/awk (stock macOS).
#
# Detection is by lockfile/manifest presence. Each scanner is guarded with
# `command -v`; a missing scanner is reported (with an install hint), not an
# error. Exit status:
#   0  no HIGH/CRITICAL vulnerability found (or nothing to scan / scanners
#      absent -- see notes below)
#   1  at least one HIGH/CRITICAL vulnerability found
#
# Usage: audit.sh [project-dir]   (defaults to the current directory)

set -uo pipefail

# --- state -----------------------------------------------------------------

# Ecosystems detected by lockfile/manifest.
detected=0
# Scanners that actually executed.
ran=0
# Ecosystems detected but whose scanner was unavailable.
missing=0
# Count of HIGH/CRITICAL findings across all scanners that report it.
high_crit=0

# Parallel arrays of human-readable lines for the final summary. bash 3.2 has
# no associative arrays, so we keep simple indexed arrays and always guard
# their expansion (see emit_list) because `set -u` + empty array is a fatal
# error under bash 3.2.
ran_lines=()
missing_lines=()
finding_lines=()

note() { printf '%s\n' "$*"; }

# Append to an array without tripping `set -u` on bash 3.2.
add_ran()     { ran_lines[${#ran_lines[@]}]="$1"; }
add_missing() { missing_lines[${#missing_lines[@]}]="$1"; }
add_finding() { finding_lines[${#finding_lines[@]}]="$1"; }

# Print each argument as a bulleted line. Callers expand the array at the call
# site (e.g. emit_list "${arr[@]+"${arr[@]}"}") so this stays free of indirect
# expansion, which is unreliable for arrays on bash 3.2.
emit_list() {
  local el
  for el in "$@"; do
    printf -- '  - %s\n' "$el"
  done
}

# --- scanner dispatch ------------------------------------------------------

# Mark an ecosystem as detected and announce it.
detect() {
  detected=$((detected + 1))
  note "==> detected: $1"
}

# Record that a detected ecosystem has no available scanner.
unavailable() {
  # $1 = ecosystem label, $2 = scanner name, $3 = install hint
  missing=$((missing + 1))
  add_missing "$1: '$2' not installed -- $3"
  note "==> skip: $2 not installed ($1)"
}

# Run a scanner, capture its output, count HIGH/CRITICAL findings via a
# caller-supplied matcher, and record the result. Always returns 0 so a single
# scanner's exit code does not abort the whole run under pipefail.
run_scanner() {
  # $1 = label, $2 = severity-grep pattern (BSD grep -iE), rest = command
  local label="$1"
  local sev_pattern="$2"
  shift 2

  note "==> $label"
  note "+ $*"
  ran=$((ran + 1))
  add_ran "$label"

  local out
  out="$("$@" 2>&1)"
  # Echo the scanner output so the operator sees the detail.
  printf '%s\n' "$out"

  if [ -n "$sev_pattern" ]; then
    local n
    n="$(printf '%s\n' "$out" | grep -icE "$sev_pattern" 2>/dev/null || true)"
    # grep -c prints a number; default to 0 if empty.
    [ -n "$n" ] || n=0
    if [ "$n" -gt 0 ]; then
      high_crit=$((high_crit + n))
      add_finding "$label: $n line(s) matching HIGH/CRITICAL"
    fi
  fi
  return 0
}

# --- node / npm-pnpm-yarn --------------------------------------------------

scan_node() {
  if [ -f pnpm-lock.yaml ]; then
    detect "node (pnpm)"
    if command -v pnpm >/dev/null 2>&1; then
      run_scanner "pnpm audit" 'high|critical' pnpm audit
    else
      unavailable "node (pnpm)" pnpm "install pnpm (https://pnpm.io)"
    fi
    return 0
  fi

  if [ -f package-lock.json ] || [ -f npm-shrinkwrap.json ]; then
    detect "node (npm)"
    if command -v npm >/dev/null 2>&1; then
      run_scanner "npm audit" 'high|critical' npm audit
    else
      unavailable "node (npm)" npm "install Node.js (https://nodejs.org)"
    fi
    return 0
  fi

  if [ -f yarn.lock ]; then
    detect "node (yarn)"
    if command -v yarn >/dev/null 2>&1; then
      run_scanner "yarn npm audit" 'high|critical' yarn npm audit
    elif command -v npm >/dev/null 2>&1; then
      run_scanner "npm audit" 'high|critical' npm audit
    else
      unavailable "node (yarn)" yarn "install yarn (https://yarnpkg.com)"
    fi
    return 0
  fi

  # A bare package.json with no lockfile: npm audit needs a lockfile, so flag
  # it rather than pretend to scan.
  if [ -f package.json ]; then
    detect "node (package.json, no lockfile)"
    add_missing "node: no lockfile present -- run your installer first, then re-audit"
    missing=$((missing + 1))
    note "==> skip: node project has no lockfile to audit"
  fi
}

# --- python ----------------------------------------------------------------

scan_python() {
  if [ -f poetry.lock ] || [ -f uv.lock ] || [ -f Pipfile.lock ] ||
    [ -f requirements.txt ] || [ -f pyproject.toml ]; then
    detect "python"
    if command -v pip-audit >/dev/null 2>&1; then
      run_scanner "pip-audit" 'high|critical' pip-audit
    elif command -v uv >/dev/null 2>&1; then
      # uv ships pip-audit-style scanning via `uv pip` only with a plugin in
      # some versions; fall back to invoking pip-audit through uvx if present.
      if command -v uvx >/dev/null 2>&1; then
        run_scanner "uvx pip-audit" 'high|critical' uvx pip-audit
      else
        unavailable "python" pip-audit "pip install pip-audit (or: uvx pip-audit)"
      fi
    else
      unavailable "python" pip-audit "pip install pip-audit (or: uvx pip-audit)"
    fi
  fi
}

# --- rust ------------------------------------------------------------------

scan_rust() {
  if [ -f Cargo.lock ] || [ -f Cargo.toml ]; then
    detect "rust"
    if command -v cargo-audit >/dev/null 2>&1 ||
      { command -v cargo >/dev/null 2>&1 && cargo audit --version >/dev/null 2>&1; }; then
      run_scanner "cargo audit" 'high|critical' cargo audit
    else
      unavailable "rust" "cargo-audit" "cargo install cargo-audit"
    fi
  fi
}

# --- go --------------------------------------------------------------------

scan_go() {
  if [ -f go.mod ]; then
    detect "go"
    if command -v govulncheck >/dev/null 2>&1; then
      # govulncheck has no severity tiers; any reported vuln is treated as
      # gating. The matcher counts "Vulnerability #" headers.
      run_scanner "govulncheck" 'vulnerability #' govulncheck ./...
    else
      unavailable "go" govulncheck "go install golang.org/x/vuln/cmd/govulncheck@latest"
    fi
  fi
}

# --- cross-ecosystem fallback ----------------------------------------------

# osv-scanner understands many lockfile formats at once. Run it only when it is
# installed AND we either detected nothing native or want broad coverage. We
# run it as a supplement when present; its findings still gate.
scan_osv() {
  if command -v osv-scanner >/dev/null 2>&1; then
    # Only bother if there is something to scan.
    if [ "$detected" -gt 0 ] || ls ./*.lock >/dev/null 2>&1; then
      run_scanner "osv-scanner" 'high|critical' osv-scanner scan --recursive .
    fi
  elif [ "$detected" -eq 0 ]; then
    add_missing "cross-ecosystem: 'osv-scanner' not installed -- https://google.github.io/osv-scanner/"
  fi
}

# --- main ------------------------------------------------------------------

main() {
  local target="${1:-.}"
  if [ ! -d "$target" ]; then
    note "dep-audit: '$target' is not a directory" >&2
    return 2
  fi
  cd "$target" || return 2

  note "dep-audit: scanning ${target}"
  note ""

  scan_node
  scan_python
  scan_rust
  scan_go
  scan_osv

  note ""
  note "==> summary"
  note "ecosystems detected: ${detected}"
  note "scanners run:        ${ran}"
  note "scanners missing:    ${missing}"
  note "HIGH/CRITICAL hits:  ${high_crit}"

  if [ "$ran" -gt 0 ]; then
    note ""
    note "ran:"
    emit_list "${ran_lines[@]}"
  fi

  if [ "$missing" -gt 0 ]; then
    note ""
    note "unavailable / skipped:"
    emit_list "${missing_lines[@]}"
  fi

  if [ "$high_crit" -gt 0 ]; then
    note ""
    note "findings (HIGH/CRITICAL):"
    emit_list "${finding_lines[@]}"
  fi

  if [ "$detected" -eq 0 ]; then
    note ""
    note "No supported lockfile or manifest detected; nothing to audit." >&2
    return 0
  fi

  if [ "$ran" -eq 0 ]; then
    note ""
    note "Ecosystems were detected but no scanner was available; install one of the tools above and re-run." >&2
    return 0
  fi

  if [ "$high_crit" -gt 0 ]; then
    note ""
    note "FAIL: ${high_crit} HIGH/CRITICAL match(es) found." >&2
    return 1
  fi

  note ""
  note "OK: no HIGH/CRITICAL vulnerabilities found by the scanners that ran."
  return 0
}

main "$@"
