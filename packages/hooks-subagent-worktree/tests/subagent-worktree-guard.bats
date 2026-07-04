#!/usr/bin/env bats
#
# Tests for subagent-worktree-guard.sh — the PreToolUse:Agent isolation advisory.
#
# Portability floor: bash 3.2.57 + BSD sed/grep (stock macOS). These tests use
# only core bats (run / status / output) — no bats-support / bats-assert.
#
# The hook reads a JSON event on stdin and, for tool_name == "Agent", emits a
# non-blocking advisory. It NEVER denies. Contract:
#   * isolation key present  -> silent about isolation (parent already chose);
#                                a stale-worktree notice may still be emitted
#   * otherwise (Agent)      -> emit additionalContext advisory, exit 0
#   * non-Agent / empty       -> pass through, no output, exit 0

setup() {
  GUARD="${BATS_TEST_DIRNAME}/../scripts/subagent-worktree-guard.sh"
  [ -f "$GUARD" ] || { echo "guard script not found at $GUARD" >&2; return 1; }
  command -v jq >/dev/null 2>&1 || skip "jq not available"
}

# ctx_of <json-payload> -> the additionalContext string, or empty if no output
ctx_of() {
  printf '%s' "$1" | "$GUARD" | jq -r '.hookSpecificOutput.additionalContext // empty' 2>/dev/null
}

# --- pass-through (no output) ----------------------------------------------

@test "non-Agent tool passes through silently" {
  run bash -c 'printf "%s" "$1" | "$0"' "$GUARD" '{"tool_name":"Bash","tool_input":{"command":"ls"}}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "empty payload passes through silently" {
  run bash -c 'printf "" | "$0"' "$GUARD"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# --- never denies ----------------------------------------------------------

@test "never emits a deny decision" {
  out="$(printf '%s' '{"tool_name":"Agent","tool_input":{"description":"do work","prompt":"x"}}' | "$GUARD")"
  # permissionDecision must be absent (advisory uses additionalContext only)
  decision="$(printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecision // "none"')"
  [ "$decision" = "none" ]
}

@test "Agent with string tool_input does not crash" {
  run bash -c 'printf "%s" "$1" | "$0"' "$GUARD" '{"tool_name":"Agent","tool_input":"oops"}'
  [ "$status" -eq 0 ]
}

# --- isolation already chosen -> silent ------------------------------------

@test "Agent with isolation:worktree is silent" {
  [ -z "$(ctx_of '{"tool_name":"Agent","tool_input":{"description":"w","prompt":"x","isolation":"worktree"}}')" ]
}

@test "Agent with isolation:remote is silent" {
  [ -z "$(ctx_of '{"tool_name":"Agent","tool_input":{"description":"w","prompt":"x","isolation":"remote"}}')" ]
}

# --- undeclared spawn -> advisory ------------------------------------------

@test "Agent without isolation gets an advisory" {
  ctx="$(ctx_of '{"tool_name":"Agent","tool_input":{"description":"do work","prompt":"x","subagent_type":"general-purpose"}}')"
  [ -n "$ctx" ]
}

@test "advisory mentions worktree isolation, parallel, committing, and cleanup" {
  ctx="$(ctx_of '{"tool_name":"Agent","tool_input":{"description":"d","prompt":"x"}}')"
  printf '%s' "$ctx" | grep -qi 'worktree'
  printf '%s' "$ctx" | grep -qi 'commit'
  printf '%s' "$ctx" | grep -qi 'parallel'
  printf '%s' "$ctx" | grep -qi 'worktree remove'
}

@test "advisory exits 0 (non-blocking)" {
  run bash -c 'printf "%s" "$1" | "$0"' "$GUARD" '{"tool_name":"Agent","tool_input":{"description":"d","prompt":"x"}}'
  [ "$status" -eq 0 ]
}

# --- stale agent worktrees -> reap notice ------------------------------------

make_repo_with_stale_worktree() {
  STALE_WORK="$(mktemp -d "${TMPDIR:-/tmp}/guard-bats.XXXXXX")"
  STALE_REPO="${STALE_WORK}/repo"
  mkdir -p "$STALE_REPO"
  git -C "$STALE_REPO" init -q
  git -C "$STALE_REPO" config user.email t@example.com
  git -C "$STALE_REPO" config user.name "Test User"
  git -C "$STALE_REPO" config commit.gpgsign false
  printf 'hello\n' > "${STALE_REPO}/file.txt"
  git -C "$STALE_REPO" add file.txt
  git -C "$STALE_REPO" commit -qm init
  git -C "$STALE_REPO" worktree add -q -b worktree-old "${STALE_WORK}/wt-old"
}

@test "declared isolation + stale agent worktree -> stale notice with confirm-clean gate" {
  make_repo_with_stale_worktree
  ctx="$(ctx_of "{\"tool_name\":\"Agent\",\"cwd\":\"${STALE_REPO}\",\"tool_input\":{\"description\":\"d\",\"prompt\":\"x\",\"isolation\":\"worktree\"}}")"
  printf '%s' "$ctx" | grep -q 'Stale worktree notice'
  printf '%s' "$ctx" | grep -q 'wt-old'
  printf '%s' "$ctx" | grep -qi 'CONFIRM IT IS CLEAN'
  printf '%s' "$ctx" | grep -qi 'never discard uncommitted work'
  rm -rf "$STALE_WORK"
}

@test "declared isolation + repo without agent worktrees -> silent" {
  STALE_WORK="$(mktemp -d "${TMPDIR:-/tmp}/guard-bats.XXXXXX")"
  STALE_REPO="${STALE_WORK}/repo"
  mkdir -p "$STALE_REPO"
  git -C "$STALE_REPO" init -q
  [ -z "$(ctx_of "{\"tool_name\":\"Agent\",\"cwd\":\"${STALE_REPO}\",\"tool_input\":{\"description\":\"d\",\"prompt\":\"x\",\"isolation\":\"worktree\"}}")" ]
  rm -rf "$STALE_WORK"
}

@test "undeclared isolation + stale agent worktree -> advisory includes stale notice" {
  make_repo_with_stale_worktree
  ctx="$(ctx_of "{\"tool_name\":\"Agent\",\"cwd\":\"${STALE_REPO}\",\"tool_input\":{\"description\":\"d\",\"prompt\":\"x\"}}")"
  printf '%s' "$ctx" | grep -qi 'Subagent isolation'
  printf '%s' "$ctx" | grep -q 'Stale worktree notice'
  printf '%s' "$ctx" | grep -q 'wt-old'
  rm -rf "$STALE_WORK"
}
