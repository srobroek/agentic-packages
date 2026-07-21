#!/usr/bin/env bats

FORMULA_SOURCE="${BATS_TEST_DIRNAME}/../../speckit/formulas"
INSTALLER="${BATS_TEST_DIRNAME}/../../speckit/.apm/skills/speckit-setup/scripts/install-speckit-formulas.sh"

setup_file() {
  command -v bd >/dev/null || skip "bd is required"
  command -v jq >/dev/null || skip "jq is required"
  export BEADS_TEST_MODE=1
  TEST_REPO="$BATS_FILE_TMPDIR/repo"
  mkdir -p "$TEST_REPO"
  git -C "$TEST_REPO" init -q
  (cd "$TEST_REPO" && BD_NON_INTERACTIVE=1 bd init --skip-hooks --skip-agents --prefix sf >/dev/null)
  mkdir -p "$TEST_REPO/.beads/formulas"
  cp "$FORMULA_SOURCE"/*.toml "$TEST_REPO/.beads/formulas/"
}

setup() {
  export BEADS_TEST_MODE=1
  TEST_REPO="$BATS_FILE_TMPDIR/repo"
}

teardown_file() {
  [ -n "${BATS_FILE_TMPDIR:-}" ] && rm -rf "$BATS_FILE_TMPDIR/repo"
}

@test "all SpecKit formulas resolve from the project" {
  for formula in speckit-feature mol-speckit-fix-findings mol-speckit-iterate; do
    run bd -C "$TEST_REPO" formula show "$formula" --json
    [ "$status" -eq 0 ]
    echo "$output" | jq -e --arg root "$TEST_REPO" '.source | startswith($root + "/.beads/formulas/")' >/dev/null
  done
}

@test "feature formula expands to the gated lifecycle" {
  run bd -C "$TEST_REPO" mol pour speckit-feature --var feature=000-formula-test --dry-run
  [ "$status" -eq 0 ]
  [[ "$output" == *"would pour 34 issues"* ]]
  [[ "$output" == *"pre-implementation checkpoint"* ]]
  [[ "$output" == *"implementation child completion"* ]]
  [[ "$output" == *"closeout approval"* ]]
}

@test "remediation formulas compose with a sequential bond" {
  run bd -C "$TEST_REPO" mol bond \
    mol-speckit-fix-findings mol-speckit-iterate \
    --type sequential --dry-run \
    --var feature=001-bond-test --var source=review --var change=scope-adjustment
  [ "$status" -eq 0 ]
  [[ "$output" == *"formula → will cook as proto"* ]]
  [[ "$output" == *"Bond type: sequential"* ]]
  [[ "$output" == *"Result: compound proto"* ]]
}

@test "setup never sources formulas from the user-global directory" {
  run grep -F "\$HOME/.beads/formulas" "$INSTALLER"
  [ "$status" -ne 0 ]
  run grep -F "mktemp \"\$FORMULA_DEST.tmp.XXXXXX\"" "$INSTALLER"
  [ "$status" -eq 0 ]
}
