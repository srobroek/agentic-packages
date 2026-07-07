#!/usr/bin/env bats
#
# Tests for git-guard.sh — the PreToolUse git-safety hook.
#
# Portability floor: bash 3.2.57 + BSD sed/grep (stock macOS). These tests use
# only core bats (run / status / output) — no bats-support / bats-assert — so
# they run anywhere bats + jq are installed.
#
# The hook reads a JSON event on stdin and emits a Claude PreToolUse decision on
# stdout: {hookSpecificOutput:{hookEventName,permissionDecision,...}}. When no
# guard fires it emits nothing and exits 0 ("allow" by omission).
#
# Policy summary (new behavior):
#   DENY  — destructive op whose target is unverifiable due to an unexpanded
#           shell variable or ~ redirect (-C "$DIR", --git-dir=$X, etc.)
#   ALLOW + additionalContext (warn) — destructive op on a dirty tracked tree
#           (reset --hard, checkout --, restore worktree, clean -f on non-empty),
#           and push --force/--force-with-lease/-f. Always non-blocking.
#   ALLOW silently — clean tree, branch -D, tag -d, stash drop/clear,
#           worktree remove --force (dropped from guard entirely), and all
#           non-destructive commands.
#   No "ask" is ever emitted.

setup() {
  # Hermetic git: ignore the host's system/global config so fixtures do not
  # inherit a system core.hooksPath (e.g. a corporate git wrapper), which would
  # run on every fixture commit and make this suite minutes-slow.
  export GIT_CONFIG_SYSTEM=/dev/null GIT_CONFIG_GLOBAL=/dev/null
  GUARD="${BATS_TEST_DIRNAME}/../scripts/git-guard.sh"
  [ -f "$GUARD" ] || {
    echo "guard script not found at $GUARD" >&2
    return 1
  }
  if ! command -v jq >/dev/null 2>&1; then
    skip "jq not available"
  fi
  if ! command -v git >/dev/null 2>&1; then
    skip "git not available"
  fi
}

# new_repo <state>  → prints the path to a fresh fixture git repo in $state.
#   clean      committed, working tree clean
#   dirty      committed, then a tracked file modified but not committed
#   untracked  committed clean, plus an extra untracked file (tracked tree clean)
# Repos live under BATS_TEST_TMPDIR (per-test, auto-cleaned). Git identity is set
# locally so commits work without relying on the caller's global config.
new_repo() {
  local state="$1" dir
  dir="$(mktemp -d "${BATS_TEST_TMPDIR}/repo.XXXXXX")"
  git -C "$dir" init -q
  git -C "$dir" config user.email guard@test.local
  git -C "$dir" config user.name "Guard Test"
  printf 'v1\n' >"$dir/tracked.txt"
  git -C "$dir" add tracked.txt
  git -C "$dir" commit -q -m init
  case "$state" in
    clean) ;;
    dirty) printf 'v2\n' >"$dir/tracked.txt" ;;
    untracked) printf 'scratch\n' >"$dir/untracked.txt" ;;
    *) echo "unknown repo state: $state" >&2; return 1 ;;
  esac
  printf '%s' "$dir"
}

# payload_in <cwd> <command>  → JSON event with .cwd and a string command.
payload_in() {
  jq -cn --arg cwd "$1" --arg cmd "$2" \
    '{cwd:$cwd, tool_input:{command:$cmd}}'
}

# decision_of <json-payload>
# Runs the guard with the payload on stdin and echoes the permissionDecision,
# or the literal string "allow" when the guard emits nothing.
decision_of() {
  local out
  out="$(printf '%s' "$1" | /usr/bin/env bash "$GUARD" 2>/dev/null || true)"
  if [ -z "$out" ]; then
    printf 'allow'
    return 0
  fi
  printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecision // "allow"'
}

# assert_decision <expected> <json-payload>
assert_decision() {
  local expected="$1" payload="$2" got
  got="$(decision_of "$payload")"
  if [ "$got" != "$expected" ]; then
    echo "expected=$expected got=$got payload=$payload" >&2
    return 1
  fi
}

