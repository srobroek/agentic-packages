#!/usr/bin/env bats

setup() {
  export PACKAGE_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
  export GUARD="$PACKAGE_ROOT/scripts/pr-create-guard.py"
  export TEST_REPO="$BATS_TEST_TMPDIR/repo"
  export OUTSIDE_REPO="$BATS_TEST_TMPDIR/outside"
  export FAKE_BIN="$BATS_TEST_TMPDIR/bin"
  mkdir -p "$TEST_REPO/.beads" "$OUTSIDE_REPO" "$FAKE_BIN"
  printf '%s\n' \
    '#!/usr/bin/env bash' \
    'case " $* " in' \
    '  *" show merge-1 --json "*) printf '\''%s\n'\'' '\''[{"id":"merge-1","status":"open","issue_type":"task","labels":["pr:merge","agent:integrator"],"metadata":{"branch":"fix/test","repo":"owner/repo","origin_actor":"test/agent","tracks_beads":["good-1"],"closes_beads":["good-1"]}}]'\'' ;;' \
    '  *" show merge-2 --json "*) printf '\''%s\n'\'' '\''[{"id":"merge-2","status":"open","issue_type":"task","labels":["pr:merge","agent:integrator"],"metadata":{"branch":"fix/test","repo":"owner/repo","origin_actor":"test/agent","tracks_beads":["good-1"],"closes_beads":[]}}]'\'' ;;' \
    '  *" show merge-blocked --json "*) printf '\''%s\n'\'' '\''[{"id":"merge-blocked","status":"blocked","labels":["pr:merge","agent:integrator"],"metadata":{"branch":"fix/test","repo":"owner/repo","origin_actor":"test/agent","tracks_beads":["good-1"],"closes_beads":[]}}]'\'' ;;' \
    '  *" show merge-unrouted --json "*) printf '\''%s\n'\'' '\''[{"id":"merge-unrouted","status":"open","labels":["pr:merge"],"metadata":{"branch":"fix/test","repo":"owner/repo","origin_actor":"test/agent","tracks_beads":["good-1"],"closes_beads":[]}}]'\'' ;;' \
    '  *" show merge-unanchored --json "*) printf '\''%s\n'\'' '\''[{"id":"merge-unanchored","status":"open","labels":["pr:merge","agent:integrator"],"metadata":{"tracks_beads":["good-1"],"closes_beads":[]}}]'\'' ;;' \
    '  *" show merge-assigned --json "*) printf '\''%s\n'\'' '\''[{"id":"merge-assigned","status":"open","assignee":"busy-agent","labels":["pr:merge","agent:integrator"],"metadata":{"branch":"fix/test","repo":"owner/repo","origin_actor":"test/agent","tracks_beads":["good-1"],"closes_beads":[]}}]'\'' ;;' \
    '  *" show good-1 --json "*) printf '\''%s\n'\'' '\''[{"id":"good-1","status":"open","labels":[],"dependencies":[{"id":"merge-1","dependency_type":"blocks"}]}]'\'' ;;' \
    '  *" show other-1 --json "*) printf '\''%s\n'\'' '\''[{"id":"other-1","status":"open","labels":[],"dependencies":[]}]'\'' ;;' \
    '  *" show "*) exit 1 ;;' \
    '  *" where "*)' \
    '    dir="$PWD"' \
    '    while [ "$2" = "-C" ] || [ "$1" = "-C" ]; do' \
    '      if [ "$1" = "-C" ]; then dir="$2"; shift 2; else shift; fi' \
    '    done' \
    '    [ -d "$dir/.beads" ] && exit 0' \
    '    exit 1 ;;' \
    'esac' > "$FAKE_BIN/bd"
  chmod +x "$FAKE_BIN/bd"
  export PATH="$FAKE_BIN:$PATH"
}

@test "blocks a non-draft PR outside Beads" {
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" \
    --arg command 'gh pr create --title x --body y' \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [ "$status" -eq 0 ]
  [[ "$output" == *'permissionDecisionReason'* ]]
  [[ "$output" == *'must start as drafts'* ]]
}

@test "allows a draft PR without Beads linkage outside Beads" {
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" \
    --arg command 'gh pr create --draft --title x --body y' \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "allows native draft flag equivalents outside Beads" {
  for command in \
    'gh pr create -d --body y' \
    'gh pr create --draft=true --body y' \
    'gh pr create -d=true --body y' \
    'gh pr create --draft=1 --body y' \
    'gh pr create -d=t --body y'; do
    export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" --arg command "$command" \
      '{cwd:$cwd,tool_input:{command:$command}}')"
    run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
    [ -z "$output" ]
  done
}

@test "blocks an explicitly false draft flag" {
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" \
    --arg command 'gh pr create --draft=false --body y' \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [[ "$output" == *'must start as drafts'* ]]
}

