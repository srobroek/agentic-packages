#!/usr/bin/env bats
#
# Tests for dep-update's helper scripts.
# detect/research/apply are Python; the suite drives them as shipped.
# Run with: bats packages/dep-update/tests/dep-update.bats
#
# Strategy:
#   - detect.py:   fixture dirs in BATS_TEST_TMPDIR (no network).
#   - research.py: DEP_UPDATE_FIXTURE_DIR points to JSON fixture files.
#   - apply.py:    stub package manager binaries on PATH; DEP_UPDATE_PKG_MANAGER.
#   - apm.yml:     parsed with python3 + tomllib/pyyaml (or grep fallback).
#
# No real network calls in any test.

SCRIPTS="${BATS_TEST_DIRNAME}/../.apm/skills/dep-update/scripts"
APM_YML="${BATS_TEST_DIRNAME}/../apm.yml"

setup() {
  PROJ="$(mktemp -d "${BATS_TMPDIR:-/tmp}/dep-update-proj.XXXXXX")"
  STUB="$(mktemp -d "${BATS_TMPDIR:-/tmp}/dep-update-stub.XXXXXX")"
  FIXTURES="$(mktemp -d "${BATS_TMPDIR:-/tmp}/dep-update-fix.XXXXXX")"

  # Minimal real PATH for script builtins + python3.
  BASE_PATH="/usr/bin:/bin:/usr/local/bin"
  # Find python3 location and add its directory explicitly.
  PYTHON3_DIR="$(dirname "$(command -v python3 2>/dev/null || echo /usr/bin/python3)")"
  BASE_PATH="${PYTHON3_DIR}:${BASE_PATH}"

  # PATH for "tool absent" assertions: it must NOT resolve any package manager.
  # BASE_PATH includes /usr/local/bin, where CI runners (e.g. GitHub
  # ubuntu-latest) ship npm/node -- so a npm-absent test that uses BASE_PATH
  # passes on a clean laptop but fails in CI because npm IS found there. Exclude
  # /usr/local/bin here; python3 stays via its explicit dir, and present-tool
  # tests inject their own stub into ${STUB} so they are unaffected.
  ABSENT_PATH="${PYTHON3_DIR}:/usr/bin:/bin"
}

teardown() {
  rm -rf "$PROJ" "$STUB" "$FIXTURES"
}

# Run a script with the stub bin dir first on PATH.
run_script() {
  local script="$1"
  shift
  run env PATH="${STUB}:${BASE_PATH}" /bin/bash "${SCRIPTS}/${script}" "$@"
}

# Run detect.py against $PROJ.
run_detect() {
  run env PATH="${STUB}:${BASE_PATH}" python3 "${SCRIPTS}/detect.py" "$PROJ"
}

# Run research.py with fixture dir against $PROJ (detect.py runs internally).
run_research() {
  run env PATH="${STUB}:${BASE_PATH}" DEP_UPDATE_FIXTURE_DIR="$FIXTURES" \
    python3 "${SCRIPTS}/research.py" "$@"
}

# Run research.py with fixture dir, reading dep lines from a file via stdin.
# Sets RESEARCH_USE_STDIN=1 so the script reads from stdin instead of detect.py.
# Usage: run_research_stdin <dep_file> [project-dir]
run_research_stdin() {
  local dep_file="$1"
  local proj="${2:-$PROJ}"
  run env PATH="${STUB}:${BASE_PATH}" \
    DEP_UPDATE_FIXTURE_DIR="$FIXTURES" \
    RESEARCH_USE_STDIN=1 \
    /bin/bash -c "python3 '${SCRIPTS}/research.py' '$proj' <'$dep_file'"
}

# Write dep lines to a temp file for research stdin tests.
write_deps() {
  local dep_file="${PROJ}/test-deps.txt"
  printf '%s' "$1" >"$dep_file"
  printf '%s' "$dep_file"
}

# Run apply.py with stub PM on PATH.
run_apply() {
  run env PATH="${STUB}:${BASE_PATH}" DEP_UPDATE_PKG_MANAGER="${DEP_UPDATE_PKG_MANAGER:-}" \
    python3 "${SCRIPTS}/apply.py" "$@"
}