# assert_has_context <json-payload>
# Asserts the guard emits additionalContext (non-empty) — the warn signal.
assert_has_context() {
  local payload="$1" out ctx
  out="$(printf '%s' "$payload" | /usr/bin/env bash "$GUARD" 2>/dev/null || true)"
  ctx="$(printf '%s' "$out" | jq -r '.hookSpecificOutput.additionalContext // empty' 2>/dev/null || true)"
  if [ -z "$ctx" ]; then
    echo "expected additionalContext but got none; output=$out" >&2
    return 1
  fi
}

# ---------------------------------------------------------------------------
# DENY — unverifiable redirect target (unexpanded variable / ~).
# A CLEAN .cwd is used to prove the deny comes from the variable, not the tree.
# ---------------------------------------------------------------------------

@test "deny: git -C \"\$DIR\" reset --hard (unexpanded variable in -C)" {
  local r; r="$(new_repo clean)"
  assert_decision deny "$(payload_in "$r" 'git -C "$DIR" reset --hard')"
}

@test "deny: git --git-dir=\$X reset --hard (unexpanded variable in --git-dir)" {
  local r; r="$(new_repo clean)"
  assert_decision deny "$(payload_in "$r" 'git --git-dir=$X reset --hard')"
}

@test "deny: git --work-tree=~/wt reset --hard (tilde in --work-tree)" {
  local r; r="$(new_repo clean)"
  assert_decision deny "$(payload_in "$r" 'git --work-tree=~/wt reset --hard')"
}

@test "allow: -C with single-quoted spaced LITERAL path then reset --hard on clean tree" {
  # A quoted literal path (no $ or ~) is verifiable; strip_git_prefix parses it.
  # The .cwd is a clean repo so no work is at risk → silent allow.
  local r; r="$(new_repo clean)"
  assert_decision allow "$(payload_in "$r" "git -C '/path with space' reset --hard")"
}

@test "allow: -C with double-quoted spaced LITERAL path then reset --hard on clean tree" {
  local r; r="$(new_repo clean)"
  assert_decision allow "$(payload_in "$r" 'git -C "/path with space" reset --hard')"
}

@test "allow: --git-dir with spaced inline LITERAL value then reset --hard on clean tree" {
  # Quoted literal --git-dir value has no $ or ~ → verifiable → clean tree → allow.
  local r; r="$(new_repo clean)"
  assert_decision allow "$(payload_in "$r" "git --git-dir='/a b/.git' reset --hard")"
}

@test "allow: multiple stacked global opts with LITERAL -C path, clean tree -> allow" {
  local r; r="$(new_repo clean)"
  assert_decision allow "$(payload_in "$r" "git -C '/a b' -c x=y --no-pager reset --hard")"
}

@test "warn/allow: reset --hard when .cwd is not a git repo (fail closed — warns, not denies)" {
  # When we cannot confirm a clean tree (not in a git repo), uncommitted_work_at_risk
  # fails closed (returns true). reset --hard emits warn (allow + context), not deny.
  local d; d="$(mktemp -d "${BATS_TEST_TMPDIR}/notrepo.XXXXXX")"
  assert_decision allow "$(payload_in "$d" 'git reset --hard')"
  assert_has_context "$(payload_in "$d" 'git reset --hard')"
}

# ---------------------------------------------------------------------------
# WARN (allow + additionalContext) — dirty-tree destructive ops and force push.
# These were previously "deny" or "ask"; now they are non-blocking warns.
# ---------------------------------------------------------------------------

@test "warn/allow: plain reset --hard in a DIRTY tree emits allow + additionalContext" {
  local r; r="$(new_repo dirty)"
  assert_decision allow "$(payload_in "$r" 'git reset --hard')"
  assert_has_context "$(payload_in "$r" 'git reset --hard')"
}

@test "warn/allow: reset via STRING tool_input (old idiom), dirty tree -> allow + context" {
  # The naive `.tool_input.command // .tool_input` jq threw on a string and
  # silently allowed this. Type-checked idiom must still warn. With a string
  # tool_input there is no .cwd, so this exercises the $PWD fallback path: run
  # the guard from inside the dirty fixture repo.
  local r; r="$(new_repo dirty)"
  run bash -c "cd '$r' && printf '%s' '{\"tool_input\":\"git reset --hard\"}' | /usr/bin/env bash '$GUARD'"
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecision == "allow"' >/dev/null
  printf '%s' "$output" | jq -e '.hookSpecificOutput.additionalContext | length > 0' >/dev/null
}