@test "uses last draft flag value" {
  for command in \
    'gh pr create --draft --draft=false --body y' \
    'gh pr create -d --draft=false --body y'; do
    export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" --arg command "$command" \
      '{cwd:$cwd,tool_input:{command:$command}}')"
    run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
    [[ "$output" == *'must start as drafts'* ]]
  done
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" \
    --arg command 'gh pr create --draft=false --draft --body y' \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [ -z "$output" ]
}

@test "blocks a Beads PR without a tracking trailer" {
  export FAKE_BD_WHERE=ok
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$TEST_REPO" \
    --arg command 'gh pr create --draft --title x --body "## Summary"' \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [[ "$output" == *'Tracks-Bead: <id>'* ]]
}

@test "allows a multiline inline body with a resolvable tracking trailer" {
  export FAKE_BD_WHERE=ok
  command=$'gh pr create --draft --title x --body "## Summary\nReady\n\n## Beads\nMerge-Bead: merge-1\nTracks-Bead: good-1\nCloses-Bead: good-1"'
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$TEST_REPO" --arg command "$command" \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "blocks an unknown tracking bead" {
  export FAKE_BD_WHERE=ok
  command=$'gh pr create --draft --body "## Beads\nMerge-Bead: merge-1\nTracks-Bead: missing-1"'
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$TEST_REPO" --arg command "$command" \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [[ "$output" == *"not resolvable"* ]]
}

@test "blocks a Beads PR without exactly one merge bead" {
  command=$'gh pr create --draft --body "## Beads\nTracks-Bead: good-1"'
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$TEST_REPO" --arg command "$command" \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [[ "$output" == *'exactly one Merge-Bead'* ]]
}

@test "blocks a closing bead that is not also tracked" {
  export FAKE_BD_WHERE=ok
  command=$'gh pr create --draft --body "## Beads\nMerge-Bead: merge-1\nTracks-Bead: good-1\nCloses-Bead: other-1"'
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$TEST_REPO" --arg command "$command" \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [[ "$output" == *"must also appear as Tracks-Bead"* ]]
}

@test "allows a linked body file" {
  export FAKE_BD_WHERE=ok
  printf '%s\n' '## Beads' 'Merge-Bead: merge-2' 'Tracks-Bead: good-1' > "$TEST_REPO/pr-body.md"
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$TEST_REPO" \
    --arg command 'gh pr create --draft --body-file pr-body.md' \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "ignores a beads directory in a shared ancestor" {
  local nested="$OUTSIDE_REPO/nested"
  mkdir -p "$OUTSIDE_REPO/.beads" "$nested"
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$nested" \
    --arg command 'gh pr create --draft --title x' \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [ -z "$output" ]
}

@test "resolves beads against the directory a cd prefix selects" {
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" \
    --arg command "cd $TEST_REPO && gh pr create --draft --title x" \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [[ "$output" == *'Tracks-Bead'* ]]
}

@test "keeps session cwd when a cd prefix is not a plain directory change" {
  for command in \
    "cd $TEST_REPO extra && gh pr create --draft --title x" \
    "cd - && gh pr create --draft --title x" \
    "cd $TEST_REPO/missing && gh pr create --draft --title x"; do
    export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" --arg command "$command" \
      '{cwd:$cwd,tool_input:{command:$command}}')"
    run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
    [ -z "$output" ]
  done
}

@test "blocks an absolute-path gh invocation without draft" {
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" \
    --arg command '/usr/bin/gh pr create --title x --body y' \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [[ "$output" == *'must start as drafts'* ]]
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
    [[ "$output" == *'must start as drafts'* ]]
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
    [[ "$output" == *'must start as drafts'* ]]
  done
}

@test "allows command lookup without treating it as execution" {
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" \
    --arg command 'command -v gh pr create' \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [ -z "$output" ]
}

@test "blocks nested shell PR creation without draft" {
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" \
    --arg command "bash -lc 'gh pr create --title x --body y'" \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [[ "$output" == *'must start as drafts'* ]]
}

@test "checks every PR create invocation independently" {
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" \
    --arg command 'gh pr create --draft --body one; gh pr create --body two' \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [[ "$output" == *'must start as drafts'* ]]
}

@test "accepts Codex bare-string payload while enforcing draft" {
  export HOOK_PAYLOAD='gh pr create --body one'
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [[ "$output" == *'must start as drafts'* ]]
}

@test "allows a quoted documentation mention of gh pr create" {
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" \
    --arg command 'printf "%s" "use gh pr create --draft"' \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "blocks a later grouped non-draft invocation" {
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" \
    --arg command '(gh pr create --draft --body x); gh pr create --body y' \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [[ "$output" == *'must start as drafts'* ]]
}

@test "allows gh words passed as ordinary command arguments" {
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" \
    --arg command 'printf "%s\n" gh pr create' \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [ -z "$output" ]
}

