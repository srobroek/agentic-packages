#!/usr/bin/env bats
#
# Tests for the portability gate. Each test builds a tiny throwaway package tree
# under $BATS_TEST_TMPDIR containing a hook script with a known portability
# property (a bad fixture that must be flagged, or a clean fixture that must
# pass), then runs the gate over that tree and asserts the verdict.
#
# The gate itself must also PARSE and run under the bash 3.2 floor, so we invoke
# it via /bin/bash when that is 3.2.x (stock macOS) and fall back to PATH bash
# on Linux CI.
#
# Run: bats packages/hooks-portability-ci/tests/portability-check.bats

setup() {
  CHECK="${BATS_TEST_DIRNAME}/../.apm/skills/hooks-portability-ci/scripts/portability-check.sh"
  FLOOR_BASH="$(pick_bash)"
  # A fresh fake package tree per test: pkg/scripts/<hook>.sh
  TREE="$(mktemp -d "${BATS_TEST_TMPDIR}/tree.XXXXXX")"
  mkdir -p "$TREE/pkg/scripts"
  HOOK="$TREE/pkg/scripts/hook.sh"
}

pick_bash() {
  if [ -x /bin/bash ] && /bin/bash --version 2>/dev/null | head -1 | grep -q 'version 3\.2'; then
    printf '/bin/bash'
  else
    printf 'bash'
  fi
}

# Run the gate over the fake tree; populate $output / $status.
run_gate() {
  run "$FLOOR_BASH" "$CHECK" "$TREE"
}

# --- the gate parses under the floor it enforces ---------------------------

@test "portability-check.sh parses under the bash 3.2 floor" {
  run "$FLOOR_BASH" -n "$CHECK"
  [ "$status" -eq 0 ]
}

# --- clean fixture: a correct PreToolUse guard -----------------------------

@test "clean hook (bash 3.2 + BSD + string-safe jq) passes" {
  cat > "$HOOK" <<'EOF'
#!/usr/bin/env bash
set -uo pipefail
payload="$(cat)"
[ -z "$payload" ] && exit 0
command="$(
  printf '%s' "$payload" | jq -r '
    if (.tool_input|type)=="string" then .tool_input
    else (.tool_input.command // empty) end
  ' 2>/dev/null || true
)"
[ -z "$command" ] && exit 0
case "$command" in
  *"rm -rf /"*) printf 'deny\n'; exit 0 ;;
esac
exit 0
EOF
  run_gate
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '0 failing check'
}

# --- bad fixture: bash-4 mapfile (parses on 3.2, exit 127 at runtime) -------

@test "hook using mapfile is flagged (bash-4 builtin)" {
  cat > "$HOOK" <<'EOF'
#!/usr/bin/env bash
set -uo pipefail
mapfile -t lines < /etc/hosts
printf '%s\n' "${lines[@]}"
EOF
  run_gate
  [ "$status" -eq 1 ]
  echo "$output" | grep -q 'bash4-builtin'
}

# --- bad fixture: ;;& fallthrough (bash-4 parse error on 3.2) ---------------

@test "hook using ;;& fallthrough is flagged (bash 3.2 parse error)" {
  # Only meaningful when the floor bash is actually 3.2; on bash 4+ `;;&` parses
  # fine and there is nothing to catch. Skip rather than assert a false verdict.
  if ! "$FLOOR_BASH" --version 2>/dev/null | head -1 | grep -q 'version 3\.2'; then
    skip "floor bash is not 3.2; ;;& parses on this bash"
  fi
  cat > "$HOOK" <<'EOF'
#!/usr/bin/env bash
set -uo pipefail
x="$1"
case "$x" in
  a) echo a ;;&
  b) echo b ;;
esac
EOF
  run_gate
  [ "$status" -eq 1 ]
  echo "$output" | grep -q 'bash32-parse'
}

# --- bad fixture: GNU \b word boundary in sed ------------------------------

@test "hook using GNU \\b word boundary in sed is flagged" {
  cat > "$HOOK" <<'EOF'
#!/usr/bin/env bash
set -uo pipefail
echo "foo bar" | sed -E 's/\bbar\b/baz/'
EOF
  run_gate
  [ "$status" -eq 1 ]
  echo "$output" | grep -q 'gnu-sed-grep'
}

# --- bad fixture: lazy quantifier in grep ----------------------------------

@test "hook using GNU/PCRE lazy quantifier in grep is flagged" {
  cat > "$HOOK" <<'EOF'
#!/usr/bin/env bash
set -uo pipefail
echo "<a><b>" | grep -E '<.+?>'
EOF
  run_gate
  [ "$status" -eq 1 ]
  echo "$output" | grep -q 'gnu-sed-grep'
}

# --- bad fixture: string-form tool_input crashes jq ------------------------

@test "hook that indexes string tool_input is flagged (Cannot index string)" {
  cat > "$HOOK" <<'EOF'
#!/usr/bin/env bash
set -uo pipefail
payload="$(cat)"
# Naive: assumes tool_input is always an object. Crashes on a bare string.
command="$(printf '%s' "$payload" | jq -r '.tool_input.command')"
[ -z "$command" ] && exit 0
exit 0
EOF
  run_gate
  [ "$status" -eq 1 ]
  echo "$output" | grep -q 'string-payload'
}

# --- discovery / environment ------------------------------------------------

@test "empty tree (no hook scripts) -> exit 0" {
  rm -f "$HOOK"
  run_gate
  [ "$status" -eq 0 ]
  echo "$output" | grep -q 'no hook scripts found'
}

@test "missing directory -> exit 2 (usage error)" {
  run "$FLOOR_BASH" "$CHECK" "$TREE/does-not-exist"
  [ "$status" -eq 2 ]
}

@test "tests/ scripts are excluded from discovery" {
  mkdir -p "$TREE/pkg/tests"
  cat > "$TREE/pkg/tests/foo.bats" <<'EOF'
#!/usr/bin/env bats
EOF
  # Put a *.sh under tests/ that WOULD fail if scanned, to prove exclusion.
  cat > "$TREE/pkg/tests/helper.sh" <<'EOF'
#!/usr/bin/env bash
mapfile -t x < /dev/null
EOF
  rm -f "$HOOK"
  run_gate
  # No real hook scripts remain outside tests/, so the gate finds nothing.
  [ "$status" -eq 0 ]
  echo "$output" | grep -q 'no hook scripts found'
}

@test "a clean and a bad hook together -> exit 1 and only the bad one flagged" {
  # clean
  cat > "$HOOK" <<'EOF'
#!/usr/bin/env bash
set -uo pipefail
exit 0
EOF
  # bad (mapfile)
  cat > "$TREE/pkg/scripts/bad.sh" <<'EOF'
#!/usr/bin/env bash
mapfile -t x < /dev/null
EOF
  run_gate
  [ "$status" -eq 1 ]
  echo "$output" | grep -q 'bad.sh'
  ! echo "$output" | grep -E 'FAIL .*hook\.sh'
}
