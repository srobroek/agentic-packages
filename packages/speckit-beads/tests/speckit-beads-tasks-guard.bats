#!/usr/bin/env bats
#
# Coverage for speckit-beads-tasks-guard.sh, which has three roles branched on
# the tool: a DENY on writes to specs/*/tasks.md, and advisories on a Bash
# command or a Skill invocation that touches the same ground.
#
# The deny is the part worth pinning hardest in both directions. tasks.md is
# never authored under the beads workflow, so writing one must be refused with
# the replacement workflow in the reason; but a write to any OTHER tasks.md, or
# to a spec file that is not tasks.md, is ordinary work and must pass. So must
# everything in a repository with no beads workspace.
#
# `bd` and `jq` are stubbed on PATH so these tests describe the guard's logic
# rather than the machine's beads state.
#
# Portability floor: bash 3.2.57 + BSD userland.
# Run: bats packages/speckit-beads/tests/speckit-beads-tasks-guard.bats

setup() {
  GUARD="${BATS_TEST_DIRNAME}/../scripts/speckit-beads-tasks-guard.sh"
  command -v jq >/dev/null 2>&1 || skip "jq not available"

  WORK="$BATS_TEST_TMPDIR/work"
  mkdir -p "$WORK/specs/001-feature"

  STUB="$BATS_TEST_TMPDIR/bin"
  mkdir -p "$STUB"
  printf '#!/bin/sh\nexit 0\n' >"$STUB/bd"
  chmod +x "$STUB/bd"
  PATH="$STUB:$PATH"
}

# write <tool> <file_path>
write() {
  output="$(jq -cn --arg t "$1" --arg p "$2" --arg d "$WORK" \
    '{cwd:$d,hook_event_name:"PreToolUse",tool_name:$t,tool_input:{file_path:$p}}' \
    | /bin/bash "$GUARD" 2>&1)" && status=0 || status=$?
}

# bash_cmd <command>
bash_cmd() {
  output="$(jq -cn --arg c "$1" --arg d "$WORK" \
    '{cwd:$d,hook_event_name:"PreToolUse",tool_name:"Bash",tool_input:{command:$c}}' \
    | /bin/bash "$GUARD" 2>&1)" && status=0 || status=$?
}

decision() {
  [ -z "$output" ] && { printf 'allow'; return; }
  printf '%s' "$output" | jq -r '.hookSpecificOutput.permissionDecision // "allow"'
}

@test "script parses under /bin/bash" {
  run /bin/bash -n "$GUARD"; [ "$status" -eq 0 ]
}

# --- the deny ----------------------------------------------------------------

@test "Write to specs/*/tasks.md is denied" {
  write Write "$WORK/specs/001-feature/tasks.md"
  [ "$(decision)" = "deny" ]
}

@test "Edit to specs/*/tasks.md is denied" {
  write Edit "$WORK/specs/001-feature/tasks.md"
  [ "$(decision)" = "deny" ]
}

@test "apply_patch to specs/*/tasks.md is denied" {
  # Codex sends the patch in tool_input.command, not file_path.
  output="$(jq -cn --arg c "*** Update File: $WORK/specs/001-feature/tasks.md" --arg d "$WORK" \
    '{cwd:$d,hook_event_name:"PreToolUse",tool_name:"apply_patch",tool_input:{command:$c}}' \
    | /bin/bash "$GUARD" 2>&1)" && status=0 || status=$?
  [ "$(decision)" = "deny" ]
}

@test "the denial carries the replacement workflow, so the agent self-corrects" {
  write Write "$WORK/specs/001-feature/tasks.md"
  printf '%s' "$output" | jq -r '.hookSpecificOutput.permissionDecisionReason' \
    | grep -q 'bd'
}

# --- what must pass ---------------------------------------------------------

@test "a spec file that is not tasks.md is allowed" {
  write Write "$WORK/specs/001-feature/spec.md"
  [ "$(decision)" = "allow" ]
}

@test "a tasks.md outside specs/ is allowed" {
  write Write "$WORK/docs/tasks.md"
  [ "$(decision)" = "allow" ]
}

@test "an ordinary source file is allowed and silent" {
  write Write "$WORK/src/main.py"
  [ "$(decision)" = "allow" ]
  [ -z "$output" ]
}

@test "no beads workspace -> allow" {
  printf '#!/bin/sh\nexit 1\n' >"$BATS_TEST_TMPDIR/bin/bd"
  chmod +x "$BATS_TEST_TMPDIR/bin/bd"
  write Write "$WORK/specs/001-feature/tasks.md"
  [ "$(decision)" = "allow" ]
}

@test "bd absent -> allow" {
  rm -f "$BATS_TEST_TMPDIR/bin/bd"
  write Write "$WORK/specs/001-feature/tasks.md"
  [ "$(decision)" = "allow" ]
}

# --- the Bash advisory is never a block -------------------------------------

@test "a Bash command touching tasks.md advises without blocking" {
  bash_cmd "cat $WORK/specs/001-feature/tasks.md"
  [ "$(decision)" = "allow" ]
}

@test "an unrelated Bash command is silent" {
  bash_cmd 'git status --short'
  [ "$(decision)" = "allow" ]
  [ -z "$output" ]
}

# --- fail open --------------------------------------------------------------

@test "empty payload -> exit 0, no output" {
  output="$(printf '' | /bin/bash "$GUARD" 2>&1)" && status=0 || status=$?
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "malformed payload -> exit 0, no output" {
  output="$(printf 'not json {' | /bin/bash "$GUARD" 2>&1)" && status=0 || status=$?
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "string-form tool_input allows, by documented choice" {
  # A bare-string tool_input carries no path to judge, so this guard allows
  # rather than guessing -- see the comment at the extraction block. That is a
  # narrower stance than the contract's general advice to read a string input,
  # and it is deliberate here because the deny needs a specific path.
  output="$(jq -cn --arg p "$WORK/specs/001-feature/tasks.md" --arg d "$WORK" \
    '{cwd:$d,hook_event_name:"PreToolUse",tool_name:"Write",tool_input:$p}' \
    | /bin/bash "$GUARD" 2>&1)" && status=0 || status=$?
  [ "$status" -eq 0 ]
  [ "$(decision)" = "allow" ]
}

@test "never emits ask" {
  write Write "$WORK/specs/001-feature/tasks.md"
  [ "$(decision)" != "ask" ]
  write Write "$WORK/src/main.py"
  [ "$(decision)" != "ask" ]
}
