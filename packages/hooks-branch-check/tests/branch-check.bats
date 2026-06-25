#!/usr/bin/env bats
#
# Tests for branch-check.sh (UserPromptSubmit advisory hook).
# Contract: never blocks; exits 0 always. On a protected branch (main/master)
# it emits a JSON object whose hookSpecificOutput.additionalContext lists the
# current branch, existing feature branches, and linked worktrees. On any other
# branch, detached HEAD, or outside a git repo it emits nothing and exits 0.

setup() {
  HOOK="${BATS_TEST_DIRNAME}/../scripts/branch-check.sh"
  REPO="$(mktemp -d "${BATS_TMPDIR:-/tmp}/bc-repo.XXXXXX")"
  git -C "$REPO" init -q -b main
  git -C "$REPO" config user.email test@example.com
  git -C "$REPO" config user.name "Test User"
  git -C "$REPO" commit -q --allow-empty -m "init"
}

teardown() {
  # Clean up any linked worktrees first, then the repo.
  if [ -n "${WORKTREE:-}" ] && [ -d "$WORKTREE" ]; then
    git -C "$REPO" worktree remove --force "$WORKTREE" 2>/dev/null || true
    rm -rf "$WORKTREE"
  fi
  [ -n "${REPO:-}" ] && rm -rf "$REPO"
}

# Run the hook from inside $dir with the given stdin payload.
run_hook() {
  local dir="$1" payload="$2"
  ( cd "$dir" && printf '%s' "$payload" | /bin/bash "$HOOK" )
}

@test "on main: injects branch facts (current branch + feature branches)" {
  git -C "$REPO" branch feat/alpha
  git -C "$REPO" branch fix/beta
  run run_hook "$REPO" '{"prompt":"add a new endpoint to the api"}'
  [ "$status" -eq 0 ]
  [ -n "$output" ]
  # Valid JSON with the correct hook event name.
  event="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.hookEventName')"
  [ "$event" = "UserPromptSubmit" ]
  # No permission decision — advisory only, never blocks.
  decision="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.permissionDecision // "none"')"
  [ "$decision" = "none" ]
  ctx="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.additionalContext')"
  echo "$ctx" | grep -q "protected branch 'main'"
  echo "$ctx" | grep -q "feat/alpha"
  echo "$ctx" | grep -q "fix/beta"
}

@test "on master: also treated as protected" {
  git -C "$REPO" branch -m main master
  run run_hook "$REPO" '{"prompt":"do some work here please"}'
  [ "$status" -eq 0 ]
  ctx="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.additionalContext')"
  echo "$ctx" | grep -q "protected branch 'master'"
}

@test "on main with no feature branches: reports (none)" {
  run run_hook "$REPO" '{"prompt":"some prompt text"}'
  [ "$status" -eq 0 ]
  ctx="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.additionalContext')"
  echo "$ctx" | grep -q "Existing feature branches: (none)"
}

@test "on feature branch: no nag, exit 0, no output" {
  git -C "$REPO" checkout -q -b feat/work
  run run_hook "$REPO" '{"prompt":"add a new endpoint to the api"}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "detached HEAD: clean exit 0, no empty-branch context" {
  sha="$(git -C "$REPO" rev-parse HEAD)"
  git -C "$REPO" checkout -q "$sha"
  run run_hook "$REPO" '{"prompt":"this is a reasonably long prompt"}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "non-git directory: clean exit 0, no output" {
  NONGIT="$(mktemp -d "${BATS_TMPDIR:-/tmp}/bc-nogit.XXXXXX")"
  run run_hook "$NONGIT" '{"prompt":"do something useful"}'
  rm -rf "$NONGIT"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "linked feature worktree on main: listed; current worktree excluded" {
  git -C "$REPO" branch feat/sidecar
  WORKTREE="$(mktemp -d "${BATS_TMPDIR:-/tmp}/bc-wt.XXXXXX")"
  rmdir "$WORKTREE"
  git -C "$REPO" worktree add -q "$WORKTREE" feat/sidecar
  run run_hook "$REPO" '{"prompt":"work on the thing"}'
  [ "$status" -eq 0 ]
  ctx="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.additionalContext')"
  echo "$ctx" | grep -q "feat/sidecar"
  # The current (main) worktree must not appear under Linked worktrees.
  worktree_section="$(printf '%s' "$ctx" | awk '/Linked worktrees:/{p=1;next} /^If this prompt/{p=0} p')"
  ! printf '%s' "$worktree_section" | grep -q "main ("
}

@test "malformed stdin (not JSON): still exits 0 with facts on main" {
  run run_hook "$REPO" 'this is not json at all }{'
  [ "$status" -eq 0 ]
  # Hook ignores stdin entirely, so it must still emit context on main.
  ctx="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.additionalContext')"
  echo "$ctx" | grep -q "protected branch 'main'"
}

@test "string-form tool_input payload: ignored, still exits 0 on main" {
  run run_hook "$REPO" '{"tool_input":"rm -rf /"}'
  [ "$status" -eq 0 ]
  ctx="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.additionalContext')"
  echo "$ctx" | grep -q "protected branch 'main'"
}

@test "empty stdin: exits 0 (facts on main, nothing off-branch)" {
  run run_hook "$REPO" ''
  [ "$status" -eq 0 ]
  ctx="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.additionalContext')"
  echo "$ctx" | grep -q "protected branch 'main'"
}

@test "empty git repo (no commits) on main: exits 0 cleanly" {
  EMPTY="$(mktemp -d "${BATS_TMPDIR:-/tmp}/bc-empty.XXXXXX")"
  git -C "$EMPTY" init -q -b main
  # No commits yet. Depending on git version, --show-current may print the
  # unborn branch ("main") or nothing. Either way the hook must exit 0 without
  # error; if it sees "main" it emits facts, if it sees "" it stays silent.
  cur="$(git -C "$EMPTY" branch --show-current 2>/dev/null || true)"
  run run_hook "$EMPTY" '{"prompt":"start building the feature"}'
  rm -rf "$EMPTY"
  [ "$status" -eq 0 ]
  if [ -z "$cur" ]; then
    # Empty/detached: no context at all.
    [ -z "$output" ]
  else
    # Unborn "main": still protected -> facts emitted, no feature branches.
    ctx="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.additionalContext')"
    echo "$ctx" | grep -q "Existing feature branches: (none)"
  fi
}

@test "output is valid JSON when emitted on main" {
  run run_hook "$REPO" '{"prompt":"build a feature"}'
  [ "$status" -eq 0 ]
  printf '%s' "$output" | jq -e . >/dev/null
}
