#!/usr/bin/env bats
#
# Tests for subagent-worktree-guard.sh — the PreToolUse:Agent isolation guard.
#
# Portability floor: bash 3.2.57 + BSD sed/grep (stock macOS). These tests use
# only core bats (run / status / output) — no bats-support / bats-assert — so
# they run anywhere bats + jq + git are installed.
#
# The hook reads a JSON event on stdin and emits a Claude PreToolUse decision on
# stdout. It fires only for tool_name == "Agent":
#   * isolation key present       -> allow by omission (no output, exit 0)
#   * [iso:readonly]              -> allow + updatedInput, sentinel stripped
#   * [iso:extern]                -> allow + updatedInput, sentinel stripped
#   * [iso:direct] in a worktree  -> allow + updatedInput, sentinel stripped
#   * [iso:direct] on primary     -> deny (move to a worktree first)
#   * otherwise                   -> deny (undeclared spawn)
# Non-Agent tools and empty payloads pass through (no output, exit 0).

setup() {
  GUARD="${BATS_TEST_DIRNAME}/../scripts/subagent-worktree-guard.sh"
  [ -f "$GUARD" ] || {
    echo "guard script not found at $GUARD" >&2
    return 1
  }
  command -v jq >/dev/null 2>&1 || skip "jq not available"
  command -v git >/dev/null 2>&1 || skip "git not available"

  # Build a real primary checkout + a linked worktree so the [iso:direct] gate
  # has genuine git state to read via the payload's cwd. BATS_TEST_TMPDIR is
  # per-test and auto-cleaned.
  PRIMARY="${BATS_TEST_TMPDIR}/primary"
  WT="${BATS_TEST_TMPDIR}/wt"
  git init -q "$PRIMARY"
  git -C "$PRIMARY" config user.email t@t.t
  git -C "$PRIMARY" config user.name t
  git -C "$PRIMARY" commit -q --allow-empty -m init
  git -C "$PRIMARY" worktree add -q "$WT" -b feature
}

# decision_of <json-payload>
# Runs the guard with the payload on stdin and echoes the permissionDecision,
# or the literal string "allow" when the guard emits nothing.
decision_of() {
  local out
  out="$(printf '%s' "$1" | "$GUARD")"
  if [ -z "$out" ]; then
    printf 'allow'
  else
    printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecision'
  fi
}

# field_of <json-payload> <jq-filter>
field_of() {
  printf '%s' "$1" | "$GUARD" | jq -r "$2"
}

# --- pass-through cases -----------------------------------------------------

@test "non-Agent tool passes through (no output)" {
  run decision_of '{"tool_name":"Bash","tool_input":{"command":"ls"}}'
  [ "$status" -eq 0 ]
  [ "$output" = "allow" ]
}

