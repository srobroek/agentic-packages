#!/usr/bin/env bash
#
# dep-update/apply.sh: apply a single confirmed dependency bump by running
# the ecosystem's package manager.
#
# Portability floor: bash 3.2.57 + BSD sed/grep/awk (stock macOS).
#
# Usage:
#   apply.sh <ecosystem> <name> <new_version> [project-dir]
#
# ecosystem: pypi | npm | cargo | go
#   (cargo and go are advisory-only; this script will print the manual command
#    and exit 0 without applying anything.)
#
# Package manager selection for node:
#   - Reads from env var DEP_UPDATE_PKG_MANAGER if set (useful for tests).
#   - Otherwise reads from .project-setup/answers.toml [module.lang-ts]
#     package_manager key if tomllib / python3 are available.
#   - Otherwise detects from lockfile presence:
#       pnpm-lock.yaml  -> pnpm
#       bun.lock / bun.lockb -> bun
#       yarn.lock       -> yarn
#       (default)       -> npm
#
# After apply, re-reads the manifest to confirm the version landed.
# If the package manager is absent, prints the manual command and exits 0.
#
# NEVER writes .project-setup/ files.
#
# Exit status:
#   0  applied (or printed manual command when PM absent), or advisory-only
#   1  apply attempted but post-apply manifest check failed (version mismatch)
#   2  bad arguments

set -uo pipefail

note()  { printf '%s\n' "$*"; }
warn()  { printf 'WARN: %s\n' "$*" >&2; }
error() { printf 'ERROR: %s\n' "$*" >&2; }

# --- argument parsing -------------------------------------------------------

if [ $# -lt 3 ]; then
  error "apply.sh: usage: apply.sh <ecosystem> <name> <new_version> [project-dir]"
  exit 2
fi

ECOSYSTEM="$1"
DEP_NAME="$2"
NEW_VERSION="$3"
TARGET="${4:-.}"

if [ ! -d "$TARGET" ]; then
  error "apply.sh: '$TARGET' is not a directory"
  exit 2
fi

# Safety guard: NEVER touch .project-setup/.
# (Belt-and-suspenders; the skill logic should never pass project-setup paths.)
case "$DEP_NAME" in
  .project-setup*|*answers.toml*|*sources.toml*)
    error "apply.sh: refusing to touch project-setup files"
    exit 2 ;;
esac

cd "$TARGET" || exit 2

# --- node package manager detection ----------------------------------------

detect_node_pm() {
  # Explicit override for tests.
  if [ -n "${DEP_UPDATE_PKG_MANAGER:-}" ]; then
    printf '%s' "$DEP_UPDATE_PKG_MANAGER"
    return
  fi
  # Read from answers.toml if present and python3 available.
  if [ -f .project-setup/answers.toml ] && command -v python3 >/dev/null 2>&1; then
    local pm
    pm=$(python3 - <<'PY' 2>/dev/null
import sys
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        sys.exit(0)
with open(".project-setup/answers.toml", "rb") as fh:
    data = tomllib.load(fh)
pm = (data.get("module", {}).get("lang-ts", {}).get("package_manager") or
      data.get("module", {}).get("lang-ts", {}).get("package_manager_pin", ""))
if pm:
    print(pm.split("@")[0].strip())
PY
    )
    if [ -n "$pm" ]; then
      printf '%s' "$pm"
      return
    fi
  fi
  # Lockfile detection.
  if [ -f pnpm-lock.yaml ];  then printf 'pnpm'; return; fi
  if [ -f bun.lock ] || [ -f bun.lockb ]; then printf 'bun'; return; fi
  if [ -f yarn.lock ];       then printf 'yarn'; return; fi
  printf 'npm'
}

# --- post-apply version check -----------------------------------------------

# Check that the manifest now reflects the new version.
# Returns 0 if confirmed, 1 if mismatch.
check_python_version() {
  local name="$1" ver="$2"
  # Check pyproject.toml for "name = "ver"" or "name==ver" style.
  if [ -f pyproject.toml ]; then
    # uv / pip-style pinned dependencies: "name==ver" in the deps list.
    if grep -qiE "\"${name}==${ver}\"" pyproject.toml 2>/dev/null; then
      return 0
    fi
    # Also check requirements.txt style.
  fi
  if [ -f requirements.txt ]; then
    if grep -qiE "^${name}==${ver}" requirements.txt 2>/dev/null; then
      return 0
    fi
  fi
  # uv.lock: check for version = "ver" after name = "name"
  if [ -f uv.lock ]; then
    _CHK_NAME="$name" _CHK_VER="$ver" python3 - <<'PY' 2>/dev/null
import os, sys
name = os.environ["_CHK_NAME"]
ver  = os.environ["_CHK_VER"]
in_pkg = False
found_name = False
with open("uv.lock") as f:
    for line in f:
        line = line.rstrip()
        if line == "[[package]]":
            in_pkg = True
            found_name = False
        elif in_pkg and line.startswith("name = "):
            pkg_name = line.split('"')[1]
            found_name = (pkg_name.lower() == name.lower())
        elif in_pkg and found_name and line.startswith("version = "):
            pkg_ver = line.split('"')[1]
            if pkg_ver == ver:
                sys.exit(0)
            else:
                sys.exit(1)
sys.exit(1)
PY
    return $?
  fi
  # Fallback: assume mismatch (conservative).
  return 1
}

