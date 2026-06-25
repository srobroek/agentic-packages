#!/usr/bin/env bats
#
# Tests for git-guard.sh — the PreToolUse git-safety hook.
#
# Portability floor: bash 3.2.57 + BSD sed/grep (stock macOS). These tests use
# only core bats (run / status / output) — no bats-support / bats-assert — so
# they run anywhere bats + jq are installed.
#
# The hook reads a JSON event on stdin and emits a Claude PreToolUse decision on
# stdout: {hookSpecificOutput:{hookEventName,permissionDecision,...}}. When no
# guard fires it emits nothing and exits 0 ("allow" by omission).

setup() {
  GUARD="${BATS_TEST_DIRNAME}/../scripts/git-guard.sh"
  [ -f "$GUARD" ] || {
    echo "guard script not found at $GUARD" >&2
    return 1
  }
  if ! command -v jq >/dev/null 2>&1; then
    skip "jq not available"
  fi
}

# decision_of <json-payload>
# Runs the guard with the payload on stdin and echoes the permissionDecision,
# or the literal string "allow" when the guard emits nothing.
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
# HARD DENY — reset --hard (incl. bypass orderings) and force push.
# ---------------------------------------------------------------------------

@test "deny: plain reset --hard (object tool_input)" {
  assert_decision deny '{"tool_input":{"command":"git reset --hard"}}'
}

@test "deny: reset --hard via STRING tool_input (old idiom bypass)" {
  # The naive `.tool_input.command // .tool_input` jq threw on a string and
  # silently allowed this. Type-checked idiom must still deny.
  assert_decision deny '{"tool_input":"git reset --hard"}'
}

@test "deny: reset HEAD --hard (--hard is NOT the immediate next token)" {
  assert_decision deny '{"tool_input":{"command":"git reset HEAD --hard"}}'
}

@test "deny: reset --hard HEAD~3 (trailing ref)" {
  assert_decision deny '{"tool_input":{"command":"git reset --hard HEAD~3"}}'
}

@test "deny: -C with single-quoted spaced path then reset --hard" {
  assert_decision deny "{\"tool_input\":{\"command\":\"git -C '/path with space' reset --hard\"}}"
}

@test "deny: -C with double-quoted spaced path then reset --hard" {
  assert_decision deny '{"tool_input":{"command":"git -C \"/path with space\" reset --hard"}}'
}

@test "deny: -c config kv with spaced value then reset --hard" {
  assert_decision deny "{\"tool_input\":{\"command\":\"git -c user.name='A B' reset --hard\"}}"
}

@test "deny: --git-dir spaced inline value then reset --hard" {
  assert_decision deny "{\"tool_input\":{\"command\":\"git --git-dir='/a b/.git' reset --hard\"}}"
}

@test "deny: multiple stacked global opts then reset --hard" {
  assert_decision deny "{\"tool_input\":{\"command\":\"git -C '/a b' -c x=y --no-pager reset --hard\"}}"
}

@test "deny: push --force" {
  assert_decision deny '{"tool_input":{"command":"git push --force origin main"}}'
}

@test "deny: push -f short flag" {
  assert_decision deny '{"tool_input":{"command":"git push -f"}}'
}

@test "deny: push --force-with-lease" {
  assert_decision deny '{"tool_input":{"command":"git push --force-with-lease"}}'
}

@test "deny: push origin main --force (force is trailing token)" {
  assert_decision deny '{"tool_input":{"command":"git push origin main --force"}}'
}

@test "deny: push -f=origin (equals boundary)" {
  assert_decision deny '{"tool_input":{"command":"git push -f=origin"}}'
}

# ---------------------------------------------------------------------------
# ASK — recoverable destructive ops (downgraded per locked severity policy).
# ---------------------------------------------------------------------------

@test "ask: clean -df (force flag in a cluster, not standalone -f)" {
  assert_decision ask '{"tool_input":{"command":"git clean -df"}}'
}

@test "ask: clean -xdf (force flag mid/end of cluster)" {
  assert_decision ask '{"tool_input":{"command":"git clean -xdf"}}'
}