@test "empty payload passes through (no output)" {
  run bash -c 'printf "" | "$0"' "$GUARD"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "Agent with string tool_input does not crash, passes through" {
  # A bare-string tool_input must not throw; with no object there is no
  # isolation and no description, so the guard denies (an undeclared spawn).
  run decision_of '{"tool_name":"Agent","tool_input":"oops"}'
  [ "$status" -eq 0 ]
  [ "$output" = "deny" ]
}

# --- isolation already chosen ----------------------------------------------

@test "Agent with isolation:worktree allows by omission" {
  run decision_of '{"tool_name":"Agent","tool_input":{"description":"write","prompt":"x","isolation":"worktree"}}'
  [ "$status" -eq 0 ]
  [ "$output" = "allow" ]
}

@test "Agent with isolation:remote allows by omission" {
  run decision_of '{"tool_name":"Agent","tool_input":{"description":"work","prompt":"x","isolation":"remote"}}'
  [ "$output" = "allow" ]
}

# --- undeclared spawn -> deny ----------------------------------------------

@test "Agent without isolation or sentinel is denied" {
  run decision_of '{"tool_name":"Agent","tool_input":{"description":"do work","prompt":"x","subagent_type":"general-purpose"}}'
  [ "$status" -eq 0 ]
  [ "$output" = "deny" ]
}

@test "deny reason names every option (worktree + all three tokens)" {
  out="$(printf '%s' '{"tool_name":"Agent","tool_input":{"description":"d","prompt":"x"}}' | "$GUARD")"
  reason="$(printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecisionReason')"
  printf '%s' "$reason" | grep -q '"isolation":"worktree"'
  printf '%s' "$reason" | grep -qF '[iso:readonly]'
  printf '%s' "$reason" | grep -qF '[iso:extern]'
  printf '%s' "$reason" | grep -qF '[iso:direct]'
}

# --- [iso:readonly] / [iso:extern] -> allow + strip ------------------------

@test "[iso:readonly] is allowed and stripped" {
  p='{"tool_name":"Agent","tool_input":{"description":"inspect things [iso:readonly]","prompt":"x"}}'
  run decision_of "$p"
  [ "$output" = "allow" ]
  [ "$(field_of "$p" '.hookSpecificOutput.updatedInput.description')" = "inspect things" ]
}

@test "[iso:extern] is allowed and stripped" {
  p='{"tool_name":"Agent","tool_input":{"description":"clone and build [iso:extern]","prompt":"x"}}'
  run decision_of "$p"
  [ "$output" = "allow" ]
  [ "$(field_of "$p" '.hookSpecificOutput.updatedInput.description')" = "clone and build" ]
}

@test "readonly/extern allow regardless of cwd (primary checkout is fine)" {
  p="$(printf '{"tool_name":"Agent","cwd":"%s","tool_input":{"description":"x [iso:readonly]","prompt":"p"}}' "$PRIMARY")"
  run decision_of "$p"
  [ "$output" = "allow" ]
}

@test "sentinel mid-description is stripped cleanly" {
  p='{"tool_name":"Agent","tool_input":{"description":"before [iso:extern] after","prompt":"x"}}'
  [ "$(field_of "$p" '.hookSpecificOutput.updatedInput.description')" = "before after" ]
}

@test "updatedInput preserves the other tool_input fields" {
  p='{"tool_name":"Agent","tool_input":{"description":"x [iso:readonly]","prompt":"PROMPT","subagent_type":"coder","model":"haiku"}}'
  [ "$(field_of "$p" '.hookSpecificOutput.updatedInput.prompt')" = "PROMPT" ]
  [ "$(field_of "$p" '.hookSpecificOutput.updatedInput.subagent_type')" = "coder" ]
  [ "$(field_of "$p" '.hookSpecificOutput.updatedInput.model')" = "haiku" ]
}

# --- [iso:direct] gate: depends on whether cwd is a worktree ---------------

@test "[iso:direct] from a linked worktree is allowed and stripped" {
  p="$(printf '{"tool_name":"Agent","cwd":"%s","tool_input":{"description":"edit the tree [iso:direct]","prompt":"x"}}' "$WT")"
  run decision_of "$p"
  [ "$output" = "allow" ]
  [ "$(field_of "$p" '.hookSpecificOutput.updatedInput.description')" = "edit the tree" ]
}

@test "[iso:direct] from a worktree SUBDIR is allowed (relative git-common-dir resolved)" {
  mkdir -p "$WT/nested/deep"
  p="$(printf '{"tool_name":"Agent","cwd":"%s","tool_input":{"description":"edit [iso:direct]","prompt":"x"}}' "$WT/nested/deep")"
  run decision_of "$p"
  [ "$output" = "allow" ]
}

@test "[iso:direct] on the PRIMARY checkout is denied" {
  p="$(printf '{"tool_name":"Agent","cwd":"%s","tool_input":{"description":"edit the tree [iso:direct]","prompt":"x"}}' "$PRIMARY")"
  run decision_of "$p"
  [ "$output" = "deny" ]
}

@test "[iso:direct] on a primary-checkout SUBDIR is also denied (not misread as a worktree)" {
  mkdir -p "$PRIMARY/sub/dir"
  p="$(printf '{"tool_name":"Agent","cwd":"%s","tool_input":{"description":"edit [iso:direct]","prompt":"x"}}' "$PRIMARY/sub/dir")"
  run decision_of "$p"
  [ "$output" = "deny" ]
}

@test "[iso:direct] deny reason tells the caller to move into a worktree" {
  p="$(printf '{"tool_name":"Agent","cwd":"%s","tool_input":{"description":"edit [iso:direct]","prompt":"x"}}' "$PRIMARY")"
  reason="$(printf '%s' "$p" | "$GUARD" | jq -r '.hookSpecificOutput.permissionDecisionReason')"
  printf '%s' "$reason" | grep -qi 'worktree'
  printf '%s' "$reason" | grep -qF '[iso:direct]'
}

@test "[iso:direct] outside any git repo fails open (allowed)" {
  # A non-git cwd cannot be classified as 'primary'; the gate must not block a
  # spawn it cannot reason about.
  p="$(printf '{"tool_name":"Agent","cwd":"%s","tool_input":{"description":"edit [iso:direct]","prompt":"x"}}' "$BATS_TEST_TMPDIR")"
  # BATS_TEST_TMPDIR itself is not a git repo (the repos are subdirs of it).
  run decision_of "$p"
  [ "$output" = "allow" ]
}

@test "[iso:direct] with no cwd falls back to PWD without crashing" {
  # No cwd key: the guard falls back to $PWD. We only assert it produces a
  # valid decision (allow or deny) and does not error.
  run decision_of '{"tool_name":"Agent","tool_input":{"description":"edit [iso:direct]","prompt":"x"}}'
  [ "$status" -eq 0 ]
  [ "$output" = "allow" ] || [ "$output" = "deny" ]
}

# --- no re-fire loop --------------------------------------------------------

@test "a stripped description (token gone) denies as undeclared (documents no-re-fire need)" {
  # Feed a stripped form back in as a fresh spawn. With the sentinel gone and no
  # isolation added, this WOULD deny — which is why the runtime must NOT re-fire
  # PreToolUse on updatedInput. The no-re-fire guarantee is the runtime's
  # (verified separately end-to-end).
  run decision_of '{"tool_name":"Agent","tool_input":{"description":"edit the tree","prompt":"x"}}'
  [ "$output" = "deny" ]
}
