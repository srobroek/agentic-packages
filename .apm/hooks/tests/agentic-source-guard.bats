#!/usr/bin/env bats
#
# Coverage for agentic-source-guard.sh -- the PreToolUse hook that blocks
# MUTATION of APM-managed assets (installed skills/agents/hooks/rules) while
# leaving READS and skill INVOCATION untouched.
#
# Policy the guard enforces:
#   - Managed-path match is ^|/-anchored on a known dir followed by /, end, or
#     whitespace (a bare-dir arg like `find ~/.claude/skills -delete` counts;
#     an unrelated `/tmp/.claudette/...` or a file named `skills.md` does not).
#   - A Bash command that only READS a managed path is allowed. Read-only is
#     PROVEN, not assumed: every pipeline/list segment (split on | ; & && ||)
#     must lead with a known reader; interpreters (python/node/bash/sh) are
#     allowed only when running a script file, never inline -c/-e code.
#   - Any write redirect, cp/mv/rm/sed -i, command substitution, find action
#     primary (-exec/-delete/...), or unproven segment => BLOCK (exit 2).
#   - Edit/Write/MultiEdit to a managed file_path => BLOCK; to project source
#     (packages/**, .apm/**) => allow.
#
# Run: bats .apm/hooks/tests/agentic-source-guard.bats

setup() {
  GUARD="${BATS_TEST_DIRNAME}/../scripts/agentic-source-guard.sh"
  # A managed target the ^|/-anchored regex matches. Use a literal home-style
  # path; the guard never touches the filesystem, it only pattern-matches.
  MANAGED_SKILL="/home/u/.claude/skills/write-docs/SKILL.md"
  MANAGED_DIR="/home/u/.claude/skills"
}

# Bash PreToolUse payload with a command string.
mk_cmd() { jq -cn --arg c "$1" '{tool_name:"Bash",tool_input:{command:$c}}'; }
# Write/Edit payload with a file_path.
mk_file() { jq -cn --arg p "$1" '{tool_name:"Write",tool_input:{file_path:$p,content:"x"}}'; }

# run_guard <payload> -> sets $status
run_guard() { run bash "$GUARD" <<<"$1"; }

# --- reads against managed paths: ALLOW (exit 0) ---------------------------

@test "read: cat a managed file" {
  run_guard "$(mk_cmd "cat $MANAGED_SKILL")"
  [ "$status" -eq 0 ]
}

@test "read: ls a managed dir piped to head" {
  run_guard "$(mk_cmd "ls -la $MANAGED_DIR | head")"
  [ "$status" -eq 0 ]
}

@test "read: fd-redirect (2>&1) is not a write" {
  run_guard "$(mk_cmd "cat $MANAGED_SKILL 2>&1 | grep MUST")"
  [ "$status" -eq 0 ]
}

@test "read: redirect to /dev/null is not a write" {
  run_guard "$(mk_cmd "grep -q x $MANAGED_SKILL 2>/dev/null")"
  [ "$status" -eq 0 ]
}

@test "read: python running an installed skill script (not inline code)" {
  run_guard "$(mk_cmd "python3 /home/u/.claude/skills/resume-session/scripts/list-sessions.py --project /x")"
  [ "$status" -eq 0 ]
}

@test "read: test -d on a managed dir" {
  run_guard "$(mk_cmd "test -d $MANAGED_DIR")"
  [ "$status" -eq 0 ]
}

@test "read: two reader segments chained with ;" {
  run_guard "$(mk_cmd "ls $MANAGED_DIR; cat $MANAGED_SKILL")"
  [ "$status" -eq 0 ]
}

@test "read: newline-separated reader commands" {
  run_guard "$(mk_cmd "$(printf 'ls -la %s\nfind %s -name SKILL.md\n' "$MANAGED_DIR" "$MANAGED_DIR")")"
  [ "$status" -eq 0 ]
}

@test "read: find with -name only (no action primary)" {
  run_guard "$(mk_cmd "find $MANAGED_DIR -name SKILL.md")"
  [ "$status" -eq 0 ]
}

# --- mutations against managed paths: BLOCK (exit 2) -----------------------

@test "write: redirect into a managed file" {
  run_guard "$(mk_cmd "echo x > $MANAGED_SKILL")"
  [ "$status" -eq 2 ]
}

@test "write: append into a managed file" {
  run_guard "$(mk_cmd "cat foo >> $MANAGED_SKILL")"
  [ "$status" -eq 2 ]
}

@test "write: rm a managed file" {
  run_guard "$(mk_cmd "rm $MANAGED_SKILL")"
  [ "$status" -eq 2 ]
}

@test "write: sed -i a managed file" {
  run_guard "$(mk_cmd "sed -i s/a/b/ $MANAGED_SKILL")"
  [ "$status" -eq 2 ]
}

@test "write: reader THEN writer chained (ls && rm)" {
  run_guard "$(mk_cmd "ls $MANAGED_DIR && rm -rf $MANAGED_DIR/foo")"
  [ "$status" -eq 2 ]
}

@test "write: pipe a reader into tee (write via pipeline)" {
  run_guard "$(mk_cmd "echo x | tee $MANAGED_SKILL")"
  [ "$status" -eq 2 ]
}

@test "write: pipe find into xargs rm" {
  run_guard "$(mk_cmd "find $MANAGED_DIR -name x | xargs rm")"
  [ "$status" -eq 2 ]
}

@test "write: bash -c inline code is not a proven read" {
  run_guard "$(mk_cmd "bash -c 'rm $MANAGED_SKILL'")"
  [ "$status" -eq 2 ]
}

@test "write: command substitution hides intent" {
  run_guard "$(mk_cmd "echo \$(rm $MANAGED_SKILL) $MANAGED_DIR/y")"
  [ "$status" -eq 2 ]
}

@test "write: find -delete on a bare managed dir arg" {
  run_guard "$(mk_cmd "find $MANAGED_DIR -delete")"
  [ "$status" -eq 2 ]
}

@test "write: find -exec rm on a bare managed dir arg" {
  run_guard "$(mk_cmd "find $MANAGED_DIR -name x -exec rm {} ;")"
  [ "$status" -eq 2 ]
}

# --- Edit/Write tool payloads ---------------------------------------------

@test "edit: Write to a managed skill file is blocked" {
  run_guard "$(mk_file "$MANAGED_SKILL")"
  [ "$status" -eq 2 ]
}

@test "edit: Write to project .apm source is allowed" {
  run_guard "$(mk_file "/repo/agentic-packages/.apm/hooks/scripts/x.sh")"
  [ "$status" -eq 0 ]
}

# --- widened anchor must not over-block lookalikes -------------------------

@test "no-overblock: path merely CONTAINING a managed dir name (.claudette)" {
  run_guard "$(mk_file "/tmp/.claudette/notes.md")"
  [ "$status" -eq 0 ]
}

@test "no-overblock: a file literally named skills.md outside a managed tree" {
  run_guard "$(mk_file "/tmp/docs/skills.md")"
  [ "$status" -eq 0 ]
}

# --- robustness ------------------------------------------------------------

@test "empty stdin exits 0" {
  run bash "$GUARD" <<<''
  [ "$status" -eq 0 ]
}

@test "parses under bash (3.2 floor)" {
  run bash -n "$GUARD"
  [ "$status" -eq 0 ]
}
