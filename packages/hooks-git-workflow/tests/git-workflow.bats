#!/usr/bin/env bats
#
# Tests for hooks-git-workflow:
#   - pre-push-test-gate.sh   block git push unless unit tests ran green
#   - test-state-tracker.sh   record edit/test state (real test runners only)
#   - uncommitted-warn.sh     Stop-time dirty-tree nudge
#
# The push gate reads /tmp/codex-test-state-<repohash>.json. We compute the same
# hash the scripts use and seed that file to drive each case deterministically.
#
# Portability floor: bash 3.2.57 + BSD userland.
# Run: bats packages/hooks-git-workflow/tests/git-workflow.bats

setup() {
  # Hermetic git: ignore host system/global config (e.g. a corporate
  # core.hooksPath) so fixture commits are fast and deterministic.
  export GIT_CONFIG_SYSTEM=/dev/null GIT_CONFIG_GLOBAL=/dev/null
  # Absolute paths: the tracker tests run it inside a `cd "$REPO"` subshell, so a
  # relative script path would not resolve there.
  S="$(cd "${BATS_TEST_DIRNAME}/../scripts" && pwd -P)"
  GATE="$S/pre-push-test-gate.sh"
  TRACKER="$S/test-state-tracker.sh"
  WARN="$S/uncommitted-warn.sh"
  command -v jq >/dev/null 2>&1 || skip "jq not available"
  command -v git >/dev/null 2>&1 || skip "git not available"

  REPO="$(mktemp -d "${BATS_TEST_TMPDIR}/repo.XXXXXX")"
  REPO="$(cd "$REPO" && pwd -P)"
  git -C "$REPO" init -q
  git -C "$REPO" config user.email t@t.t
  git -C "$REPO" config user.name t
  # Make it a detectable-test project (go.mod -> "go test ./...").
  printf 'module x\n\ngo 1.21\n' > "$REPO/go.mod"
  # The state file path the scripts derive from the repo toplevel. MUST match the
  # scripts' calc exactly — they hash via `echo` (trailing newline included).
  STATE="/tmp/codex-test-state-$(echo "$REPO" | md5 2>/dev/null || echo "$REPO" | md5sum 2>/dev/null | cut -d' ' -f1).json"
  rm -f "$STATE"
}

teardown() { [ -n "${STATE:-}" ] && rm -f "$STATE"; }

# seed_state <last_edit> <last_test> <test_passed>
seed_state() {
  printf '{"last_edit":%s,"last_test":%s,"test_passed":%s}\n' "$1" "$2" "$3" > "$STATE"
}

# push_event <command>  -> JSON PreToolUse event with .cwd = $REPO
push_event() { jq -cn --arg c "$1" --arg w "$REPO" '{cwd:$w, tool_input:{command:$c}}'; }

run_gate() { output="$(printf '%s' "$1" | /bin/bash "$GATE" 2>&1)" && status=0 || status=$?; }
decision() { [ -z "$output" ] && { printf allow; return; }; printf '%s' "$output" | jq -r '.hookSpecificOutput.permissionDecision // "allow"'; }

# --- parse ------------------------------------------------------------------

@test "scripts parse under /bin/bash" {
  run /bin/bash -n "$GATE"; [ "$status" -eq 0 ]
  run /bin/bash -n "$TRACKER"; [ "$status" -eq 0 ]
  run /bin/bash -n "$WARN"; [ "$status" -eq 0 ]
}

# --- pre-push-test-gate -----------------------------------------------------

@test "gate: non-push command is ignored -> allow (silent)" {
  seed_state 100 50 false
  run_gate "$(push_event 'git status')"
  [ "$status" -eq 0 ]; [ -z "$output" ]
}

@test "gate: green tests after last edit -> allow" {
  seed_state 100 200 true   # tested after edit, passed
  run_gate "$(push_event 'git push origin main')"
  [ "$(decision)" = "allow" ]
}

@test "gate: edited but tests never ran -> deny" {
  seed_state 100 0 false
  run_gate "$(push_event 'git push')"
  [ "$(decision)" = "deny" ]
  printf '%s' "$output" | jq -r '.hookSpecificOutput.permissionDecisionReason' | grep -q 'go test'
}

