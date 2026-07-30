#!/usr/bin/env bats

# A bare `[[ ... ]]` that is not the LAST command in a bats test does not fail
# the test: bash 3.2 does not apply errexit to it there. Every assertion below a
# final one was therefore vacuous, which hid a real behaviour change in this very
# suite. These helpers are function calls, and a failing function call does
# propagate, so each assertion is load-bearing wherever it appears.
has() {
  if [[ "$1" != *"$2"* ]]; then
    printf 'expected output to contain %s\nactual: %s\n' "$2" "$1" >&2
    return 1
  fi
}

lacks() {
  if [[ "$1" == *"$2"* ]]; then
    printf 'expected output NOT to contain %s\nactual: %s\n' "$2" "$1" >&2
    return 1
  fi
}

empty() {
  if [ -n "$1" ]; then
    printf 'expected no output\nactual: %s\n' "$1" >&2
    return 1
  fi
}

setup() {
  export PACKAGE_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
  export GUARD="$PACKAGE_ROOT/scripts/pr-create-guard.py"
  export TEST_REPO="$BATS_TEST_TMPDIR/repo"
  export OUTSIDE_REPO="$BATS_TEST_TMPDIR/outside"
  mkdir -p "$TEST_REPO/.beads" "$OUTSIDE_REPO"
}

@test "blocks a non-draft PR" {
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" \
    --arg command 'gh pr create --title x --body y' \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [ "$status" -eq 0 ]
  has "$output" 'permissionDecisionReason'
  has "$output" 'must start as drafts'
}

@test "allows a draft PR" {
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" \
    --arg command 'gh pr create --draft --title x --body y' \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [ "$status" -eq 0 ]
  empty "$output"
}

@test "allows native draft flag equivalents" {
  for command in \
    'gh pr create -d --body y' \
    'gh pr create --draft=true --body y' \
    'gh pr create -d=true --body y' \
    'gh pr create --draft=1 --body y' \
    'gh pr create -d=t --body y'; do
    export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" --arg command "$command" \
      '{cwd:$cwd,tool_input:{command:$command}}')"
    run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
    empty "$output"
  done
}

@test "blocks an explicitly false draft flag" {
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" \
    --arg command 'gh pr create --draft=false --body y' \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  has "$output" 'must start as drafts'
}

@test "uses last draft flag value" {
  for command in \
    'gh pr create --draft --draft=false --body y' \
    'gh pr create -d --draft=false --body y'; do
    export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" --arg command "$command" \
      '{cwd:$cwd,tool_input:{command:$command}}')"
    run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
    has "$output" 'must start as drafts'
  done
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" \
    --arg command 'gh pr create --draft=false --draft --body y' \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  empty "$output"
}

@test "blocks an absolute-path gh invocation without draft" {
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" \
    --arg command '/usr/bin/gh pr create --title x --body y' \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  has "$output" 'must start as drafts'
}

@test "blocks gh repo-global option forms without draft" {
  for command in \
    'gh -R owner/repo pr create --body y' \
    'gh -Rowner/repo pr create --body y' \
    'gh --repo owner/repo pr create --body y' \
    'gh --repo=owner/repo pr create --body y'; do
    export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" --arg command "$command" \
      '{cwd:$cwd,tool_input:{command:$command}}')"
    run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
    has "$output" 'must start as drafts'
  done
}

@test "blocks wrapped PR creation without draft" {
  for command in \
    'env -i gh pr create --body y' \
    "env -S 'gh pr create --body y'" \
    "env -S'gh pr create --body y'" \
    "timeout 5 env -S'gh pr create --body y'" \
    "sudo env -S'gh pr create --body y'" \
    "command env -S'gh pr create --body y'" \
    "nice env -S'gh pr create --body y'" \
    "env -i env -S'gh pr create --body y'" \
    'command -- gh pr create --body y' \
    'exec gh pr create --body y' \
    'timeout 5 gh pr create --body y' \
    'nice gh pr create --body y' \
    'sudo gh pr create --body y'; do
    export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" --arg command "$command" \
      '{cwd:$cwd,tool_input:{command:$command}}')"
    run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
    has "$output" 'must start as drafts'
  done
}

@test "allows command lookup without treating it as execution" {
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" \
    --arg command 'command -v gh pr create' \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  empty "$output"
}

@test "blocks nested shell PR creation without draft" {
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" \
    --arg command "bash -lc 'gh pr create --title x --body y'" \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  has "$output" 'must start as drafts'
}

@test "checks every PR create invocation independently" {
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" \
    --arg command 'gh pr create --draft --body one; gh pr create --body two' \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  has "$output" 'must start as drafts'
}

@test "accepts Codex bare-string payload while enforcing draft" {
  export HOOK_PAYLOAD='gh pr create --body one'
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  has "$output" 'must start as drafts'
}

@test "allows a quoted documentation mention of gh pr create" {
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" \
    --arg command 'printf "%s" "use gh pr create --draft"' \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [ "$status" -eq 0 ]
  empty "$output"
}

@test "blocks a later grouped non-draft invocation" {
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" \
    --arg command '(gh pr create --draft --body x); gh pr create --body y' \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  has "$output" 'must start as drafts'
}

@test "allows gh words passed as ordinary command arguments" {
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" \
    --arg command 'printf "%s\n" gh pr create' \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  empty "$output"
}

@test "allows gh words in a shell comment" {
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" \
    --arg command 'echo ok # gh pr create' \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  empty "$output"
}

@test "allows nested-shell text passed to echo" {
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" \
    --arg command "echo bash -lc 'gh pr create --body x'" \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  empty "$output"
}

# --- an inconclusive check must not deny -------------------------------------
#
# This used to deny. A guard that blocks whenever it cannot reach a verdict turns
# every parser gap into a rejected PR.

@test "allows with an advisory when the command cannot be parsed" {
  # An apostrophe in the body defeats shell tokenizing, and PR bodies are
  # markdown, so this is the ordinary case rather than an edge one.
  command="gh pr create --draft --title t --body 'it"
  command="${command}'"
  command="${command}s got an apostrophe'"
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" --arg command "$command" \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [ "$status" -eq 0 ]
  has "$output" '"allow"'
  has "$output" 'could not be parsed'
  lacks "$output" '"deny"'
}

# --- a body is never inspected -----------------------------------------------
#
# The guard is PreToolUse, so a body file the same command is about to write does
# not exist yet. Reading it denied a correct compound command and blamed the
# file, which is readable a millisecond later.

@test "allows a compound command that writes its own body file" {
  command="printf x > $TEST_REPO/b.md && gh pr create --draft --body-file $TEST_REPO/b.md --title t"
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$TEST_REPO" --arg command "$command" \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [ "$status" -eq 0 ]
  empty "$output"
  lacks "$output" 'body file'
}

@test "allows an implicit body" {
  # --fill and an editor body were denied as unverifiable. Neither is a policy
  # breach.
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$TEST_REPO" \
    --arg command 'gh pr create --draft --fill' \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  empty "$output"
}

# --- a beads repository is not a trigger -------------------------------------

@test "says nothing about beads in a beads repository" {
  command=$'gh pr create --body "## Summary\nno trailers here"'
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$TEST_REPO" --arg command "$command" \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  has "$output" '"deny"'
  has "$output" 'must start as drafts'
  lacks "$output" 'Bead'
}

@test "allows a draft PR in a beads repository with no trailers" {
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$TEST_REPO" \
    --arg command 'gh pr create --draft --title x --body y' \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [ "$status" -eq 0 ]
  empty "$output"
}