@test "allows gh words in a shell comment" {
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" \
    --arg command 'echo ok # gh pr create' \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [ -z "$output" ]
}

@test "allows nested-shell text passed to echo" {
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$OUTSIDE_REPO" \
    --arg command "echo bash -lc 'gh pr create --body x'" \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [ -z "$output" ]
}

@test "blocks a closing trailer without a predeclared dependency edge" {
  command=$'gh pr create --draft --body "## Beads\nMerge-Bead: merge-1\nTracks-Bead: other-1\nCloses-Bead: other-1"'
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$TEST_REPO" --arg command "$command" \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [[ "$output" == *'must already depend on Merge-Bead'* ]]
}

@test "blocks a merge bead that is not open" {
  command=$'gh pr create --draft --body "## Beads\nMerge-Bead: merge-blocked\nTracks-Bead: good-1"'
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$TEST_REPO" --arg command "$command" \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [[ "$output" == *'must be open'* ]]
}

@test "blocks a merge bead without integrator routing" {
  command=$'gh pr create --draft --body "## Beads\nMerge-Bead: merge-unrouted\nTracks-Bead: good-1"'
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$TEST_REPO" --arg command "$command" \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [[ "$output" == *'agent:integrator'* ]]
}

@test "blocks a merge bead without durable anchors" {
  command=$'gh pr create --draft --body "## Beads\nMerge-Bead: merge-unanchored\nTracks-Bead: good-1"'
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$TEST_REPO" --arg command "$command" \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [[ "$output" == *'branch, repo, and origin_actor'* ]]
}

@test "blocks an assigned merge bead that would starve discovery" {
  command=$'gh pr create --draft --body "## Beads\nMerge-Bead: merge-assigned\nTracks-Bead: good-1"'
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$TEST_REPO" --arg command "$command" \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [[ "$output" == *'must be unassigned'* ]]
}

# --- an inconclusive check must not deny -------------------------------------
#
# Both cases below used to deny. A guard that blocks whenever it cannot reach a
# verdict turns every parser gap and every slow database into a rejected PR.

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
  [[ "$output" == *'"allow"'* ]]
  [[ "$output" == *'could not be parsed'* ]]
  [[ "$output" != *'"deny"'* ]]
}

@test "allows with an advisory when a bead lookup cannot complete" {
  # bd answers `where` (so this is a beads repo) but fails `show` for a reason
  # unrelated to the bead existing. An unhealthy database is not evidence that
  # the bead is missing.
  broken="$BATS_TEST_TMPDIR/broken-bin"
  mkdir -p "$broken"
  {
    printf '%s\n' '#!/usr/bin/env bash'
    printf '%s\n' 'case " $* " in'
    printf '%s\n' '  *" where "*) exit 0 ;;'
    printf '%s\n' '  *" show "*) echo "Error: database is locked" >&2; exit 1 ;;'
    printf '%s\n' 'esac'
    printf '%s\n' 'exit 0'
  } > "$broken/bd"
  chmod +x "$broken/bd"
  command=$'gh pr create --draft --body "## Beads\nMerge-Bead: merge-1\nTracks-Bead: good-1"'
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$TEST_REPO" --arg command "$command" \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run env PATH="$broken:$PATH" bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [ "$status" -eq 0 ]
  [[ "$output" == *'"allow"'* ]]
  [[ "$output" == *'could not complete'* ]]
  [[ "$output" != *'"deny"'* ]]
}

@test "still denies a bead the database reports as unknown" {
  # The counterpart to the case above: an explicit not-found is a real miss and
  # keeps denying, so the hardening does not become a blanket allow.
  missing="$BATS_TEST_TMPDIR/missing-bin"
  mkdir -p "$missing"
  {
    printf '%s\n' '#!/usr/bin/env bash'
    printf '%s\n' 'case " $* " in'
    printf '%s\n' '  *" where "*) exit 0 ;;'
    printf '%s\n' '  *" show "*) echo "no issue found matching id" >&2; exit 1 ;;'
    printf '%s\n' 'esac'
    printf '%s\n' 'exit 0'
  } > "$missing/bd"
  chmod +x "$missing/bd"
  command=$'gh pr create --draft --body "## Beads\nMerge-Bead: merge-1\nTracks-Bead: good-1"'
  export HOOK_PAYLOAD="$(jq -cn --arg cwd "$TEST_REPO" --arg command "$command" \
    '{cwd:$cwd,tool_input:{command:$command}}')"
  run env PATH="$missing:$PATH" bash -c 'printf "%s" "$HOOK_PAYLOAD" | python3 "$GUARD"'
  [ "$status" -eq 0 ]
  [[ "$output" == *'"deny"'* ]]
  [[ "$output" == *'not resolvable'* ]]
}