@test "gate: tests stale (edited after last run) -> deny" {
  seed_state 200 100 true   # passed, but a later edit invalidates it
  run_gate "$(push_event 'git push')"
  [ "$(decision)" = "deny" ]
  printf '%s' "$output" | grep -q 'stale'
}

@test "gate: last test run failed -> deny" {
  seed_state 100 200 false  # tested after edit, but failed
  run_gate "$(push_event 'git push')"
  [ "$(decision)" = "deny" ]
}

@test "gate: no edits recorded -> allow (nothing changed)" {
  seed_state 0 0 false
  run_gate "$(push_event 'git push')"
  [ "$(decision)" = "allow" ]
}

@test "gate: SKIP_TEST_GATE=1 inline -> allow despite red state" {
  seed_state 100 0 false
  run_gate "$(push_event 'SKIP_TEST_GATE=1 git push')"
  [ "$(decision)" = "allow" ]
}

@test "gate: no state file at all -> warn + allow (never wedge)" {
  rm -f "$STATE"
  run_gate "$(push_event 'git push')"
  [ "$(decision)" = "allow" ]
  printf '%s' "$output" | jq -e '.hookSpecificOutput.additionalContext | test("TEST GATE")' >/dev/null
}

@test "gate: no detectable test command -> warn + allow" {
  rm -f "$REPO/go.mod"   # remove the only project marker
  seed_state 100 0 false
  run_gate "$(push_event 'git push')"
  [ "$(decision)" = "allow" ]
  printf '%s' "$output" | jq -e '.hookSpecificOutput.additionalContext | test("no unit-test command")' >/dev/null
}

@test "gate: empty stdin -> allow" {
  run_gate ""
  [ "$status" -eq 0 ]; [ -z "$output" ]
}

# --- test-state-tracker: only real test runners set test_passed -------------

# tracker_bash <command> <exit_code> : run tracker as a Bash PostToolUse event
tracker_bash() {
  jq -cn --arg c "$1" --argjson e "$2" '{tool_name:"Bash", tool_input:{command:$c}, tool_response:{exit_code:$e}}' \
    | (cd "$REPO" && /bin/bash "$TRACKER")
}

@test "tracker: a real 'go test' run records test_passed" {
  printf '{"last_edit":100,"last_test":0,"test_passed":false}\n' > "$STATE"
  tracker_bash "go test ./..." 0
  [ "$(jq -r '.test_passed' "$STATE")" = "true" ]
  [ "$(jq -r '.last_test' "$STATE")" != "0" ]
}

@test "tracker: 'cargo build' does NOT count as a test (build != test)" {
  printf '{"last_edit":100,"last_test":0,"test_passed":false}\n' > "$STATE"
  tracker_bash "cargo build" 0
  # last_test must stay 0 — a green build must not mark the suite as run.
  [ "$(jq -r '.last_test' "$STATE")" = "0" ]
}

@test "tracker: 'ruff check' does NOT count as a test" {
  printf '{"last_edit":100,"last_test":0,"test_passed":false}\n' > "$STATE"
  tracker_bash "ruff check ." 0
  [ "$(jq -r '.last_test' "$STATE")" = "0" ]
}

@test "tracker: an Edit stamps last_edit" {
  printf '{"last_edit":0,"last_test":0,"test_passed":false}\n' > "$STATE"
  jq -cn '{tool_name:"Edit", tool_input:{file_path:"x.go"}}' | (cd "$REPO" && /bin/bash "$TRACKER")
  [ "$(jq -r '.last_edit' "$STATE")" != "0" ]
}

@test "tracker: a docs-only Edit does NOT stamp last_edit (no false gate)" {
  printf '{"last_edit":0,"last_test":0,"test_passed":false}\n' > "$STATE"
  jq -cn '{tool_name:"Edit", tool_input:{file_path:"README.md"}}' | (cd "$REPO" && /bin/bash "$TRACKER")
  [ "$(jq -r '.last_edit' "$STATE")" == "0" ]
}

