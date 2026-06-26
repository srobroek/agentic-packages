#!/usr/bin/env bats
#
# Coverage for package-file-warn.sh — a non-blocking PreToolUse hook that warns
# when a dependency manifest is edited directly. Tests assert the warn/allow
# decision (presence/absence of additionalContext) and that the script PARSES
# under /bin/bash (macOS bash 3.2.57).
#
# Run: bats packages/hooks-package-file-guard/tests/package-file-warn.bats

setup() {
  SCRIPTS="${BATS_TEST_DIRNAME}/../scripts"
  WARN="${SCRIPTS}/package-file-warn.sh"
}

# --- helpers ---------------------------------------------------------------

# Build a PreToolUse payload for a direct file edit (Edit/Write/MultiEdit).
mk_edit() {
  jq -cn --arg fp "$1" '{tool_input: {file_path: $fp}}'
}

# Build a payload carrying an Edit replacement string alongside the file path —
# proves old_string is never treated as a path.
mk_edit_replace() {
  jq -cn --arg fp "$1" --arg new "$2" '{tool_input: {file_path: $fp, old_string: "x", new_string: $new}}'
}

# Build a NotebookEdit-shaped payload (.notebook_path).
mk_notebook() {
  jq -cn --arg np "$1" '{tool_input: {notebook_path: $np}}'
}

# Build a payload where tool_input is a bare STRING (the historical bypass).
mk_str() {
  jq -cn --arg s "$1" '{tool_input: $s}'
}

# Run the hook; capture $output, $status, and the decoded $context (empty => allow).
run_warn() {
  payload="$1"
  output="$(printf '%s' "$payload" | /bin/bash "$WARN")"
  status=$?
  context="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.additionalContext // empty' 2>/dev/null || true)"
}

# --- parse / portability floor --------------------------------------------

@test "package-file-warn.sh parses under /bin/bash (no bash-4 syntax)" {
  run /bin/bash -n "$WARN"
  [ "$status" -eq 0 ]
}

# --- manifest edits -> warn -------------------------------------------------

@test "editing package.json -> warn additionalContext" {
  run_warn "$(mk_edit "/repo/package.json")"
  [ "$status" -eq 0 ]
  [ -n "$context" ]
  case "$context" in *"package.json"*) : ;; *) false ;; esac
  case "$context" in *"pnpm add"*) : ;; *) false ;; esac
}

@test "editing Cargo.toml -> warn cargo add" {
  run_warn "$(mk_edit "/repo/Cargo.toml")"
  [ -n "$context" ]
  case "$context" in *"cargo add"*) : ;; *) false ;; esac
}

@test "editing go.mod -> warn go get" {
  run_warn "$(mk_edit "/repo/go.mod")"
  [ -n "$context" ]
  case "$context" in *"go get"*) : ;; *) false ;; esac
}

@test "editing pyproject.toml -> warn uv add" {
  run_warn "$(mk_edit "/repo/pyproject.toml")"
  [ -n "$context" ]
  case "$context" in *"uv add"*) : ;; *) false ;; esac
}

@test "editing Gemfile -> warn bundle add" {
  run_warn "$(mk_edit "/repo/Gemfile")"
  [ -n "$context" ]
  case "$context" in *"bundle add"*) : ;; *) false ;; esac
}

@test "editing composer.json -> warn composer require" {
  run_warn "$(mk_edit "/repo/composer.json")"
  [ -n "$context" ]
  case "$context" in *"composer require"*) : ;; *) false ;; esac
}

@test "nested-path manifest still keys on basename -> warn" {
  run_warn "$(mk_edit "/a/b/c/package.json")"
  [ -n "$context" ]
}

# --- non-manifest edits -> allow, no output --------------------------------

@test "editing a non-manifest file -> allow, no output" {
  run_warn "$(mk_edit "/repo/src/index.ts")"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "editing package-lock.json (not a manifest) -> allow, no output" {
  run_warn "$(mk_edit "/repo/package-lock.json")"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "editing requirements.txt (not in set) -> allow, no output" {
  run_warn "$(mk_edit "/repo/requirements.txt")"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# --- old_string / replacement text is never treated as a path --------------

@test "Edit with manifest-looking replacement text on a non-manifest file -> allow" {
  # new_string mentions package.json; file_path is a source file. Must NOT warn.
  run_warn "$(mk_edit_replace "/repo/src/app.ts" "see package.json")"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "Edit of a manifest still warns even with replacement text present" {
  run_warn "$(mk_edit_replace "/repo/package.json" "whatever")"
  [ -n "$context" ]
}

# --- NotebookEdit shape (.notebook_path) -----------------------------------

@test "notebook_path to a manifest -> warn" {
  run_warn "$(mk_notebook "/repo/pyproject.toml")"
  [ -n "$context" ]
}

@test "notebook_path to a non-manifest -> allow, no output" {
  run_warn "$(mk_notebook "/repo/notebook.ipynb")"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# --- string-form tool_input ------------------------------------------------

@test "string-form tool_input naming a manifest -> warn (no jq crash)" {
  run_warn "$(mk_str "/repo/go.mod")"
  [ "$status" -eq 0 ]
  [ -n "$context" ]
}

@test "string-form tool_input naming a non-manifest -> allow, no crash" {
  run_warn "$(mk_str "/repo/src/main.go")"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# --- malformed / empty stdin -----------------------------------------------

@test "empty stdin -> exit 0, no output" {
  run_warn ""
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "invalid JSON stdin -> exit 0, no crash" {
  run_warn "not json {"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "payload with no tool_input -> exit 0, no output" {
  run_warn "$(jq -cn '{tool_name: "Edit"}')"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}