@test "ask: clean -fd (force flag first in cluster)" {
  assert_decision ask '{"tool_input":{"command":"git clean -fd"}}'
}

@test "ask: clean --force long form" {
  assert_decision ask '{"tool_input":{"command":"git clean --force"}}'
}

@test "ask: clean -f standalone" {
  assert_decision ask '{"tool_input":{"command":"git clean -f"}}'
}

@test "ask: clean -df via STRING tool_input" {
  assert_decision ask '{"tool_input":"git clean -df"}'
}

@test "ask: -C spaced path then clean -df" {
  assert_decision ask "{\"tool_input\":{\"command\":\"git -C '/path with space' clean -df\"}}"
}

@test "ask: branch -d (was deny, downgraded to ask)" {
  assert_decision ask '{"tool_input":{"command":"git branch -d feature"}}'
}

@test "ask: branch -D force delete" {
  assert_decision ask '{"tool_input":{"command":"git branch -D feature"}}'
}

@test "ask: branch --delete" {
  assert_decision ask '{"tool_input":{"command":"git branch --delete x"}}'
}

@test "ask: stash drop" {
  assert_decision ask '{"tool_input":{"command":"git stash drop"}}'
}

@test "ask: stash clear" {
  assert_decision ask '{"tool_input":{"command":"git stash clear"}}'
}

@test "ask: restore --staged" {
  assert_decision ask '{"tool_input":{"command":"git restore --staged file.txt"}}'
}

@test "ask: tag -d" {
  assert_decision ask '{"tool_input":{"command":"git tag -d v1.0"}}'
}

@test "ask: checkout -- path" {
  assert_decision ask '{"tool_input":{"command":"git checkout -- file.txt"}}'
}

@test "ask: worktree remove (stays ask)" {
  assert_decision ask '{"tool_input":{"command":"git worktree remove wt"}}'
}

# ---------------------------------------------------------------------------
# ALLOW — non-destructive commands and near-miss false-positive guards.
# ---------------------------------------------------------------------------

@test "allow: git status" {
  assert_decision allow '{"tool_input":{"command":"git status"}}'
}

@test "allow: plain push (no force)" {
  assert_decision allow '{"tool_input":{"command":"git push"}}'
}

@test "allow: commit message that merely contains the phrase reset --hard" {
  assert_decision allow '{"tool_input":{"command":"git commit -m \"reset --hard stuff\""}}'
}

@test "allow: reset --soft (not --hard)" {
  assert_decision allow '{"tool_input":{"command":"git reset --soft HEAD~1"}}'
}

@test "allow: branch -a (list, no delete)" {
  assert_decision allow '{"tool_input":{"command":"git branch -a"}}'
}

@test "allow: branch --merged (no false positive on -merged)" {
  assert_decision allow '{"tool_input":{"command":"git branch --merged main"}}'
}

@test "allow: branch -m rename" {
  assert_decision allow '{"tool_input":{"command":"git branch -m oldname newname"}}'
}

@test "allow: clean -n dry run (no force flag)" {
  assert_decision allow '{"tool_input":{"command":"git clean -n"}}'
}

@test "allow: clean --help (no force)" {
  assert_decision allow '{"tool_input":{"command":"git clean --help"}}'
}

@test "allow: push --follow-tags (--f... is not -f)" {
  assert_decision allow '{"tool_input":{"command":"git push --follow-tags origin main"}}'
}

@test "allow: push --force-if-includes (safety flag, not force push)" {
  assert_decision allow '{"tool_input":{"command":"git push --force-if-includes origin x"}}'
}

@test "allow: checkout to a branch (no -- pathspec)" {
  assert_decision allow '{"tool_input":{"command":"git checkout main"}}'
}

# ---------------------------------------------------------------------------
# MALFORMED / EDGE STDIN — must never crash; default to allow.
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

@test "guard exits 0 even when it denies (Claude reads decision from stdout)" {
  run bash -c "printf '%s' '{\"tool_input\":{\"command\":\"git reset --hard\"}}' | /usr/bin/env bash '$GUARD'"
  [ "$status" -eq 0 ]
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
}
