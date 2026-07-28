#!/usr/bin/env bats
#
# Coverage for repomix-refresh-snapshot.sh, a PostToolUse:Bash hook that repacks
# a Repomix snapshot after a branch, worktree, or integration event.
#
# Repomix packs a whole snapshot rather than indexing incrementally, so a pack is
# expensive and every gate that suppresses one is load-bearing. These tests are
# therefore mostly about NOT packing: a dirty tree, a failed command, an
# unrelated command, a subagent, an unchanged HEAD, and a concurrent run all have
# to bail. `repomix` is stubbed so a "pack" is observable without running one.
#
# Portability floor: bash 3.2.57 + BSD userland.
# Run: bats packages/mcp-repomix/tests/repomix-refresh-snapshot.bats

setup() {
  HOOK="${BATS_TEST_DIRNAME}/../scripts/repomix-refresh-snapshot.sh"
  command -v jq >/dev/null 2>&1 || skip "jq not available"

  REPO="$BATS_TEST_TMPDIR/repo"
  mkdir -p "$REPO"
  git -C "$REPO" init -q
  git -C "$REPO" config user.email t@example.test
  git -C "$REPO" config user.name t
  git -C "$REPO" config commit.gpgsign false
  # repomix.xml must be gitignored, or the hook declines to write it.
  printf 'repomix.xml\n' >"$REPO/.gitignore"
  printf 'x\n' >"$REPO/file.txt"
  git -C "$REPO" add -A
  git -C "$REPO" commit -qm initial

  # Stub repomix: records that it ran instead of packing.
  STUB="$BATS_TEST_TMPDIR/bin"
  mkdir -p "$STUB"
  RAN="$BATS_TEST_TMPDIR/ran"
  cat >"$STUB/repomix" <<EOF
#!/bin/sh
printf 'packed\n' >>"$RAN"
exit 0
EOF
  chmod +x "$STUB/repomix"
  PATH="$STUB:$PATH"

  # Isolate the snapshot state directory per test.
  export XDG_STATE_HOME="$BATS_TEST_TMPDIR/state"
}

# fire <command> [exit_code] -> runs the hook, waits for its background pack
fire() {
  local code="${2:-0}"
  jq -cn --arg c "$1" --arg d "$REPO" --argjson e "$code" \
    '{cwd:$d,hook_event_name:"PostToolUse",tool_name:"Bash",
      tool_input:{command:$c},tool_response:{exit_code:$e}}' \
    | /bin/bash "$HOOK"
  # The pack is backgrounded; give it a moment to land.
  sleep 1
}

packed() {
  [ -f "$RAN" ]
}

@test "script parses under /bin/bash" {
  run /bin/bash -n "$HOOK"; [ "$status" -eq 0 ]
}

# --- the events that justify a repack ---------------------------------------

@test "a worktree add triggers a pack" {
  # The command string is all the hook inspects; it does not run it. A real
  # `git worktree add` here would add an untracked entry and trip the
  # clean-tree gate, which is a property of the fixture rather than the hook.
  fire 'git worktree add ../elsewhere'
  packed
}

@test "a branch creation triggers a pack" {
  fire 'git switch -c feature/x'
  packed
}

@test "a merge triggers a pack" {
  fire 'git merge origin/main'
  packed
}

# --- the gates that must suppress a pack ------------------------------------

@test "an unrelated command does not pack" {
  fire 'ls -la'
  ! packed
}

@test "a read-only git command does not pack" {
  fire 'git status --short'
  ! packed
}

@test "a failed command does not pack" {
  fire 'git merge origin/main' 1
  ! packed
}

@test "a dirty working tree does not pack" {
  printf 'dirty\n' >>"$REPO/file.txt"
  fire 'git merge origin/main'
  ! packed
}

@test "a subagent invocation does not pack" {
  jq -cn --arg c 'git merge origin/main' --arg d "$REPO" \
    '{cwd:$d,agent_id:"sub-1",tool_name:"Bash",tool_input:{command:$c},
      tool_response:{exit_code:0}}' | /bin/bash "$HOOK"
  sleep 1
  ! packed
}

@test "an unchanged HEAD does not pack twice" {
  fire 'git merge origin/main'
  packed
  rm -f "$RAN"
  fire 'git merge origin/main'
  ! packed
}

@test "a new commit does pack again" {
  fire 'git merge origin/main'
  packed
  rm -f "$RAN"
  printf 'more\n' >>"$REPO/file.txt"
  git -C "$REPO" add -A
  git -C "$REPO" commit -qm second
  fire 'git merge origin/main'
  packed
}

@test "repomix absent -> no pack, exit 0" {
  rm -f "$BATS_TEST_TMPDIR/bin/repomix"
  fire 'git merge origin/main'
  ! packed
}

@test "an untracked repomix.xml that is NOT gitignored does not pack" {
  printf '\n' >"$REPO/.gitignore"
  git -C "$REPO" add -A
  git -C "$REPO" commit -qm "drop the ignore"
  fire 'git merge origin/main'
  ! packed
}

# --- fail open --------------------------------------------------------------

@test "empty payload -> exit 0, no pack" {
  run /bin/bash -c "printf '' | /bin/bash '$HOOK'"
  [ "$status" -eq 0 ]
  ! packed
}

@test "malformed payload -> exit 0, no pack" {
  run /bin/bash -c "printf 'not json {' | /bin/bash '$HOOK'"
  [ "$status" -eq 0 ]
  ! packed
}

@test "the hook emits no decision, being PostToolUse" {
  output="$(jq -cn --arg c 'git merge origin/main' --arg d "$REPO" \
    '{cwd:$d,tool_name:"Bash",tool_input:{command:$c},tool_response:{exit_code:0}}' \
    | /bin/bash "$HOOK" 2>&1)"
  [ -z "$output" ]
}
