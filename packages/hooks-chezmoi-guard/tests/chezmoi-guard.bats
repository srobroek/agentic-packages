#!/usr/bin/env bats
#
# Adversarial coverage for chezmoi-guard.sh. These tests stub the `chezmoi` CLI
# (or remove it from PATH) so the managed-file membership list is deterministic,
# then assert the advisory/allow decision plus that the script PARSES under
# /bin/bash (macOS bash 3.2.57).
#
# The hook is NON-BLOCKING: it emits permissionDecision:"allow" + additionalContext
# when a write targets a chezmoi-managed file, rather than denying. Tests check
# that the advisory fires (allow + additionalContext present) or is silent (no
# additionalContext).
#
# Run: bats packages/hooks-chezmoi-guard/tests/chezmoi-guard.bats

setup() {
  SCRIPTS="${BATS_TEST_DIRNAME}/../scripts"
  GUARD="${SCRIPTS}/chezmoi-guard.sh"

  # Isolated TMPDIR per test so the per-user membership cache never leaks between
  # tests and never collides with a real ~/.../chezmoi-managed-cache.
  TEST_TMP="$(mktemp -d)"
  export TMPDIR="$TEST_TMP"

  # A directory holding our fake `chezmoi` shim, prepended to PATH on demand.
  STUB_DIR="$TEST_TMP/stub-bin"
  mkdir -p "$STUB_DIR"

  # The set of paths our stub reports as managed. Use a stable home-rooted path.
  MANAGED_FILE="$HOME/.config/agentic-tools/steering/index.md"
  MANAGED_LIST="$TEST_TMP/managed.txt"
  printf '%s\n' "$MANAGED_FILE" > "$MANAGED_LIST"
}

teardown() {
  rm -rf "$TEST_TMP"
}

# --- helpers ---------------------------------------------------------------

# Install a fake `chezmoi` on PATH that prints our managed list for
# `chezmoi managed ...` and exits 0 otherwise.
with_chezmoi() {
  cat > "$STUB_DIR/chezmoi" <<EOF
#!/bin/sh
case "\$1" in
  managed) cat "$MANAGED_LIST" ;;
  *) : ;;
esac
EOF
  chmod +x "$STUB_DIR/chezmoi"
  export PATH="$STUB_DIR:$PATH"
}

# Build a PreToolUse payload with an object tool_input carrying a shell command.
mk_cmd() {
  jq -cn --arg cmd "$1" '{tool_input: {command: $cmd}}'
}

# Build a PreToolUse payload for a direct file edit (Edit/Write/MultiEdit).
mk_edit() {
  jq -cn --arg fp "$1" '{tool_input: {file_path: $fp}}'
}

# Build a payload where tool_input is a bare STRING (the historical bypass) — a
# direct write target expressed as just the path string.
mk_str() {
  jq -cn --arg s "$1" '{tool_input: $s}'
}

# Run the guard; capture $output, $status, $decision, and $ctx.
# decision == "allow" means the advisory fired; empty means silent allow.
run_guard() {
  payload="$1"
  output="$(printf '%s' "$payload" | /bin/bash "$GUARD")"
  status=$?
  decision="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.permissionDecision // empty' 2>/dev/null || true)"
  ctx="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.additionalContext // empty' 2>/dev/null || true)"
}

# --- parse / portability floor --------------------------------------------

@test "chezmoi-guard.sh parses under /bin/bash (no bash-4 syntax)" {
  run /bin/bash -n "$GUARD"
  [ "$status" -eq 0 ]
}

# --- direct edit of a managed file -> advisory (allow + additionalContext) -

@test "managed file direct edit -> advisory allow" {
  with_chezmoi
  run_guard "$(mk_edit "$MANAGED_FILE")"
  [ "$status" -eq 0 ]
  [ "$decision" = "allow" ]
  [ -n "$ctx" ]
}

# --- ../-traversal equivalent of a managed file -> advisory (proves the fix) -

@test "../-traversal equivalent of managed file -> advisory allow (canonicalization)" {
  with_chezmoi
  # ~/.config/agentic-tools/steering/index.md reached via a .. detour through a
  # sibling dir. Without lexical canonicalization this dodged exact membership.
  traversal="$HOME/.config/agentic-tools/steering/../steering/index.md"
  run_guard "$(mk_edit "$traversal")"
  [ "$status" -eq 0 ]
  [ "$decision" = "allow" ]
  [ -n "$ctx" ]
}

@test "../-traversal via parent of managed file -> advisory allow" {
  with_chezmoi
  traversal="$HOME/.config/agentic-tools/../agentic-tools/steering/index.md"
  run_guard "$(mk_edit "$traversal")"
  [ "$status" -eq 0 ]
  [ "$decision" = "allow" ]
  [ -n "$ctx" ]
}

