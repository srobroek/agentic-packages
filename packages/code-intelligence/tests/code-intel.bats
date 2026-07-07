#!/usr/bin/env bats
# Tests for the code-intelligence hook scripts.
# Portability floor: bash 3.2.57 + BSD coreutils (stock macOS).
# Run with: bats packages/code-intelligence/tests/code-intel.bats

setup() {
  SCRIPTS="${BATS_TEST_DIRNAME}/../scripts"
  SUBAGENT="${SCRIPTS}/subagent-context-inject.sh"
  REINDEX="${SCRIPTS}/reindex-after-commit.sh"

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

@test "subagent-inject: non-subagent (no agent_id) exits silently" {
  run env PATH="${STUBBIN}:${PATH}" bash "$SUBAGENT" <<<'{"cwd":"/whatever"}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "subagent-inject: malformed/empty stdin does not crash" {
  run env PATH="${STUBBIN}:${PATH}" bash "$SUBAGENT" <<<''
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------

@test "reindex: subagent payload (agent_id present) exits without indexing" {
  run env PATH="${STUBBIN}:${PATH}" bash "$REINDEX" <<<'{"agent_id":"sub-1","cwd":"/whatever"}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "reindex: jq builds a valid JSON arg for a backslash repo path" {
  # Mirror the exact idiom the script uses to confirm valid encoding.
  repo='/tmp/re\po"odd'
  arg="$(jq -nc --arg p "$repo" '{repo_path:$p,mode:"fast"}')"
  echo "$arg" | jq . >/dev/null
  got="$(echo "$arg" | jq -r '.repo_path')"
  [ "$got" = "$repo" ]
}

@test "reindex: empty stdin does not crash" {
  run bash "$REINDEX" <<<''
  [ "$status" -eq 0 ]
}