@test "tracker: a config-only Edit (.toml/.json/.yml) does NOT stamp last_edit" {
  for p in pyproject.toml config.json ci.yml notes.txt; do
    printf '{"last_edit":0,"last_test":0,"test_passed":false}\n' > "$STATE"
    jq -cn --arg p "$p" '{tool_name:"Edit", tool_input:{file_path:$p}}' | (cd "$REPO" && /bin/bash "$TRACKER")
    [ "$(jq -r '.last_edit' "$STATE")" == "0" ]
  done
}

@test "tracker: an apply_patch touching a code file stamps last_edit" {
  printf '{"last_edit":0,"last_test":0,"test_passed":false}\n' > "$STATE"
  jq -cn '{tool_name:"apply_patch", tool_input:{input:"*** Update File: src/main.rs\n@@\n-old\n+new\n"}}' | (cd "$REPO" && /bin/bash "$TRACKER")
  [ "$(jq -r '.last_edit' "$STATE")" != "0" ]
}

@test "gate: docs-only edit then push is ALLOWED (regression: no false block)" {
  # A docs edit must not arm the gate. After a docs-only Edit, last_edit stays 0,
  # so the gate's "no edits recorded -> allow" path fires and the push proceeds.
  printf '{"last_edit":0,"last_test":0,"test_passed":false}\n' > "$STATE"
  jq -cn '{tool_name:"Edit", tool_input:{file_path:"docs/guide.md"}}' | (cd "$REPO" && /bin/bash "$TRACKER")
  out="$(jq -cn --arg d "$REPO" '{tool_input:{command:"git push"}, cwd:$d}' | /bin/bash "$GATE" 2>&1)"
  [ -z "$out" ]   # allow == silent exit 0, no deny JSON
}

# --- uncommitted-warn -------------------------------------------------------

@test "warn: dirty tracked tree -> systemMessage" {
  printf 'v1\n' > "$REPO/f.txt"; git -C "$REPO" add f.txt; git -C "$REPO" commit -q -m init
  printf 'v2\n' > "$REPO/f.txt"   # tracked, uncommitted
  out="$(jq -cn '{stop_hook_active:false}' | (cd "$REPO" && /bin/bash "$WARN") 2>&1)"
  printf '%s' "$out" | jq -e '.systemMessage | test("Uncommitted")' >/dev/null
}

@test "warn: clean tree -> no output" {
  printf 'v1\n' > "$REPO/f.txt"; git -C "$REPO" add f.txt; git -C "$REPO" commit -q -m init
  out="$(jq -cn '{stop_hook_active:false}' | (cd "$REPO" && /bin/bash "$WARN") 2>&1)"
  [ -z "$out" ]
}

@test "warn: commits ahead of upstream -> systemMessage" {
  BARE="$(mktemp -d "${BATS_TEST_TMPDIR}/bare.XXXXXX")"; git init -q --bare "$BARE"
  printf 'v1\n' > "$REPO/f.txt"; git -C "$REPO" add f.txt; git -C "$REPO" commit -q -m init
  git -C "$REPO" remote add origin "$BARE"
  git -C "$REPO" push -q -u origin HEAD
  printf 'v2\n' > "$REPO/f.txt"; git -C "$REPO" add f.txt; git -C "$REPO" commit -q -m ahead
  out="$(jq -cn '{stop_hook_active:false}' | (cd "$REPO" && /bin/bash "$WARN") 2>&1)"
  printf '%s' "$out" | jq -e '.systemMessage | test("Unpushed")' >/dev/null
}

@test "warn: pushed and clean -> no output" {
  BARE="$(mktemp -d "${BATS_TEST_TMPDIR}/bare.XXXXXX")"; git init -q --bare "$BARE"
  printf 'v1\n' > "$REPO/f.txt"; git -C "$REPO" add f.txt; git -C "$REPO" commit -q -m init
  git -C "$REPO" remote add origin "$BARE"
  git -C "$REPO" push -q -u origin HEAD
  out="$(jq -cn '{stop_hook_active:false}' | (cd "$REPO" && /bin/bash "$WARN") 2>&1)"
  [ -z "$out" ]
}