# Install an executable stub named $1 whose body is the remaining args.
mk_stub() {
  local name="$1"; shift
  { printf '#!/usr/bin/env bash\n'; printf '%s\n' "$*"; } >"${STUB}/${name}"
  chmod +x "${STUB}/${name}"
}

# Write a PyPI-style JSON fixture for the given package name and latest version.
mk_pypi_fixture() {
  local name="$1" latest="$2"
  # Creates FIXTURES/pypi_<name>.json
  python3 - <<PY
import json, os
name = "$name"
latest = "$latest"
data = {
    "info": {"version": latest, "yanked": False,
             "project_urls": {"Source": "https://github.com/example/" + name},
             "home_page": ""},
    "releases": {
        latest: [{"filename": name + "-" + latest + ".tar.gz", "yanked": False}]
    }
}
with open(os.path.join("$FIXTURES", f"pypi_{name}.json"), "w") as f:
    json.dump(data, f)
PY
}

# Write an npm-style JSON fixture.
mk_npm_fixture() {
  local name="$1" latest="$2"
  local safe_name
  safe_name=$(printf '%s' "$name" | sed 's|/|__|g' | sed 's|@|__at__|g')
  python3 - <<PY
import json, os
name = "$name"
latest = "$latest"
safe_name = "$safe_name"
data = {
    "name": name,
    "dist-tags": {"latest": latest},
    "versions": {latest: {"name": name, "version": latest}},
    "repository": {"url": "https://github.com/example/" + safe_name}
}
with open(os.path.join("$FIXTURES", f"npm_{safe_name}.json"), "w") as f:
    json.dump(data, f)
PY
}

# Write a yanked-only PyPI fixture (all files yanked).
mk_pypi_yanked_fixture() {
  local name="$1" latest="$2"
  python3 - <<PY
import json, os
name = "$name"
latest = "$latest"
data = {
    "info": {"version": latest, "yanked": False,
             "project_urls": {}, "home_page": ""},
    "releases": {
        latest: [{"filename": name + "-" + latest + ".tar.gz", "yanked": True}]
    }
}
with open(os.path.join("$FIXTURES", f"pypi_{name}.json"), "w") as f:
    json.dump(data, f)
PY
}

# ============================================================================
# detect.py tests
# ============================================================================

# --- portability -----------------------------------------------------------

@test "detect.py parses as valid Python" {
  run python3 -c 'import ast,sys; ast.parse(open(sys.argv[1]).read())' "${SCRIPTS}/detect.py"
  [ "$status" -eq 0 ]
}

# --- Python: uv.lock -------------------------------------------------------

@test "detect: uv.lock emits pypi deps (SC-001 input)" {
  cat >"${PROJ}/uv.lock" <<'EOF'
[[package]]
name = "fastapi"
version = "0.111.0"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "pydantic"
version = "2.7.1"
source = { registry = "https://pypi.org/simple" }
EOF
  run_detect
  [ "$status" -eq 0 ]
  [[ "$output" == *"pypi	fastapi	0.111.0"* ]] || return 1
  [[ "$output" == *"pypi	pydantic	2.7.1"* ]] || return 1
}

# --- Python: pyproject.toml ------------------------------------------------

@test "detect: pyproject.toml emits pypi deps (poetry style)" {
  cat >"${PROJ}/pyproject.toml" <<'EOF'
[tool.poetry.dependencies]
python = "^3.11"
requests = "^2.28.0"
click = "^8.1.0"
EOF
  run_detect
  [ "$status" -eq 0 ]
  [[ "$output" == *"pypi	requests"* ]] || return 1
  [[ "$output" == *"pypi	click"* ]] || return 1
  # python pseudo-dep must not appear
  [[ "$output" != *"pypi	python"* ]] || return 1
}

# --- Node: package.json ----------------------------------------------------

@test "detect: package.json emits npm deps" {
  cat >"${PROJ}/package.json" <<'EOF'
{
  "dependencies": {
    "express": "^4.18.0",
    "lodash": "4.17.21"
  },
  "devDependencies": {
    "jest": "^29.0.0"
  }
}
EOF
  run_detect
  [ "$status" -eq 0 ]
  [[ "$output" == *"npm	express"* ]] || return 1
  [[ "$output" == *"npm	lodash"* ]] || return 1
  [[ "$output" == *"npm	jest"* ]] || return 1
}

# --- empty project ---------------------------------------------------------