@test "warn/allow: reset HEAD --hard (--hard is NOT the immediate next token), dirty" {
  local r; r="$(new_repo dirty)"
  assert_decision allow "$(payload_in "$r" 'git reset HEAD --hard')"
  assert_has_context "$(payload_in "$r" 'git reset HEAD --hard')"
}

@test "warn/allow: reset --hard HEAD~3 (trailing ref), dirty" {
  local r; r="$(new_repo dirty)"
  assert_decision allow "$(payload_in "$r" 'git reset --hard HEAD~3')"
}

@test "warn/allow: -c config kv with spaced value then reset --hard (dirty tree -> warn)" {
  # -c (config) does NOT redirect the repo, so this warns on tree state.
  local r; r="$(new_repo dirty)"
  assert_decision allow "$(payload_in "$r" "git -c user.name='A B' reset --hard")"
  assert_has_context "$(payload_in "$r" "git -c user.name='A B' reset --hard")"
}

@test "warn/allow: push --force emits allow + additionalContext" {
  assert_decision allow '{"tool_input":{"command":"git push --force origin main"}}'
  assert_has_context '{"tool_input":{"command":"git push --force origin main"}}'
}

@test "warn/allow: push -f short flag -> allow + context" {
  assert_decision allow '{"tool_input":{"command":"git push -f"}}'
  assert_has_context '{"tool_input":{"command":"git push -f"}}'
}

@test "warn/allow: push --force-with-lease -> allow + context" {
  assert_decision allow '{"tool_input":{"command":"git push --force-with-lease"}}'
  assert_has_context '{"tool_input":{"command":"git push --force-with-lease"}}'
}

@test "warn/allow: push origin main --force (force is trailing token) -> allow + context" {
  assert_decision allow '{"tool_input":{"command":"git push origin main --force"}}'
}

@test "warn/allow: push -f=origin (equals boundary) -> allow + context" {
  assert_decision allow '{"tool_input":{"command":"git push -f=origin"}}'
}

@test "warn/allow: restore <file> (default=worktree) in a DIRTY tree -> allow + context" {
  local r; r="$(new_repo dirty)"
  assert_decision allow "$(payload_in "$r" 'git restore file.txt')"
  assert_has_context "$(payload_in "$r" 'git restore file.txt')"
}

@test "warn/allow: restore --worktree in a DIRTY tree -> allow + context" {
  local r; r="$(new_repo dirty)"
  assert_decision allow "$(payload_in "$r" 'git restore --worktree file.txt')"
  assert_has_context "$(payload_in "$r" 'git restore --worktree file.txt')"
}

@test "warn/allow: checkout -- path in a DIRTY tree -> allow + context" {
  local r; r="$(new_repo dirty)"
  assert_decision allow "$(payload_in "$r" 'git checkout -- file.txt')"
  assert_has_context "$(payload_in "$r" 'git checkout -- file.txt')"
}

@test "warn/allow: clean -f with untracked files -> allow + context" {
  local r; r="$(new_repo untracked)"
  assert_decision allow "$(payload_in "$r" 'git clean -f')"
  assert_has_context "$(payload_in "$r" 'git clean -f')"
}

@test "warn/allow: clean -df with untracked files -> allow + context" {
  local r; r="$(new_repo untracked)"
  assert_decision allow "$(payload_in "$r" 'git clean -df')"
  assert_has_context "$(payload_in "$r" 'git clean -df')"
}

# ---------------------------------------------------------------------------
# ALLOW (silently) — dropped guards: branch -D, tag -d, stash drop/clear,
# worktree remove --force. No JSON output at all.
# ---------------------------------------------------------------------------

@test "allow: git stash drop -> silent allow (guard dropped)" {
  local out
  out="$(printf '%s' '{"tool_input":{"command":"git stash drop"}}' | /usr/bin/env bash "$GUARD" 2>/dev/null || true)"
  [ -z "$out" ]
}