# --- read-only command referencing a managed path -> silent allow -----------

@test "read-only 'cat managed 2>/dev/null' -> allow" {
  with_chezmoi
  run_guard "$(mk_cmd "cat $MANAGED_FILE 2>/dev/null")"
  [ "$status" -eq 0 ]
  [ -z "$decision" ]
}

@test "read-only 'diff managed other' -> allow" {
  with_chezmoi
  run_guard "$(mk_cmd "diff $MANAGED_FILE /tmp/other")"
  [ "$status" -eq 0 ]
  [ -z "$decision" ]
}

# --- shell write to a managed file -> advisory (allow + additionalContext) --

@test "redirect overwrite of managed file -> advisory allow" {
  with_chezmoi
  run_guard "$(mk_cmd "echo hi > $MANAGED_FILE")"
  [ "$status" -eq 0 ]
  [ "$decision" = "allow" ]
  [ -n "$ctx" ]
}

@test "tee into managed file -> advisory allow" {
  with_chezmoi
  run_guard "$(mk_cmd "echo hi | tee $MANAGED_FILE")"
  [ "$status" -eq 0 ]
  [ "$decision" = "allow" ]
  [ -n "$ctx" ]
}

@test "cp destination is managed file -> advisory allow" {
  with_chezmoi
  run_guard "$(mk_cmd "cp /tmp/src $MANAGED_FILE")"
  [ "$status" -eq 0 ]
  [ "$decision" = "allow" ]
  [ -n "$ctx" ]
}

@test "cp SOURCE is managed (dest unmanaged) -> silent allow" {
  with_chezmoi
  run_guard "$(mk_cmd "cp $MANAGED_FILE /tmp/dst")"
  [ "$status" -eq 0 ]
  [ -z "$decision" ]
}

@test "cp dest managed WITH trailing redirect -> advisory allow (redirect stripped, not taken as dest)" {
  # Regression: $NF naively took the redirect token (/dev/null) as the
  # destination, so the real managed write slipped through. Strip redirects first.
  with_chezmoi
  run_guard "$(mk_cmd "cp /tmp/src $MANAGED_FILE >/dev/null 2>&1")"
  [ "$status" -eq 0 ]
  [ "$decision" = "allow" ]
  [ -n "$ctx" ]
}

@test "mv dest managed WITH trailing redirect -> advisory allow" {
  with_chezmoi
  run_guard "$(mk_cmd "mv /tmp/src $MANAGED_FILE 2>/dev/null")"
  [ "$status" -eq 0 ]
  [ "$decision" = "allow" ]
  [ -n "$ctx" ]
}

@test "../-traversal redirect write to managed file -> advisory allow" {
  with_chezmoi
  traversal="$HOME/.config/agentic-tools/steering/../steering/index.md"
  run_guard "$(mk_cmd "echo hi > $traversal")"
  [ "$status" -eq 0 ]
  [ "$decision" = "allow" ]
  [ -n "$ctx" ]
}

# --- string-form tool_input write to managed file -> advisory (proves the fix) --

@test "string-form tool_input edit of managed file -> advisory allow (no bypass)" {
  with_chezmoi
  run_guard "$(mk_str "$MANAGED_FILE")"
  [ "$status" -eq 0 ]
  [ "$decision" = "allow" ]
  [ -n "$ctx" ]
}

@test "string-form tool_input unmanaged path -> allow, no jq crash" {
  with_chezmoi
  run_guard "$(mk_str "$HOME/.config/agentic-tools/steering/UNMANAGED.md")"
  [ "$status" -eq 0 ]
  [ -z "$decision" ]
}

@test "string-form tool_input redirect write to managed file -> advisory allow (falls through to command check)" {
  with_chezmoi
  run_guard "$(mk_str "echo x > $MANAGED_FILE")"
  [ "$status" -eq 0 ]
  [ "$decision" = "allow" ]
  [ -n "$ctx" ]
}

# --- unmanaged file -> silent allow ----------------------------------------

@test "unmanaged file direct edit -> allow" {
  with_chezmoi
  run_guard "$(mk_edit "$HOME/.config/agentic-tools/steering/NOT-MANAGED.md")"
  [ "$status" -eq 0 ]
  [ -z "$decision" ]
}

@test "unmanaged file redirect write -> allow" {
  with_chezmoi
  run_guard "$(mk_cmd "echo x > $HOME/.config/agentic-tools/steering/NOT-MANAGED.md")"
  [ "$status" -eq 0 ]
  [ -z "$decision" ]
}

# --- wrapper-prefixed writes to managed file -> advisory (proves false-negative fix) --
# Branch (b) must strip leading wrappers before extracting the first_word verb.

