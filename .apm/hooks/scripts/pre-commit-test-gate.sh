#!/usr/bin/env bash
set -euo pipefail

input="$(cat)"
command="$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"
[[ -z "$command" ]] && exit 0

printf '%s' "$command" | grep -qE '^git commit\b' || exit 0

if printf '%s' "$command" | grep -qiE '\[skip.tests\]|\[no.tests\]'; then
  exit 0
fi

[[ "${SKIP_TEST_GATE:-}" == "1" ]] && exit 0

key="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
state_file="/tmp/codex-test-state-$(echo "$key" | md5 2>/dev/null || echo "$key" | md5sum 2>/dev/null | cut -d' ' -f1).json"

[[ -f "$state_file" ]] || exit 0
if ! jq -e type "$state_file" >/dev/null 2>&1; then
  exit 0
fi

last_edit="$(jq -r '.last_edit // 0' "$state_file" 2>/dev/null || echo "0")"
last_test="$(jq -r '.last_test // 0' "$state_file" 2>/dev/null || echo "0")"
test_passed="$(jq -r '.test_passed // false' "$state_file" 2>/dev/null || echo "false")"

[[ "$last_edit" == "0" ]] && exit 0

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

suggest=""
[[ -n "$test_cmd" ]] && suggest=" Suggested: $test_cmd"

if [[ "$last_test" -lt "$last_edit" ]]; then
  jq -n --arg msg "Tests must pass before committing. Source files were edited after last test run (or no tests run).${suggest}" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: $msg
    }
  }'
  exit 0
fi

if [[ "$test_passed" == "false" ]]; then
  jq -n --arg msg "Last test run failed. Fix tests before committing.${suggest}" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: $msg
    }
  }'
fi

exit 0