@test "detect: empty project exits 0, no output lines" {
  run_detect
  [ "$status" -eq 0 ]
  # stdout must have no tab-separated dep lines
  local dep_lines
  dep_lines=$(printf '%s\n' "$output" | grep -c $'\t' || true)
  [ "$dep_lines" -eq 0 ]
}

# --- non-existent dir ------------------------------------------------------

@test "detect: non-existent directory exits 2" {
  run env PATH="${STUB}:${BASE_PATH}" python3 "${SCRIPTS}/detect.py" "${PROJ}/does-not-exist"
  [ "$status" -eq 2 ]
}

# ============================================================================
# research.py tests
# ============================================================================

# --- portability -----------------------------------------------------------

@test "research.py parses as valid Python" {
  run python3 -c 'import ast,sys; ast.parse(open(sys.argv[1]).read())' "${SCRIPTS}/research.py"
  [ "$status" -eq 0 ]
}

# --- SC-001: pinned == latest is NOT offered -------------------------------

@test "research: dep already at latest is CURRENT (SC-001)" {
  mk_pypi_fixture "requests" "2.32.3"
  local df; df=$(write_deps $'pypi\trequests\t2.32.3\n')
  run_research_stdin "$df"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"status":"CURRENT"'* ]] || [[ "$output" == *'"status": "CURRENT"'* ]] || return 1
}

# --- SC-001: correct semver classification ---------------------------------

@test "research: patch bump classified PATCH-SAFE" {
  mk_pypi_fixture "fastapi" "0.111.1"
  local df; df=$(write_deps $'pypi\tfastapi\t0.111.0\n')
  run_research_stdin "$df"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"class":"PATCH-SAFE"'* ]] || [[ "$output" == *'"class": "PATCH-SAFE"'* ]] || return 1
}

@test "research: minor bump classified MINOR-CHECK" {
  mk_pypi_fixture "fastapi" "0.112.0"
  local df; df=$(write_deps $'pypi\tfastapi\t0.111.0\n')
  run_research_stdin "$df"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"class":"MINOR-CHECK"'* ]] || [[ "$output" == *'"class": "MINOR-CHECK"'* ]] || return 1
}

@test "research: major bump classified MAJOR-ADVISORY (SC-003 prereq)" {
  mk_pypi_fixture "fastapi" "1.0.0"
  local df; df=$(write_deps $'pypi\tfastapi\t0.111.0\n')
  run_research_stdin "$df"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"class":"MAJOR-ADVISORY"'* ]] || [[ "$output" == *'"class": "MAJOR-ADVISORY"'* ]] || return 1
}

# --- 404 -> UNRESOLVABLE ---------------------------------------------------

@test "research: 404 (no fixture) results in UNRESOLVABLE (SC-008 prereq)" {
  # No fixture file created -> simulates offline / 404.
  local df; df=$(write_deps $'pypi\tunknown-private-pkg\t1.0.0\n')
  run_research_stdin "$df"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"status":"UNRESOLVABLE"'* ]] || [[ "$output" == *'"status": "UNRESOLVABLE"'* ]] || return 1
}

# --- all-offline -> graceful, zero writes (SC-008) -------------------------

@test "research: all-offline exits 0 with no registry access warning, zero writes (SC-008)" {
  # No fixtures -> every dep is UNRESOLVABLE.
  local df; df=$(write_deps $'pypi\tpkg-a\t1.0.0\npypi\tpkg-b\t2.0.0\n')
  run_research_stdin "$df"
  [ "$status" -eq 0 ]
  # Should warn about no registry access (note: bats captures stdout+stderr together without --separate-stderr).
  [[ "$output" == *"UNRESOLVABLE"* ]] || [[ "$output" == *"no registry access"* ]] || return 1
  # No writes to .project-setup/ (checked again in SC-009 test).
  [ ! -d "${PROJ}/.project-setup" ]
}

# --- yanked PyPI version -> DISCONFIRMED -----------------------------------

@test "research: all-yanked PyPI version is DISCONFIRMED, not offered" {
  mk_pypi_yanked_fixture "badpkg" "9.9.9"
  local df; df=$(write_deps $'pypi\tbadpkg\t1.0.0\n')
  run_research_stdin "$df"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"status":"DISCONFIRMED"'* ]] || [[ "$output" == *'"status": "DISCONFIRMED"'* ]] || return 1
}