@test "sudo tee MANAGED -> advisory allow (wrapper-prefixed write)" {
  with_chezmoi
  run_guard "$(mk_cmd "sudo tee $MANAGED_FILE")"
  [ "$status" -eq 0 ]
  [ "$decision" = "allow" ]
  [ -n "$ctx" ]
}

@test "sudo rm MANAGED -> advisory allow (wrapper-prefixed rm)" {
  with_chezmoi
  run_guard "$(mk_cmd "sudo rm $MANAGED_FILE")"
  [ "$status" -eq 0 ]
  [ "$decision" = "allow" ]
  [ -n "$ctx" ]
}

@test "env rm MANAGED -> advisory allow (env wrapper)" {
  with_chezmoi
  run_guard "$(mk_cmd "env rm $MANAGED_FILE")"
  [ "$status" -eq 0 ]
  [ "$decision" = "allow" ]
  [ -n "$ctx" ]
}

@test "time tee MANAGED -> advisory allow (time wrapper)" {
  with_chezmoi
  run_guard "$(mk_cmd "time tee $MANAGED_FILE")"
  [ "$status" -eq 0 ]
  [ "$decision" = "allow" ]
  [ -n "$ctx" ]
}

@test "cat x | sudo tee MANAGED -> advisory allow (piped wrapper)" {
  with_chezmoi
  run_guard "$(mk_cmd "cat /tmp/x | sudo tee $MANAGED_FILE")"
  [ "$status" -eq 0 ]
  [ "$decision" = "allow" ]
  [ -n "$ctx" ]
}

@test "sudo -u root tee MANAGED -> advisory allow (sudo with -u option)" {
  with_chezmoi
  run_guard "$(mk_cmd "sudo -u root tee $MANAGED_FILE")"
  [ "$status" -eq 0 ]
  [ "$decision" = "allow" ]
  [ -n "$ctx" ]
}

@test "sudo cat MANAGED -> silent allow (wrapper + read-only verb)" {
  with_chezmoi
  run_guard "$(mk_cmd "sudo cat $MANAGED_FILE")"
  [ "$status" -eq 0 ]
  [ -z "$decision" ]
}

# --- read-only managed reference in compound command -> NO advisory ---------
# Regression: chmod /tmp/foo is in-place verb segment but MANAGED_FILE appears
# only in the diff segment (a read-only verb) — must be completely silent.

@test "chmod /tmp/foo && diff MANAGED /tmp/foo -> no advisory (segment-scoped)" {
  with_chezmoi
  run_guard "$(mk_cmd "chmod /tmp/foo && diff $MANAGED_FILE /tmp/foo")"
  [ "$status" -eq 0 ]
  [ -z "$decision" ]
}

# --- chezmoi absent -> clean allow (exit 0) ---------------------------------

@test "chezmoi absent: direct edit of would-be-managed file -> allow exit 0" {
  # Run with a PATH that contains NO chezmoi. Build a minimal PATH from the dirs
  # the script needs (jq, grep, sed, awk, date, stat, id, cat) but no chezmoi.
  jq_dir="$(dirname "$(command -v jq)")"
  run_guard_no_chezmoi() {
    output="$(printf '%s' "$1" | PATH="/usr/bin:/bin:$jq_dir" /bin/bash "$GUARD")"
    status=$?
    decision="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.permissionDecision // empty' 2>/dev/null || true)"
  }
  run_guard_no_chezmoi "$(mk_edit "$MANAGED_FILE")"
  [ "$status" -eq 0 ]
  [ -z "$decision" ]
}

@test "chezmoi absent: shell write to would-be-managed file -> allow exit 0" {
  jq_dir="$(dirname "$(command -v jq)")"
  output="$(printf '%s' "$(mk_cmd "echo x > $MANAGED_FILE")" | PATH="/usr/bin:/bin:$jq_dir" /bin/bash "$GUARD")"
  status=$?
  decision="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.permissionDecision // empty' 2>/dev/null || true)"
  [ "$status" -eq 0 ]
  [ -z "$decision" ]
}

# --- malformed / empty stdin -----------------------------------------------

@test "empty stdin -> exit 0, no decision" {
  with_chezmoi
  run_guard ""
  [ "$status" -eq 0 ]
  [ -z "$decision" ]
}

@test "invalid JSON stdin -> exit 0, no crash" {
  with_chezmoi
  run_guard "not json {"
  [ "$status" -eq 0 ]
  [ -z "$decision" ]
}

@test "benign command (no managed target) -> allow" {
  with_chezmoi
  run_guard "$(mk_cmd "ls -la /tmp")"
  [ "$status" -eq 0 ]
  [ -z "$decision" ]
}