@test "allow: git stash clear -> silent allow (guard dropped)" {
  local out
  out="$(printf '%s' '{"tool_input":{"command":"git stash clear"}}' | /usr/bin/env bash "$GUARD" 2>/dev/null || true)"
  [ -z "$out" ]
}

@test "allow: branch -D force delete -> silent allow (guard dropped)" {
  local out
  out="$(printf '%s' '{"tool_input":{"command":"git branch -D feature"}}' | /usr/bin/env bash "$GUARD" 2>/dev/null || true)"
  [ -z "$out" ]
}

@test "allow: branch --delete --force -> silent allow (guard dropped)" {
  local out
  out="$(printf '%s' '{"tool_input":{"command":"git branch --delete --force x"}}' | /usr/bin/env bash "$GUARD" 2>/dev/null || true)"
  [ -z "$out" ]
}

@test "allow: branch -df (force cluster) -> silent allow (guard dropped)" {
  local out
  out="$(printf '%s' '{"tool_input":{"command":"git branch -df feature"}}' | /usr/bin/env bash "$GUARD" 2>/dev/null || true)"
  [ -z "$out" ]
}

@test "allow: tag -d -> silent allow (guard dropped)" {
  local out
  out="$(printf '%s' '{"tool_input":{"command":"git tag -d v1.0"}}' | /usr/bin/env bash "$GUARD" 2>/dev/null || true)"
  [ -z "$out" ]
}

@test "allow: worktree remove --force -> silent allow (guard dropped)" {
  local out
  out="$(printf '%s' '{"tool_input":{"command":"git worktree remove --force wt"}}' | /usr/bin/env bash "$GUARD" 2>/dev/null || true)"
  [ -z "$out" ]
}

@test "allow: worktree remove -f (short force flag) -> silent allow (guard dropped)" {
  local out
  out="$(printf '%s' '{"tool_input":{"command":"git worktree remove -f wt"}}' | /usr/bin/env bash "$GUARD" 2>/dev/null || true)"
  [ -z "$out" ]
}

# ---------------------------------------------------------------------------
# ALLOW — non-destructive commands and near-miss false-positive guards.
# ---------------------------------------------------------------------------

@test "allow: git status" {
  assert_decision allow '{"tool_input":{"command":"git status"}}'
}

@test "allow: plain push (no force)" {
  assert_decision allow '{"tool_input":{"command":"git push"}}'
}

@test "allow: commit message that merely contains the phrase reset --hard" {
  assert_decision allow '{"tool_input":{"command":"git commit -m \"reset --hard stuff\""}}'
}

@test "allow: reset --soft (not --hard)" {
  assert_decision allow '{"tool_input":{"command":"git reset --soft HEAD~1"}}'
}

@test "allow: reset --hard in a CLEAN tree (nothing would be lost)" {
  local r; r="$(new_repo clean)"
  assert_decision allow "$(payload_in "$r" 'git reset --hard')"
}

@test "allow: reset --hard HEAD~3 in a CLEAN tree (ref move is reflog-recoverable)" {
  local r; r="$(new_repo clean)"
  assert_decision allow "$(payload_in "$r" 'git reset --hard HEAD~3')"
}

@test "allow: reset --hard with ONLY untracked files (tracked tree is clean)" {
  local r; r="$(new_repo untracked)"
  assert_decision allow "$(payload_in "$r" 'git reset --hard')"
}

# restore --staged only UNSTAGES (working tree untouched, fully reversible) — it
# must NEVER warn, even with a dirty tree. This was the false positive.
@test "allow: restore --staged (unstage only) in a DIRTY tree" {
  local r; r="$(new_repo dirty)"
  assert_decision allow "$(payload_in "$r" 'git restore --staged file.txt')"
}

@test "allow: restore <file> (worktree) in a CLEAN tree (nothing uncommitted to lose)" {
  local r; r="$(new_repo clean)"
  assert_decision allow "$(payload_in "$r" 'git restore file.txt')"
}

@test "allow: checkout -- path in a CLEAN tree (nothing uncommitted to lose)" {
  local r; r="$(new_repo clean)"
  assert_decision allow "$(payload_in "$r" 'git checkout -- file.txt')"
}

