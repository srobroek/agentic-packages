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

# ---------------------------------------------------------------------------
# HARD DENY — reset --hard (incl. bypass orderings) and force push.
# ---------------------------------------------------------------------------

# reset --hard is conditional: it only denies when the tracked working tree is
# dirty (work would be lost). All plain-form deny tests therefore run in a DIRTY
# fixture repo passed via .cwd. Allow-when-clean cases live in the ALLOW section.

@test "deny: plain reset --hard in a DIRTY tree (object tool_input)" {
  local r; r="$(new_repo dirty)"
  assert_decision deny "$(payload_in "$r" 'git reset --hard')"
}

@test "deny: reset --hard via STRING tool_input (old idiom bypass), dirty tree" {
  # The naive `.tool_input.command // .tool_input` jq threw on a string and
  # silently allowed this. Type-checked idiom must still deny. With a string
  # tool_input there is no .cwd, so this exercises the $PWD fallback path: run
  # the guard from inside the dirty fixture repo.
  local r; r="$(new_repo dirty)"
  run bash -c "cd '$r' && printf '%s' '{\"tool_input\":\"git reset --hard\"}' | /usr/bin/env bash '$GUARD'"
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
}

@test "deny: reset HEAD --hard (--hard is NOT the immediate next token), dirty" {
  local r; r="$(new_repo dirty)"
  assert_decision deny "$(payload_in "$r" 'git reset HEAD --hard')"
}

@test "deny: reset --hard HEAD~3 (trailing ref), dirty" {
  local r; r="$(new_repo dirty)"
  assert_decision deny "$(payload_in "$r" 'git reset --hard HEAD~3')"
}

# -C / --git-dir / --work-tree redirect git to a DIFFERENT repo than .cwd, whose
# state we can't trust → fail closed (deny) regardless of .cwd cleanliness. A
# CLEAN .cwd is passed to prove the deny comes from the redirect, not the tree.

@test "deny: -C with single-quoted spaced path then reset --hard (fail closed)" {
  local r; r="$(new_repo clean)"
  assert_decision deny "$(payload_in "$r" "git -C '/path with space' reset --hard")"
}

@test "deny: -C with double-quoted spaced path then reset --hard (fail closed)" {
  local r; r="$(new_repo clean)"
  assert_decision deny "$(payload_in "$r" 'git -C "/path with space" reset --hard')"
}

@test "deny: -c config kv with spaced value then reset --hard (dirty tree)" {
  # -c (config) does NOT redirect the repo, so this denies on tree state.
  local r; r="$(new_repo dirty)"
  assert_decision deny "$(payload_in "$r" "git -c user.name='A B' reset --hard")"
}

@test "deny: --git-dir spaced inline value then reset --hard (fail closed)" {
  local r; r="$(new_repo clean)"
  assert_decision deny "$(payload_in "$r" "git --git-dir='/a b/.git' reset --hard")"
}

@test "deny: multiple stacked global opts then reset --hard (fail closed via -C)" {
  local r; r="$(new_repo clean)"
  assert_decision deny "$(payload_in "$r" "git -C '/a b' -c x=y --no-pager reset --hard")"
}

@test "deny: reset --hard when .cwd is not a git repo (fail closed)" {
  local d; d="$(mktemp -d "${BATS_TEST_TMPDIR}/notrepo.XXXXXX")"
  assert_decision deny "$(payload_in "$d" 'git reset --hard')"
}

@test "deny: push --force" {
  assert_decision deny '{"tool_input":{"command":"git push --force origin main"}}'
}

@test "deny: push -f short flag" {
  assert_decision deny '{"tool_input":{"command":"git push -f"}}'
}

@test "deny: push --force-with-lease" {
  assert_decision deny '{"tool_input":{"command":"git push --force-with-lease"}}'
}

@test "deny: push origin main --force (force is trailing token)" {
  assert_decision deny '{"tool_input":{"command":"git push origin main --force"}}'
}

@test "deny: push -f=origin (equals boundary)" {
  assert_decision deny '{"tool_input":{"command":"git push -f=origin"}}'
}

# ---------------------------------------------------------------------------
# ASK — recoverable destructive ops (downgraded per locked severity policy).
# ---------------------------------------------------------------------------