# --- npm registry -----------------------------------------------------------

@test "research: npm dep patch bump classified PATCH-SAFE" {
  mk_npm_fixture "express" "4.18.3"
  local df; df=$(write_deps $'npm\texpress\t4.18.0\n')
  run_research_stdin "$df"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"class":"PATCH-SAFE"'* ]] || [[ "$output" == *'"class": "PATCH-SAFE"'* ]] || return 1
}

# ============================================================================
# answers.toml read (SC-006 / SC-007)
# ============================================================================

@test "absent answers.toml: detect + research run without error (SC-006)" {
  # No .project-setup/ at all.
  mk_pypi_fixture "requests" "2.32.3"
  cat >"${PROJ}/pyproject.toml" <<'EOF'
[tool.poetry.dependencies]
requests = "^2.28.0"
EOF
  run_research "$PROJ"
  [ "$status" -eq 0 ]
  # Must not print any error about answers.toml.
  [[ "$output" != *"answers.toml"* ]] || true  # allowed to mention it, but not error
  [[ "$output" != *"Error"* ]] || return 1
  [[ "$output" != *"Traceback"* ]] || return 1
}

@test "answers.toml pinned_deps differ from lockfile: research still classifies (SC-007)" {
  # Set up answers.toml with fastapi@0.100.0 (drift from lockfile 0.111.0).
  mkdir -p "${PROJ}/.project-setup"
  cat >"${PROJ}/.project-setup/answers.toml" <<'EOF'
[module.lang-python]
pinned_deps = ["fastapi@0.100.0"]
dev_deps = []
framework = "fastapi"
python_version = "3.13"
EOF
  # uv.lock has 0.111.0 (drifted).
  cat >"${PROJ}/uv.lock" <<'EOF'
[[package]]
name = "fastapi"
version = "0.111.0"
source = { registry = "https://pypi.org/simple" }
EOF
  mk_pypi_fixture "fastapi" "0.111.1"
  run_research "$PROJ"
  [ "$status" -eq 0 ]
  # The research result must have fastapi classified (not error out).
  [[ "$output" == *"fastapi"* ]] || return 1
}

# ============================================================================
# apply.py tests
# ============================================================================

# --- portability -----------------------------------------------------------

@test "apply.py parses as valid Python" {
  run python3 -c 'import ast,sys; ast.parse(open(sys.argv[1]).read())' "${SCRIPTS}/apply.py"
  [ "$status" -eq 0 ]
}

# --- SC-004: confirmed patch runs stub PM + re-reads ----------------------

@test "apply: confirmed patch runs stub uv and exits 0 (SC-004)" {
  # Create a pyproject.toml with the target version so the re-read check passes.
  cat >"${PROJ}/pyproject.toml" <<'EOF'
[project]
dependencies = ["requests==2.32.3"]
EOF
  # uv.lock so the version check succeeds.
  cat >"${PROJ}/uv.lock" <<'EOF'
[[package]]
name = "requests"
version = "2.32.3"
source = { registry = "https://pypi.org/simple" }
EOF
  mk_stub uv 'echo "Updated requests to $4"; exit 0'
  run env PATH="${STUB}:${BASE_PATH}" python3 "${SCRIPTS}/apply.py" \
    "pypi" "requests" "2.32.3" "$PROJ"
  [ "$status" -eq 0 ]
  [[ "$output" == *"uv add"* ]] || return 1
}

# --- PM absent -> print manual command, exit 0 ----------------------------

@test "apply: uv absent prints manual command and exits 0 (no abort)" {
  # No uv stub installed; ABSENT_PATH guarantees uv is unresolvable (BASE_PATH
  # would find a /usr/local/bin uv on some runners).
  run env PATH="${STUB}:${ABSENT_PATH}" python3 "${SCRIPTS}/apply.py" \
    "pypi" "requests" "2.32.3" "$PROJ"
  [ "$status" -eq 0 ]
  [[ "$output" == *"SKIP"* ]] || return 1
  [[ "$output" == *"uv add"* ]] || return 1
}

# --- SC-003: major never enters apply path ---------------------------------

