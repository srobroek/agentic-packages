#!/usr/bin/env bats

INSTALLER_SOURCE="${BATS_TEST_DIRNAME}/../.apm/skills/speckit-setup/scripts/install-speckit-formulas.sh"
FORMULA_SOURCE="${BATS_TEST_DIRNAME}/../formulas"
SPECKIT_MANIFEST="${BATS_TEST_DIRNAME}/../apm.yml"
BEADS_MANIFEST="${BATS_TEST_DIRNAME}/../../speckit-beads/apm.yml"

setup() {
  TEST_ROOT="$(mktemp -d "${BATS_TMPDIR:-/tmp}/speckit-formula-layout.XXXXXX")"
  TEST_HOME="$TEST_ROOT/home"
  TEST_PROJECT="$TEST_ROOT/project"
  TEST_BIN="$TEST_ROOT/bin"
  INSTALLER_DIR="$TEST_ROOT/plugin/.apm/skills/speckit-setup/scripts"
  mkdir -p "$TEST_HOME" "$TEST_PROJECT" "$TEST_BIN" "$INSTALLER_DIR"
  cp "$INSTALLER_SOURCE" "$INSTALLER_DIR/install-speckit-formulas.sh"
  INSTALLER="$INSTALLER_DIR/install-speckit-formulas.sh"
  {
    printf '#!/usr/bin/env bash\n'
    printf 'exit 0\n'
  } > "$TEST_BIN/bd"
  chmod +x "$TEST_BIN/bd"
}

teardown() {
  rm -rf "$TEST_ROOT"
}

install_fixture() {
  local destination="$1"
  mkdir -p "$destination"
  cp "$FORMULA_SOURCE"/*.toml "$destination/"
}

assert_source() {
  local expected="$1"
  run env HOME="$TEST_HOME" bash "$INSTALLER" --print-source
  [ "$status" -eq 0 ]
  [ "$output" = "$expected" ]
}

@test "discovers formulas from the APM-managed module" {
  formula_dir="$TEST_HOME/.apm/apm_modules/srobroek/agentic-packages/packages/speckit/formulas"
  install_fixture "$formula_dir"
  assert_source "$formula_dir"

  run bash -c 'cd "$1" && HOME="$2" PATH="$3:$PATH" bash "$4"' \
    _ "$TEST_PROJECT" "$TEST_HOME" "$TEST_BIN" "$INSTALLER"
  [ "$status" -eq 0 ]
  for formula in "$FORMULA_SOURCE"/*.toml; do
    cmp "$formula" "$TEST_PROJECT/.beads/formulas/${formula##*/}"
  done
}

@test "discovers formulas from the native Claude plugin cache" {
  formula_dir="$TEST_HOME/.claude/plugins/cache/agentic-packages/speckit/6.0.0/formulas"
  install_fixture "$formula_dir"
  assert_source "$formula_dir"
}

@test "discovers formulas from the native Codex plugin cache" {
  formula_dir="$TEST_HOME/.codex/plugins/cache/agentic-packages/speckit/6.0.0/formulas"
  install_fixture "$formula_dir"
  assert_source "$formula_dir"
}

@test "does not discover a user-global Beads formula" {
  install_fixture "$TEST_HOME/.beads/formulas"
  run env HOME="$TEST_HOME" bash "$INSTALLER" --print-source
  [ "$status" -ne 0 ]
}

@test "speckit owns formulas and speckit-beads depends one-way on speckit" {
  run grep -F 'srobroek/agentic-packages/packages/speckit-beads#' "$SPECKIT_MANIFEST"
  [ "$status" -ne 0 ]
  run grep -F 'srobroek/agentic-packages/packages/speckit#>=8.1.0 <9.0.0' "$BEADS_MANIFEST"
  [ "$status" -eq 0 ]
}
