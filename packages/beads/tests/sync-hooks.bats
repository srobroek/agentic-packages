#!/usr/bin/env bats
#
# Coverage for the JSONL-over-git sync hooks:
#   - beads-sync-stage.sh    PreToolUse:Bash, refresh + stage on `git commit`
#   - beads-sync-hydrate.sh  SessionStart, Dolt pull first, JSONL fallback
#
# The gating tests matter more than the happy path: these hooks run on every
# Bash call and every session start in every repo, so a missing guard means
# writing bead state into repos that never asked for it.
#
# Portability floor: bash 3.2.57 + BSD userland.
# Run: bats packages/beads/tests/jsonl-git-sync.bats

setup() {
  S="${BATS_TEST_DIRNAME}/../scripts"
  STAGE="$S/beads-sync-stage.sh"
  HYDRATE="$S/beads-sync-hydrate.sh"
  command -v jq >/dev/null 2>&1 || skip "jq not available"

  REPO="$BATS_TEST_TMPDIR/repo"
  mkdir -p "$REPO"
  cd "$REPO" || return 1
  git init -q -b main .
  git config user.email t@t
  git config user.name t
}

# Build a beads workspace in $REPO. Skips the whole test when bd is absent so
# the suite stays green on a machine without it.
init_beads() {
  command -v bd >/dev/null 2>&1 || skip "bd not available"
  # `bd -C` refuses a directory with no project yet ("no beads project found"),
  # so init must run with $REPO as the cwd. setup() already cd'd there.
  # --skip-hooks: never let a test wire global hooks. NOT --stealth, which
  # excludes .beads/ via .git/info/exclude and would make `git add` fail.
  bd init --prefix tb --skip-hooks >/dev/null 2>&1 ||
    bd init --prefix tb >/dev/null 2>&1 ||
    skip "bd init failed"
  bd -C "$REPO" where >/dev/null 2>&1 || skip "no beads workspace"
}

opt_in() { bd -C "$REPO" config set custom.jsonl-git-sync true >/dev/null 2>&1; }

# commit_payload <command> -> PreToolUse JSON for that Bash command
commit_payload() {
  jq -n --arg cwd "$REPO" --arg cmd "$1" \
    '{cwd:$cwd, tool_input:{command:$cmd}}'
}

run_stage() { commit_payload "$1" | /bin/bash "$STAGE"; }
run_hydrate() { jq -n --arg cwd "$REPO" '{cwd:$cwd}' | /bin/bash "$HYDRATE"; }

staged() { git -C "$REPO" diff --cached --name-only; }

# --- parse / portability floor ---------------------------------------------

@test "scripts parse under /bin/bash" {
  run /bin/bash -n "$STAGE"; [ "$status" -eq 0 ]
  run /bin/bash -n "$HYDRATE"; [ "$status" -eq 0 ]
}

# --- fail-open gating -------------------------------------------------------

@test "stage: empty payload exits 0 and writes nothing" {
  run bash -c "printf '' | /bin/bash '$STAGE'"
  [ "$status" -eq 0 ]
  [ ! -f "$REPO/.beads/issues.jsonl" ]
}

@test "hydrate: empty payload exits 0" {
  run bash -c "printf '' | /bin/bash '$HYDRATE'"
  [ "$status" -eq 0 ]
}

@test "stage: no beads workspace is inert" {
  run_stage "git commit -m x"
  [ ! -f "$REPO/.beads/issues.jsonl" ]
}

@test "stage: beads workspace WITHOUT opt-in is inert" {
  init_beads
  bd -C "$REPO" create "a bead" >/dev/null 2>&1
  run_stage "git commit -m x"
  # The whole point of the opt-in: installing the package must not start
  # committing bead state in a repo that syncs via Dolt.
  [ ! -f "$REPO/.beads/issues.jsonl" ]
}