check_node_version() {
  local name="$1" ver="$2"
  if [ -f package.json ] && command -v python3 >/dev/null 2>&1; then
    _CHK_NAME="$name" _CHK_VER="$ver" python3 - <<'PY' 2>/dev/null
import json, os, sys
name = os.environ["_CHK_NAME"]
ver  = os.environ["_CHK_VER"]
try:
    with open("package.json") as f:
        data = json.load(f)
    for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        v = data.get(section, {}).get(name, "")
        if v and (v == ver or v == f"^{ver}" or v == f"~{ver}" or ver in v):
            sys.exit(0)
    sys.exit(1)
except Exception:
    sys.exit(1)
PY
    return $?
  fi
  return 1
}

# --- apply ------------------------------------------------------------------

apply_python() {
  local name="$1" ver="$2"
  if command -v uv >/dev/null 2>&1; then
    note "==> uv add \"${name}==${ver}\""
    uv add "${name}==${ver}"
    # Post-apply check.
    if check_python_version "$name" "$ver"; then
      note "OK: ${name} confirmed at ${ver}"
    else
      warn "${name}: post-apply manifest check failed — version may not have landed"
      return 1
    fi
  else
    note "SKIP: uv not found. To apply manually:"
    note "  uv add \"${name}==${ver}\""
    note "  (or: pip install \"${name}==${ver}\" and update your requirements file)"
  fi
}

apply_node() {
  local name="$1" ver="$2"
  local pm
  pm=$(detect_node_pm)
  case "$pm" in
    pnpm)
      if command -v pnpm >/dev/null 2>&1; then
        note "==> pnpm update ${name} --version ${ver}"
        pnpm update "${name}" --version "${ver}"
      else
        note "SKIP: pnpm not found. To apply manually:"
        note "  pnpm update ${name} --version ${ver}"
        return 0
      fi ;;
    bun)
      if command -v bun >/dev/null 2>&1; then
        note "==> bun add \"${name}@${ver}\""
        bun add "${name}@${ver}"
      else
        note "SKIP: bun not found. To apply manually:"
        note "  bun add \"${name}@${ver}\""
        return 0
      fi ;;
    yarn)
      if command -v yarn >/dev/null 2>&1; then
        note "==> yarn add \"${name}@${ver}\""
        yarn add "${name}@${ver}"
      else
        note "SKIP: yarn not found. To apply manually:"
        note "  yarn add \"${name}@${ver}\""
        return 0
      fi ;;
    *)
      if command -v npm >/dev/null 2>&1; then
        note "==> npm install \"${name}@${ver}\""
        npm install "${name}@${ver}"
      else
        note "SKIP: npm not found. To apply manually:"
        note "  npm install \"${name}@${ver}\""
        return 0
      fi ;;
  esac
  # Post-apply check.
  if check_node_version "$name" "$ver"; then
    note "OK: ${name} confirmed at ${ver}"
  else
    warn "${name}: post-apply manifest check failed — version may not have landed"
    return 1
  fi
}

# --- main ------------------------------------------------------------------

main() {
  note "dep-update/apply: ${ECOSYSTEM} ${DEP_NAME} -> ${NEW_VERSION}"

  case "$ECOSYSTEM" in
    pypi|python)
      apply_python "$DEP_NAME" "$NEW_VERSION" ;;
    npm|node|pnpm|yarn|bun)
      apply_node "$DEP_NAME" "$NEW_VERSION" ;;
    cargo|rust)
      note "ADVISORY-ONLY: Rust deps are advisory-only in this version."
      note "To update manually: cargo update -p ${DEP_NAME} --precise ${NEW_VERSION}"
      ;;
    go)
      note "ADVISORY-ONLY: Go deps are advisory-only in this version."
      note "To update manually: go get ${DEP_NAME}@${NEW_VERSION} && go mod tidy"
      ;;
    *)
      warn "apply.sh: unknown ecosystem '${ECOSYSTEM}'"
      note "Cannot apply automatically. Check the registry for ${DEP_NAME}@${NEW_VERSION}."
      ;;
  esac
}

main
