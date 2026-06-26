#!/usr/bin/env bash
set -euo pipefail

input="$(cat)"
tool="$(printf '%s' "$input" | jq -r '.tool_name // empty' 2>/dev/null || true)"

key="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
state_file="/tmp/codex-test-state-$(echo "$key" | md5 2>/dev/null || echo "$key" | md5sum 2>/dev/null | cut -d' ' -f1).json"
now="$(date +%s)"

if [[ ! -f "$state_file" ]] || ! jq -e type "$state_file" >/dev/null 2>&1; then
  echo '{"last_edit":0,"last_test":0,"test_passed":false}' > "$state_file"
fi

# Edit-type tools stamp last_edit so the pre-commit gate knows code changed
# since the last passing test run.
case "$tool" in
  Edit|Write|MultiEdit|apply_patch)
    jq --argjson now "$now" '.last_edit = $now' \
      "$state_file" > "${state_file}.tmp" && mv "${state_file}.tmp" "$state_file"
    exit 0
    ;;
esac

if [[ "$tool" != "Bash" ]]; then
  exit 0
fi

command="$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"
# ONLY real test runners count. The pre-push gate blocks on test_passed, so a
# build/lint/format command must NOT mark tests as having passed (a green build
# does not mean the suite ran). Previously cargo build / ruff check / cargo
# clippy / pre-commit run were treated as "tests" — dropped.
is_test=false
case "$command" in
  *"cargo test"*|*"cargo nextest"*) is_test=true ;;
  *"pnpm test"*|*"pnpm run test"*|*"npm test"*) is_test=true ;;
  *"pytest"*) is_test=true ;;   # covers python -m pytest / uv run pytest
  *"go test"*) is_test=true ;;
  *"just test"*|*"task test"*) is_test=true ;;
  *"vitest"*|*"jest"*|*"mocha"*) is_test=true ;;
  *"make test"*) is_test=true ;;
esac

if [[ "$is_test" == true ]]; then
  exit_code="$(printf '%s' "$input" | jq -r '.tool_response.exit_code // .tool_response.exitCode // "0"' 2>/dev/null || echo "0")"
  passed=true
  [[ "$exit_code" != "0" ]] && passed=false

  jq --argjson now "$now" --argjson passed "$passed" \
    '.last_test = $now | .test_passed = $passed' \
    "$state_file" > "${state_file}.tmp" && mv "${state_file}.tmp" "$state_file"
fi

exit 0
