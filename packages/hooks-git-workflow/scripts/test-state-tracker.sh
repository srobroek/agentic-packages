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

# Edit-type tools stamp last_edit so the pre-push gate knows code changed since
# the last passing test run. ONLY source-file edits count: editing docs, config,
# or markdown must not arm the gate, or a docs-only change would wall a push that
# no test could possibly cover. We inspect the edited path(s) and stamp only when
# at least one is a code file. apply_patch carries no discrete path, so its patch
# body is scanned for code-file markers instead.
case "$tool" in
  Edit|Write|MultiEdit|apply_patch)
    # Collect every path-like field the edit tools expose (Claude: file_path /
    # edits[].file_path / notebook_path; apply_patch: the patch/command body).
    paths="$(printf '%s' "$input" | jq -r '
      [
        .tool_input.file_path?,
        .tool_input.path?,
        .tool_input.notebook_path?,
        .tool_input.edits[]?.file_path?,
        .tool_input.input?,
        .tool_input.command?,
        .tool_input.patch?
      ]
      | map(select(type == "string")) | .[]
    ' 2>/dev/null || true)"

    # Source extensions that mean "tests could be affected". Mirrors the code
    # regex used by coder-delegation-reminder.sh. Docs/config (.md/.toml/.json/
    # .yml/.txt/...) are intentionally excluded so they never arm the gate.
    code_ext_regex='\.(ts|tsx|js|jsx|mjs|cjs|py|go|rs|java|kt|rb|php|cs|swift|c|cc|cpp|h|hpp|sh|bash|zsh|fish|lua|ex|exs|erl|clj|scala|sql|vue|svelte|css|scss)(\b|$)'

    # No path info at all (unusual) -> fail safe by stamping (old behavior).
    if [[ -z "$paths" ]] || printf '%s' "$paths" | grep -Eiq "$code_ext_regex"; then
      jq --argjson now "$now" '.last_edit = $now' \
        "$state_file" > "${state_file}.tmp" && mv "${state_file}.tmp" "$state_file"
    fi
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