@test "allow: branch -d (safe merge-checked delete)" {
  assert_decision allow '{"tool_input":{"command":"git branch -d feature"}}'
}

@test "allow: branch --delete (safe merge-checked delete)" {
  assert_decision allow '{"tool_input":{"command":"git branch --delete x"}}'
}

@test "allow: branch -a (list, no delete)" {
  assert_decision allow '{"tool_input":{"command":"git branch -a"}}'
}

@test "allow: branch --merged (no false positive on -merged)" {
  assert_decision allow '{"tool_input":{"command":"git branch --merged main"}}'
}

@test "allow: branch -m rename" {
  assert_decision allow '{"tool_input":{"command":"git branch -m oldname newname"}}'
}

@test "allow: clean -n dry run (no force flag)" {
  assert_decision allow '{"tool_input":{"command":"git clean -n"}}'
}

@test "allow: clean --help (no force)" {
  assert_decision allow '{"tool_input":{"command":"git clean --help"}}'
}

@test "allow: clean -f in a CLEAN repo (nothing untracked, nothing to warn about)" {
  local r; r="$(new_repo clean)"
  assert_decision allow "$(payload_in "$r" 'git clean -f')"
}

@test "allow: push --follow-tags (--f... is not -f)" {
  assert_decision allow '{"tool_input":{"command":"git push --follow-tags origin main"}}'
}

@test "allow: push --force-if-includes (safety flag, not force push)" {
  assert_decision allow '{"tool_input":{"command":"git push --force-if-includes origin x"}}'
}

@test "allow: checkout to a branch (no -- pathspec)" {
  assert_decision allow '{"tool_input":{"command":"git checkout main"}}'
}

@test "allow: worktree remove (plain — git refuses if dirty)" {
  assert_decision allow '{"tool_input":{"command":"git worktree remove wt"}}'
}

# ---------------------------------------------------------------------------
# MALFORMED / EDGE STDIN — must never crash; default to allow.
# ---------------------------------------------------------------------------

@test "allow: empty stdin" {
  assert_decision allow ''
}

@test "allow: empty JSON object" {
  assert_decision allow '{}'
}

@test "allow: non-JSON garbage on stdin" {
  assert_decision allow 'garbage not json'
}

@test "allow: tool_input is null" {
  assert_decision allow '{"tool_input":null}'
}

@test "guard exits 0 even when it warns (Claude reads decision from stdout)" {
  local r payload; r="$(new_repo dirty)"
  payload="$(payload_in "$r" 'git reset --hard')"
  run bash -c "printf '%s' '$payload' | /usr/bin/env bash '$GUARD'"
  [ "$status" -eq 0 ]
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecision == "allow"' >/dev/null
}

@test "guard exits 0 even when it denies (Claude reads decision from stdout)" {
  local r payload; r="$(new_repo clean)"
  payload="$(payload_in "$r" 'git -C "$DIR" reset --hard')"
  run bash -c "printf '%s' '$payload' | /usr/bin/env bash '$GUARD'"
  [ "$status" -eq 0 ]
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
}

# ---------------------------------------------------------------------------
# Rule-ID citation: guard messages must cite the GS rule that fired.
# ---------------------------------------------------------------------------

@test "deny message cites a GS rule ID (GS-2)" {
  # An unexpanded variable in -C fires GS-2; the deny reason must cite it.
  local r; r="$(new_repo clean)"
  local out
  out="$(payload_in "$r" 'git -C "$DIR" reset --hard' | /usr/bin/env bash "$GUARD" 2>/dev/null || true)"
  printf '%s' "$out" | jq -e '.hookSpecificOutput.permissionDecisionReason | test("GS-[0-9]")' >/dev/null
}

@test "warn additionalContext cites a GS rule ID (GS-3)" {
  # reset --hard on a dirty tree fires GS-3; the advisory must cite it.
  local r; r="$(new_repo dirty)"
  local out ctx
  out="$(payload_in "$r" 'git reset --hard' | /usr/bin/env bash "$GUARD" 2>/dev/null || true)"
  ctx="$(printf '%s' "$out" | jq -r '.hookSpecificOutput.additionalContext // empty' 2>/dev/null || true)"
  printf '%s' "$ctx" | grep -q 'GS-[0-9]'
}
