#!/usr/bin/env bash
set -euo pipefail

# pre-push-test-gate.sh — PreToolUse:Bash hook (Claude + Codex).
#
# Enforce that the agent has run its unit tests, green, before pushing. The hook
# does NOT run the tests itself (that would put a slow suite on the push path);
# it reads the edit/test state recorded by test-state-tracker.sh and BLOCKS the
# push when tests are stale or red, telling the agent to run them. Agents commit
# constantly but push rarely, so the test gate belongs at push, not commit.
#
# Decision:
#   - no `git push` command            -> allow (not our concern)
#   - SKIP_TEST_GATE=1 (env or inline)  -> allow (documented bypass)
#   - no detectable test command        -> WARN + allow (tooling gap, never wedge)
#   - tests ran, green, since last edit -> allow
#   - tests stale (edited after last run) or last run FAILED -> DENY with guidance
#
# State source: /tmp/codex-test-state-<repohash>.json written by
# test-state-tracker.sh ({last_edit,last_test,test_passed}). Same-session only —
# this is client-side enforcement (the state lives in the agent session); a
# fresh clone / other tool has no state and is handled by the no-state path.
#
# Portability floor: bash 3.2.57 + BSD userland.

input="$(cat 2>/dev/null || true)"
command -v jq >/dev/null 2>&1 || exit 0

command="$(printf '%s' "$input" | jq -r 'if (.tool_input|type)=="string" then .tool_input else (.tool_input.command // empty) end' 2>/dev/null || true)"
[[ -z "$command" || "$command" == "null" ]] && exit 0

# Only gate a real `git push`, anchored to command position (not a push string
# inside some other command's argument).
printf '%s' "$command" | grep -Eq '(^|[;&|][[:space:]]*)git([[:space:]][^;&|]*)?[[:space:]]+push($|[[:space:]])' || exit 0

# Documented bypass: env var, or inline `SKIP_TEST_GATE=1 git push ...`.
[[ "${SKIP_TEST_GATE:-}" == "1" ]] && exit 0
printf '%s' "$command" | grep -Eq '(^|[[:space:]])SKIP_TEST_GATE=1([[:space:]]|$)' && exit 0

cwd="$(printf '%s' "$input" | jq -r '.cwd // empty' 2>/dev/null || true)"
[[ -n "$cwd" && "$cwd" != "null" && -d "$cwd" ]] || cwd="$PWD"
repo_root="$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null || true)"
[[ -n "$repo_root" ]] || exit 0
cd "$repo_root"

deny() {
  jq -cn --arg reason "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}'
  exit 0
}
warn() {
  jq -cn --arg ctx "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow",additionalContext:$ctx}}'
  exit 0
}

# Detect the project's unit-test command (used only to NAME it in the message;
# the agent runs it, the hook never does).
test_cmd=""
if [[ -f "Cargo.toml" ]]; then
  test_cmd="cargo test"
elif [[ -f "package.json" ]]; then
  test_cmd="pnpm test"
elif [[ -f "pyproject.toml" ]]; then
  test_cmd="pytest"
elif [[ -f "go.mod" ]]; then
  test_cmd="go test ./..."
elif [[ -f "justfile" ]] && grep -q '^test:' justfile 2>/dev/null; then
  test_cmd="just test"
fi

# No detectable test command -> tooling gap, not a failure. Warn and allow.
if [[ -z "$test_cmd" ]]; then
  warn "PUSH TEST GATE: no unit-test command detected for this project; pushing without a test check. Add a test runner (cargo/pytest/go test/pnpm test/just test) to enable the gate."
fi

key="$repo_root"
# MUST match test-state-tracker.sh's path calc exactly (it uses `echo`, which
# appends a newline before hashing — so we do too, or the gate reads a different
# file than the tracker wrote).
state_file="/tmp/codex-test-state-$(echo "$key" | md5 2>/dev/null || echo "$key" | md5sum 2>/dev/null | cut -d' ' -f1).json"

# No state recorded this session -> we cannot confirm tests ran. Per "minimal
# impediment + never wedge on missing signal", WARN and allow rather than block
# (a fresh clone or a session that never edited code should not be walled).
if [[ ! -f "$state_file" ]] || ! jq -e type "$state_file" >/dev/null 2>&1; then
  warn "PUSH TEST GATE: no test run recorded this session. If you changed code, run your unit tests ($test_cmd) and confirm they pass before pushing."
fi

last_edit="$(jq -r '.last_edit // 0' "$state_file" 2>/dev/null || echo 0)"
last_test="$(jq -r '.last_test // 0' "$state_file" 2>/dev/null || echo 0)"
test_passed="$(jq -r '.test_passed // false' "$state_file" 2>/dev/null || echo false)"
[[ "$last_edit" =~ ^[0-9]+$ ]] || last_edit=0
[[ "$last_test" =~ ^[0-9]+$ ]] || last_test=0

# No edits recorded -> nothing changed to test -> allow.
[[ "$last_edit" == "0" ]] && exit 0

# Tests never ran, but code was edited -> block: run them first.
if [[ "$last_test" == "0" ]]; then
  deny "Refusing git push: code was edited but unit tests have not been run this session. Run '$test_cmd' and ensure it passes, then push (bypass with SKIP_TEST_GATE=1 if you accept the risk)."
fi

# Code edited after the last test run -> the green result is stale -> block.
if [[ "$last_test" -lt "$last_edit" ]]; then
  deny "Refusing git push: source was edited after the last unit-test run, so the tests are stale. Re-run '$test_cmd' and ensure it passes before pushing (bypass: SKIP_TEST_GATE=1)."
fi

# Last test run failed -> block.
if [[ "$test_passed" != "true" ]]; then
  deny "Refusing git push: the last unit-test run failed. Fix the tests ('$test_cmd') and get them green before pushing (bypass: SKIP_TEST_GATE=1)."
fi

# Tests ran green, after the last edit -> allow.
exit 0