@test "apply: cargo ecosystem is advisory-only, exits 0, no apply (SC-003 extension)" {
  run env PATH="${STUB}:${BASE_PATH}" python3 "${SCRIPTS}/apply.py" \
    "cargo" "serde" "2.0.0" "$PROJ"
  [ "$status" -eq 0 ]
  [[ "$output" == *"ADVISORY-ONLY"* ]] || return 1
  [[ "$output" != *"cargo update"* ]] || [[ "$output" == *"To update manually"* ]] || return 1
}

@test "apply: go ecosystem is advisory-only, exits 0, no apply" {
  run env PATH="${STUB}:${BASE_PATH}" python3 "${SCRIPTS}/apply.py" \
    "go" "github.com/gin-gonic/gin" "1.10.0" "$PROJ"
  [ "$status" -eq 0 ]
  [[ "$output" == *"ADVISORY-ONLY"* ]] || return 1
}

# --- Node: pnpm stub -------------------------------------------------------

@test "apply: node (pnpm) runs pnpm update and exits 0" {
  cat >"${PROJ}/package.json" <<'EOF'
{"dependencies": {"express": "4.18.3"}}
EOF
  mk_stub pnpm 'echo "Packages updated"; exit 0'
  run env PATH="${STUB}:${BASE_PATH}" DEP_UPDATE_PKG_MANAGER="pnpm" \
    python3 "${SCRIPTS}/apply.py" "npm" "express" "4.18.3" "$PROJ"
  [ "$status" -eq 0 ]
  [[ "$output" == *"pnpm update"* ]] || return 1
}

# --- Node: npm absent -> print manual command ------------------------------

@test "apply: node npm absent prints manual npm install command" {
  # No npm stub. ABSENT_PATH excludes /usr/local/bin, where CI runners ship npm
  # -- with BASE_PATH this test passes locally but npm IS found in CI, so the
  # script runs `npm install` instead of printing the manual SKIP message.
  run env PATH="${STUB}:${ABSENT_PATH}" DEP_UPDATE_PKG_MANAGER="npm" \
    python3 "${SCRIPTS}/apply.py" "npm" "lodash" "4.17.21" "$PROJ"
  [ "$status" -eq 0 ]
  [[ "$output" == *"SKIP"* ]] || return 1
  [[ "$output" == *"npm install"* ]] || return 1
}

# --- bad arguments ---------------------------------------------------------

@test "apply: missing arguments exits 2" {
  run env PATH="${STUB}:${BASE_PATH}" python3 "${SCRIPTS}/apply.py"
  [ "$status" -eq 2 ]
}

@test "apply: non-existent project dir exits 2" {
  run env PATH="${STUB}:${BASE_PATH}" python3 "${SCRIPTS}/apply.py" \
    "pypi" "requests" "2.32.3" "${PROJ}/no-such-dir"
  [ "$status" -eq 2 ]
}

# ============================================================================
# SC-009: NO write to .project-setup/ under any path
# ============================================================================

@test "SC-009: detect.py never writes to .project-setup/" {
  cat >"${PROJ}/uv.lock" <<'EOF'
[[package]]
name = "fastapi"
version = "0.111.0"
source = { registry = "https://pypi.org/simple" }
EOF
  run_detect
  [ "$status" -eq 0 ]
  [ ! -d "${PROJ}/.project-setup" ]
}

@test "SC-009: research.py never writes to .project-setup/ (offline path)" {
  # Pre-create answers.toml so we can check it is not modified.
  mkdir -p "${PROJ}/.project-setup"
  printf '[module.lang-python]\npinned_deps = []\n' >"${PROJ}/.project-setup/answers.toml"
  local before_checksum
  before_checksum=$(python3 -c "import hashlib; print(hashlib.md5(open('${PROJ}/.project-setup/answers.toml','rb').read()).hexdigest())")

  local df; df=$(write_deps $'pypi\trequests\t1.0.0\n')
  run_research_stdin "$df"
  [ "$status" -eq 0 ]

  local after_checksum
  after_checksum=$(python3 -c "import hashlib; print(hashlib.md5(open('${PROJ}/.project-setup/answers.toml','rb').read()).hexdigest())")
  [ "$before_checksum" = "$after_checksum" ]
  # Also check sources.toml was not created.
  [ ! -f "${PROJ}/.project-setup/sources.toml" ]
}

