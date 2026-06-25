#!/usr/bin/env bats
#
# Tests for squash-merge-guard.sh — the PreToolUse hook that requires an
# explicit merge strategy on `gh pr merge`.
#
# Portability floor: bash 3.2.57 + BSD sed/grep (stock macOS). These tests use
# only core bats (run / status / output) — no bats-support / bats-assert.
#
# Danger strings (`gh pr merge`, ...) are NEVER placed on a bare command line:
# every payload is assembled via jq so a live PreToolUse hook in the session
# cannot intercept the literal.

setup() {
  GUARD="${BATS_TEST_DIRNAME}/../scripts/squash-merge-guard.sh"
  [ -f "$GUARD" ] || {
    echo "guard script not found at $GUARD" >&2
    return 1
  }
  if ! command -v jq >/dev/null 2>&1; then
    skip "jq not available"
  fi
}

# obj_payload <command-string> — JSON event with an OBJECT tool_input.
obj_payload() {
  jq -cn --arg c "$1" '{tool_input:{command:$c}}'
}

# str_payload <command-string> — JSON event with a STRING tool_input.
str_payload() {
  jq -cn --arg c "$1" '{tool_input:$c}'
}

# decision_of <json-payload> — run the guard, echo the permissionDecision, or
# the literal "allow" when the guard emits nothing.
decision_of() {
  local out
  out="$(printf '%s' "$1" | /usr/bin/env bash "$GUARD" 2>/dev/null || true)"
  if [ -z "$out" ]; then
    printf 'allow'
    return 0
  fi
  printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecision // "allow"'
}

# assert_decision <expected> <json-payload>
assert_decision() {
  local expected="$1" payload="$2" got
  got="$(decision_of "$payload")"
  if [ "$got" != "$expected" ]; then
    echo "expected=$expected got=$got payload=$payload" >&2
    return 1
  fi
}

# ---------------------------------------------------------------------------
# ALLOW — an explicit strategy is present, or it is a help lookup.
# ---------------------------------------------------------------------------

@test "allow: short strategy flag -s" {
  assert_decision allow "$(obj_payload 'gh pr merge 123 -s')"
}

@test "allow: short strategy flag -m" {
  assert_decision allow "$(obj_payload 'gh pr merge 123 -m')"
}

@test "allow: short strategy flag -r" {
  assert_decision allow "$(obj_payload 'gh pr merge 123 -r')"
}

@test "allow: long strategy --squash" {
  assert_decision allow "$(obj_payload 'gh pr merge 123 --squash')"
}

@test "allow: long strategy --merge" {
  assert_decision allow "$(obj_payload 'gh pr merge 123 --merge')"
}

@test "allow: long strategy --rebase" {
  assert_decision allow "$(obj_payload 'gh pr merge 123 --rebase')"
}

@test "allow: --help lookup is not a merge" {
  assert_decision allow "$(obj_payload 'gh pr merge --help')"
}

@test "allow: -h lookup is not a merge" {
  assert_decision allow "$(obj_payload 'gh pr merge -h')"
}

@test "allow: strategy via STRING tool_input" {
  assert_decision allow "$(str_payload 'gh pr merge 123 --squash')"
}

@test "allow: non-merge gh command is untouched" {
  assert_decision allow "$(obj_payload 'gh pr view 123')"
}

# ---------------------------------------------------------------------------
# DENY (block) — a real `gh pr merge` with NO genuine strategy provided.
# ---------------------------------------------------------------------------

@test "deny: no strategy at all" {
  assert_decision deny "$(obj_payload 'gh pr merge 123')"
}

@test "deny: --mergetool must NOT be treated as the 'merge' strategy" {
  assert_decision deny "$(obj_payload 'gh pr merge 123 --mergetool')"
}

@test "deny: --squash only inside a -t subject value (not a real strategy)" {
  assert_decision deny "$(obj_payload 'gh pr merge 123 -t "use --squash"')"
}

@test "deny: --merge only inside a --body value (not a real strategy)" {
  assert_decision deny "$(obj_payload 'gh pr merge 123 --body "we will --merge later"')"
}

@test "deny: --squash only inside an inline --title= value" {
  assert_decision deny "$(obj_payload 'gh pr merge 123 --title=use-the---squash-flag')"
}

@test "deny: STRING tool_input with no strategy" {
  assert_decision deny "$(str_payload 'gh pr merge 123')"
}

# ---------------------------------------------------------------------------
# MALFORMED / EDGE STDIN — must never crash.
# ---------------------------------------------------------------------------

@test "allow: empty stdin" {
  assert_decision allow ''
}

@test "allow: empty JSON object" {
  assert_decision allow '{}'
}

@test "allow: non-JSON garbage on stdin" {
  assert_decision allow 'garbage not json'
}

@test "allow: tool_input is null" {
  assert_decision allow '{"tool_input":null}'
}

@test "guard exits 0 on empty stdin (no crash)" {
  run bash -c "printf '' | /usr/bin/env bash '$GUARD'"
  [ "$status" -eq 0 ]
}

@test "guard exits 0 on garbage stdin (no crash)" {
  run bash -c "printf '%s' 'not json at all' | /usr/bin/env bash '$GUARD'"
  [ "$status" -eq 0 ]
}

@test "guard exits 0 even when it blocks (decision is in stdout JSON)" {
  local payload
  payload="$(obj_payload 'gh pr merge 123')"
  run bash -c "printf '%s' '$payload' | /usr/bin/env bash '$GUARD'"
  [ "$status" -eq 0 ]
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
}
