#!/usr/bin/env bats
#
# Tests for no-ff-guard.sh — the PreToolUse hook that advises --no-ff on real
# `git merge` invocations.
#
# Portability floor: bash 3.2.57 + BSD sed/grep (stock macOS). These tests use
# only core bats (run / status / output) — no bats-support / bats-assert — so
# they run anywhere bats + jq are installed.
#
# Danger strings (`git merge`, ...) are NEVER placed on a bare command line:
# every payload is assembled via jq so a live PreToolUse hook in the session
# cannot intercept the literal.

setup() {
  GUARD="${BATS_TEST_DIRNAME}/../scripts/no-ff-guard.sh"
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
# ALLOW — not a real merge (read-only / recovery / non-merge subcommands).
# ---------------------------------------------------------------------------

@test "allow: merge-base (no boundary after 'merge')" {
  assert_decision allow "$(obj_payload 'git merge-base a b')"
}

@test "allow: mergetool (no boundary after 'merge')" {
  assert_decision allow "$(obj_payload 'git mergetool')"
}

@test "allow: merge-file (no boundary after 'merge')" {
  assert_decision allow "$(obj_payload 'git merge-file a b c')"
}

@test "allow: merge-tree (no boundary after 'merge')" {
  assert_decision allow "$(obj_payload 'git merge-tree x y')"
}

@test "allow: merge --abort (recovery, not a new merge)" {
  assert_decision allow "$(obj_payload 'git merge --abort')"
}

@test "allow: merge --continue (recovery, not a new merge)" {
  assert_decision allow "$(obj_payload 'git merge --continue')"
}

@test "allow: merge --quit (recovery, not a new merge)" {
  assert_decision allow "$(obj_payload 'git merge --quit')"
}

@test "allow: merge --ff-only x (explicit ff policy, not a no-ff target)" {
  assert_decision allow "$(obj_payload 'git merge --ff-only x')"
}

@test "allow: real --no-ff token present" {
  assert_decision allow "$(obj_payload 'git merge --no-ff feature')"
}

@test "allow: --no-ff with -C global option" {
  assert_decision allow "$(obj_payload 'git -C /repo merge --no-ff feature')"
}

# ---------------------------------------------------------------------------
# ASK — real merge lacking a genuine --no-ff token (advisory, NOT hard deny).
# ---------------------------------------------------------------------------

@test "ask: bare merge of a feature branch" {
  assert_decision ask "$(obj_payload 'git merge feature')"
}

@test "ask: merge with -C global option" {
  assert_decision ask "$(obj_payload 'git -C /repo merge feature')"
}

@test "ask: merge with stacked global options" {
  assert_decision ask "$(obj_payload 'git -C /repo --no-pager merge feature')"
}

@test "ask: --no-ff appears ONLY inside a trailing comment (must not satisfy)" {
  assert_decision ask "$(obj_payload 'git merge feature # remember --no-ff')"
}

@test "ask: real merge via STRING tool_input" {
  assert_decision ask "$(str_payload 'git merge feature')"
}

@test "advisory decision is exactly 'ask', never 'deny'" {
  local got
  got="$(decision_of "$(obj_payload 'git merge feature')")"
  [ "$got" = "ask" ]
  [ "$got" != "deny" ]
}

# ---------------------------------------------------------------------------
# MALFORMED / EDGE STDIN — must never crash; default to allow; exit 0.
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

@test "guard exits 0 even when it advises (decision is in stdout JSON)" {
  local payload
  payload="$(obj_payload 'git merge feature')"
  run bash -c "printf '%s' '$payload' | /usr/bin/env bash '$GUARD'"
  [ "$status" -eq 0 ]
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecision == "ask"' >/dev/null
}