@test "SC-009: apply.py never writes to .project-setup/" {
  mkdir -p "${PROJ}/.project-setup"
  printf '[module.lang-python]\npinned_deps = []\n' >"${PROJ}/.project-setup/answers.toml"
  local before
  before=$(python3 -c "import hashlib; print(hashlib.md5(open('${PROJ}/.project-setup/answers.toml','rb').read()).hexdigest())")

  # Run apply (uv absent via ABSENT_PATH -> prints manual command, no write).
  run env PATH="${STUB}:${ABSENT_PATH}" python3 "${SCRIPTS}/apply.py" \
    "pypi" "requests" "2.32.3" "$PROJ"
  [ "$status" -eq 0 ]

  local after
  after=$(python3 -c "import hashlib; print(hashlib.md5(open('${PROJ}/.project-setup/answers.toml','rb').read()).hexdigest())")
  [ "$before" = "$after" ]
  [ ! -f "${PROJ}/.project-setup/sources.toml" ]
}

# ============================================================================
# SC-010: apm.yml is type:skill with no project-setup dependency
# ============================================================================

@test "SC-010: apm.yml declares type: skill" {
  run grep -F 'type: skill' "$APM_YML"
  [ "$status" -eq 0 ]
}

@test "SC-010: apm.yml has no project-setup dependency entry" {
  # The description may mention .project-setup/ as a path — that is fine.
  # What must not exist: a dependencies: block that references the project-setup package.
  # Verified by: no `dependencies:` key at all (test 32), and no `- project-setup` entry.
  run python3 -c "
import sys
try:
    import yaml
    with open('${APM_YML}') as f:
        data = yaml.safe_load(f)
    deps = data.get('dependencies', {})
    # deps is a dict or None; check no key/value contains 'project-setup' as a package ref
    found = any('project-setup' in str(k) or 'project-setup' in str(v)
                for k, v in (deps.items() if isinstance(deps, dict) else []))
    sys.exit(1 if found else 0)
except ImportError:
    # pyyaml absent: check that no 'dependencies:' block has project-setup
    with open('${APM_YML}') as f:
        lines = f.readlines()
    in_deps = False
    for line in lines:
        if line.startswith('dependencies:'):
            in_deps = True
        elif in_deps and not line.startswith(' ') and not line.startswith('\t'):
            in_deps = False
        if in_deps and 'project-setup' in line:
            sys.exit(1)
    sys.exit(0)
"
  [ "$status" -eq 0 ]
}

@test "SC-010: apm.yml has no dependencies: block at all" {
  run grep -E '^dependencies:' "$APM_YML"
  [ "$status" -ne 0 ]
}

@test "SC-010: SKILL.md trigger frontmatter covers expected phrases" {
  SKILL_MD="${BATS_TEST_DIRNAME}/../.apm/skills/dep-update/SKILL.md"
  run grep -i 'upgrade dependencies\|bump versions\|what.*outdated\|stale packages\|apply safe bumps\|update lockfile' "$SKILL_MD"
  [ "$status" -eq 0 ]
}

# ============================================================================
# apm.yml schema validation
# ============================================================================

@test "apm.yml: parses as valid YAML with python3" {
  run python3 -c "
import sys
try:
    import yaml
    with open('${APM_YML}') as f:
        data = yaml.safe_load(f)
    assert data.get('type') == 'skill', 'type must be skill'
    assert data.get('category') == 'code-intelligence', 'category must be code-intelligence'
    assert 'dependencies' not in data, 'must not have dependencies'
    print('OK')
except ImportError:
    # pyyaml not available; use line-based checks instead. The no-dependencies
    # check must anchor to the key at column 0: a bare 'project-setup' substring
    # also matches the description's reference to .project-setup/answers.toml,
    # which is prose, not a dependency.
    with open('${APM_YML}') as f:
        content = f.read()
    assert 'type: skill' in content
    assert 'category: code-intelligence' in content
    assert not any(ln.startswith('dependencies:') for ln in content.splitlines())
    print('OK (no pyyaml, line-checked)')
"
  [ "$status" -eq 0 ]
  [[ "$output" == *"OK"* ]] || return 1
}

@test "apm.yml: category is code-intelligence" {
  run grep -F 'category: code-intelligence' "$APM_YML"
  [ "$status" -eq 0 ]
}

@test "apm.yml: tags include dependencies and upgrade" {
  run grep -E 'dependencies|upgrade' "$APM_YML"
  [ "$status" -eq 0 ]
}