@test "ask: clean -df (force flag in a cluster, not standalone -f)" {
  assert_decision ask '{"tool_input":{"command":"git clean -df"}}'
}

@test "ask: clean -xdf (force flag mid/end of cluster)" {
  assert_decision ask '{"tool_input":{"command":"git clean -xdf"}}'
}

@test "ask: clean -fd (force flag first in cluster)" {
  assert_decision ask '{"tool_input":{"command":"git clean -fd"}}'
}

@test "ask: clean --force long form" {
  assert_decision ask '{"tool_input":{"command":"git clean --force"}}'
}

@test "ask: clean -f standalone" {
  assert_decision ask '{"tool_input":{"command":"git clean -f"}}'
}

@test "ask: clean -df via STRING tool_input" {
  assert_decision ask '{"tool_input":"git clean -df"}'
}

@test "ask: -C spaced path then clean -df" {
  assert_decision ask "{\"tool_input\":{\"command\":\"git -C '/path with space' clean -df\"}}"
}

@test "ask: branch -D force delete (possibly-unmerged)" {
  assert_decision ask '{"tool_input":{"command":"git branch -D feature"}}'
}

@test "ask: branch --delete --force" {
  assert_decision ask '{"tool_input":{"command":"git branch --delete --force x"}}'
}

@test "ask: branch -df (force cluster)" {
  assert_decision ask '{"tool_input":{"command":"git branch -df feature"}}'
}

@test "allow: branch -d (safe merge-checked delete)" {
  assert_decision allow '{"tool_input":{"command":"git branch -d feature"}}'
}

@test "allow: branch --delete (safe merge-checked delete)" {
  assert_decision allow '{"tool_input":{"command":"git branch --delete x"}}'
}

@test "ask: stash drop" {
  assert_decision ask '{"tool_input":{"command":"git stash drop"}}'
}

@test "ask: stash clear" {
  assert_decision ask '{"tool_input":{"command":"git stash clear"}}'
}

# restore (worktree) and checkout -- discard ONLY uncommitted changes, so they
# mirror reset --hard: ask only when the tracked tree is dirty, allow when clean.
@test "ask: restore <file> (default=worktree) in a DIRTY tree" {
  local r; r="$(new_repo dirty)"
  assert_decision ask "$(payload_in "$r" 'git restore file.txt')"
}

@test "ask: restore --worktree in a DIRTY tree" {
  local r; r="$(new_repo dirty)"
  assert_decision ask "$(payload_in "$r" 'git restore --worktree file.txt')"
}

@test "ask: tag -d" {
  assert_decision ask '{"tool_input":{"command":"git tag -d v1.0"}}'
}

@test "ask: checkout -- path in a DIRTY tree" {
  local r; r="$(new_repo dirty)"
  assert_decision ask "$(payload_in "$r" 'git checkout -- file.txt')"
}

@test "allow: worktree remove (plain — git refuses if dirty)" {
  assert_decision allow '{"tool_input":{"command":"git worktree remove wt"}}'
}

@test "ask: worktree remove --force (can discard uncommitted work)" {
  assert_decision ask '{"tool_input":{"command":"git worktree remove --force wt"}}'
}

@test "ask: worktree remove -f (short force flag)" {
  assert_decision ask '{"tool_input":{"command":"git worktree remove -f wt"}}'
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
# must NEVER prompt, even with a dirty tree. This was the false positive.
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

@test "allow: push --follow-tags (--f... is not -f)" {
  assert_decision allow '{"tool_input":{"command":"git push --follow-tags origin main"}}'
}

@test "allow: push --force-if-includes (safety flag, not force push)" {
  assert_decision allow '{"tool_input":{"command":"git push --force-if-includes origin x"}}'
}

@test "allow: checkout to a branch (no -- pathspec)" {
  assert_decision allow '{"tool_input":{"command":"git checkout main"}}'
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

@test "guard exits 0 even when it denies (Claude reads decision from stdout)" {
  local r payload; r="$(new_repo dirty)"
  payload="$(payload_in "$r" 'git reset --hard')"
  run bash -c "printf '%s' '$payload' | /usr/bin/env bash '$GUARD'"
  [ "$status" -eq 0 ]
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
}
