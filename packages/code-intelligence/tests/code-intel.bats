#!/usr/bin/env bats
# Tests for the code-intelligence hook scripts.
# Portability floor: bash 3.2.57 + BSD coreutils (stock macOS).
# Run with: bats packages/code-intelligence/tests/code-intel.bats

setup() {
  SCRIPTS="${BATS_TEST_DIRNAME}/../scripts"
  SUBAGENT="${SCRIPTS}/subagent-context-inject.sh"

  TESTDIR="$(mktemp -d "${BATS_TMPDIR:-/tmp}/code-intel.XXXXXX")"

  RUNTIME="${TESTDIR}/runtime"
  mkdir -p "$RUNTIME"

  # A git stub whose repo root contains a backslash and a double quote --
  # the exact adversarial path that broke the old sed/tr JSON escaping.
  STUBBIN="${TESTDIR}/bin"
  mkdir -p "$STUBBIN"
  cat >"${STUBBIN}/git" <<'STUB'
#!/usr/bin/env bash
case "$*" in
  *"rev-parse --show-toplevel"*) printf '%s\n' '/tmp/re\po"odd' ;;
  *"branch --show-current"*) printf '%s\n' 'feat/x"y' ;;
  *"symbolic-ref"*) exit 1 ;;
  *"diff --name-only"*) printf 'a.txt\nb.txt\n' ;;
  *) exit 0 ;;
esac
STUB
  chmod +x "${STUBBIN}/git"
}

teardown() {
  rm -rf "$TESTDIR"
}

# ---------------------------------------------------------------------------
# subagent-context-inject.sh
# ---------------------------------------------------------------------------

@test "subagent-inject: backslash + quote repo name yields valid JSON" {
  run env PATH="${STUBBIN}:${PATH}" bash "$SUBAGENT" <<<'{"agent_id":"a1","agent_type":"speckit-implement-task","cwd":"/whatever"}'
  [ "$status" -eq 0 ]
  # The whole stdout must parse as JSON. The old sed/tr escaping produced
  # invalid JSON for a backslash in the path.
  echo "$output" | jq . >/dev/null
}

@test "subagent-inject: backslash path round-trips through the JSON field" {
  run env PATH="${STUBBIN}:${PATH}" bash "$SUBAGENT" <<<'{"agent_id":"a1","agent_type":"x","cwd":"/whatever"}'
  [ "$status" -eq 0 ]
  ctx="$(echo "$output" | jq -r '.hookSpecificOutput.additionalContext')"
  [[ "$ctx" == *'re\po"odd'* ]]
}

@test "subagent-inject: base block carries project/branch + discovery routing, NOT working-style rules" {
  run env PATH="${STUBBIN}:${PATH}" bash "$SUBAGENT" <<<'{"agent_id":"a1","agent_type":"coder","cwd":"/whatever"}'
  [ "$status" -eq 0 ]
  ctx="$(echo "$output" | jq -r '.hookSpecificOutput.additionalContext')"
  # Project identity + code-discovery routing (this package's own concern)
  echo "$ctx" | grep -q "codebase-memory-mcp" || { echo "no discovery routing"; return 1; }
  # Working-style discipline moved to steering-pragmatic; it MUST NOT appear here.
  for gone in "MANDATORY RULES" "MUST Code economy" "MUST YAGNI" "MUST Comments" "MUST Reports"; do
    if echo "$ctx" | grep -q "$gone"; then echo "working-style leaked back: $gone"; return 1; fi
  done
}

@test "subagent-inject: non-subagent (no agent_id) exits silently" {
  run env PATH="${STUBBIN}:${PATH}" bash "$SUBAGENT" <<<'{"cwd":"/whatever"}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "subagent-inject: malformed/empty stdin does not crash" {
  run env PATH="${STUBBIN}:${PATH}" bash "$SUBAGENT" <<<''
  [ "$status" -eq 0 ]
}