@test "hydrate: beads workspace WITHOUT opt-in is inert" {
  init_beads
  run run_hydrate
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# --- export: command matching ------------------------------------------------

@test "stage: non-commit git command does not stage" {
  init_beads; opt_in
  bd -C "$REPO" create "a bead" >/dev/null 2>&1
  run_stage "git status"
  [ -z "$(staged)" ]
}

@test "stage: 'git commit' inside a quoted string does not stage" {
  init_beads; opt_in
  bd -C "$REPO" create "a bead" >/dev/null 2>&1
  # Quote-stripping guards this: an unrelated command that merely mentions a
  # commit must not rewrite and stage bead state.
  run_stage 'echo "remember to git commit later"'
  [ -z "$(staged)" ]
}

@test "stage: real commit stages the export even when the message says 'git commit'" {
  init_beads; opt_in
  bd -C "$REPO" create "a bead" >/dev/null 2>&1
  run_stage 'git commit -m "docs: explain git commit"'
  [ "$(staged)" = ".beads/issues.jsonl" ]
}

@test "stage: flags between git and commit still match" {
  init_beads; opt_in
  bd -C "$REPO" create "a bead" >/dev/null 2>&1
  run_stage "git -c user.name=x commit -m y"
  [ "$(staged)" = ".beads/issues.jsonl" ]
}

# --- export: content --------------------------------------------------------

@test "stage: written file is valid JSONL carrying the bead" {
  init_beads; opt_in
  bd -C "$REPO" create "findable title" >/dev/null 2>&1
  run_stage "git commit -m x"
  run jq -e -s 'length >= 1 and (map(.title) | index("findable title"))' \
    "$REPO/.beads/issues.jsonl"
  [ "$status" -eq 0 ]
}

@test "stage: a git-ignored target reports instead of failing silently" {
  init_beads; opt_in
  bd -C "$REPO" create "a bead" >/dev/null 2>&1
  # A stealth `bd init` produces exactly this state. `git add` on an ignored
  # path exits non-zero without staging, so the sync would look healthy while
  # nothing was ever committed.
  printf '.beads/\n' >> "$REPO/.git/info/exclude"
  output="$(run_stage 'git commit -m x')"
  [ -z "$(staged)" ]
  printf '%s' "$output" | jq -e '.hookSpecificOutput.additionalContext | test("git-ignored")'
}

# --- import: hydration ------------------------------------------------------

@test "hydrate: a peer bead in the committed file lands in the database" {
  init_beads; opt_in
  bd -C "$REPO" create "local bead" >/dev/null 2>&1
  run_stage "git commit -m x"
  # Append a row as a `git pull` from a peer would.
  jq -c '.id = "tb-peer1" | .title = "peer bead"' \
    <(head -1 "$REPO/.beads/issues.jsonl") >> "$REPO/.beads/issues.jsonl"
  run_hydrate
  run bd -C "$REPO" show tb-peer1
  [ "$status" -eq 0 ]
}

@test "hydrate: routine hydration is silent" {
  init_beads; opt_in
  bd -C "$REPO" create "a bead" >/dev/null 2>&1
  run_stage "git commit -m x"
  # Nothing changed since the export, so a session start must not annotate every
  # single session with a no-op line.
  run run_hydrate
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "hydrate: a stale committed file cannot revert newer local work" {
  init_beads; opt_in
  id="$(bd -C "$REPO" q "a bead" 2>/dev/null | tr -d '[:space:]')"
  [ -n "$id" ] || skip "bd q did not return an id"
  run_stage "git commit -m x"
  # updated_at has second granularity, and a tie keeps local anyway; sleep past
  # the boundary so this exercises the strictly-newer path it claims to.
  sleep 2
  bd -C "$REPO" update "$id" -d "newer local work" >/dev/null 2>&1

  # Hold the hook output in a named variable: bats' `run` clobbers $output, so
  # asserting on it after a later `run` would check the wrong command.
  hook_out="$(run_hydrate)"

  # The divergence is reported rather than hidden -- the next export would
  # otherwise overwrite what a peer committed.
  [[ "$hook_out" == *"BEHIND"* ]]
  printf '%s' "$hook_out" | jq -e '.hookSpecificOutput.hookEventName == "SessionStart"'

  # And the newer local description survived the import.
  run bd -C "$REPO" show "$id"
  [ "$status" -eq 0 ]
  [[ "$output" == *"newer local work"* ]]
}

# --- Dolt-first ordering ----------------------------------------------------

@test "hydrate: no Dolt auto-pull opt-in means no pull is attempted" {
  init_beads; opt_in
  # custom.dolt-auto-pull is unset. Even if a remote existed, the hook must not
  # reach the network -- pull is opt-in because the SYNC doctrine requires
  # explicit sync authority.
  run run_hydrate
  [ "$status" -eq 0 ]
  [[ "$output" != *"dolt pull"* ]]
}

@test "hydrate: a bogus Dolt remote is reported, not fatal, and JSONL still runs" {
  init_beads; opt_in
  bd -C "$REPO" create "local bead" >/dev/null 2>&1
  run_stage "git commit -m x"
  # Point at an unreachable remote and authorise the pull. The pull must fail,
  # the hook must survive it, and the JSONL path must still hydrate the peer row.
  bd -C "$REPO" dolt remote add origin \
    "git+https://invalid.invalid/nope.git" >/dev/null 2>&1 || skip "cannot add remote"
  bd -C "$REPO" config set custom.dolt-auto-pull true >/dev/null 2>&1
  jq -c '.id = "tb-peer2" | .title = "peer via jsonl"' \
    <(head -1 "$REPO/.beads/issues.jsonl") >> "$REPO/.beads/issues.jsonl"

  BEADS_SYNC_PULL_TIMEOUT=5 run run_hydrate
  [ "$status" -eq 0 ]
  # Reported rather than swallowed: a silent pull failure would leave the
  # operator believing native sync was working.
  [[ "$output" == *"did not complete"* ]]
  run bd -C "$REPO" show tb-peer2
  [ "$status" -eq 0 ]
}

@test "hydrate: identical file skips the import entirely" {
  init_beads; opt_in
  bd -C "$REPO" create "a bead" >/dev/null 2>&1
  run_stage "git commit -m x"
  # The file now matches a fresh export byte for byte, so there is nothing to
  # import. Silence proves the content comparison short-circuited.
  run run_hydrate
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# --- stage: native auto-export coexistence -----------------------------------

@test "stage: unchanged state does not rewrite the file" {
  init_beads; opt_in
  bd -C "$REPO" create "a bead" >/dev/null 2>&1
  run_stage "git commit -m x"
  git -C "$REPO" commit -q -m "chore: bead state" 2>/dev/null || true
  before="$(md5 -q "$REPO/.beads/issues.jsonl" 2>/dev/null ||
            md5sum "$REPO/.beads/issues.jsonl" | cut -d' ' -f1)"
  # A second commit with no bead changes must not carry a spurious diff.
  run_stage "git commit -m y"
  after="$(md5 -q "$REPO/.beads/issues.jsonl" 2>/dev/null ||
           md5sum "$REPO/.beads/issues.jsonl" | cut -d' ' -f1)"
  [ "$before" = "$after" ]
  [ -z "$(staged)" ]
}
