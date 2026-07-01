#!/usr/bin/env bats
#
# Coverage for release-please-guard.sh -- a non-blocking PreToolUse hook that
# warns when, on a release-please-managed repo, the agent tries to cut a release
# or tag manually, push tags, or hand-merge a release branch to a protected
# branch. Tests assert the warn/allow decision (presence/absence of
# additionalContext), that it stays silent off release-please repos, and that it
# parses under /bin/bash (macOS bash 3.2.57).
#
# Run: bats packages/release-please/tests/release-please-guard.bats

setup() {
  GUARD="${BATS_TEST_DIRNAME}/../scripts/release-please-guard.sh"
  DETECT="${BATS_TEST_DIRNAME}/../.apm/skills/release-please/scripts/detect-release-please.sh"

  # A throwaway repo that LOOKS release-please-managed (config + manifest).
  RP_DIR="$(mktemp -d)"
  printf '{"packages":{".":{}}}\n' >"$RP_DIR/release-please-config.json"
  printf '{".":"1.0.0"}\n' >"$RP_DIR/.release-please-manifest.json"
  ( cd "$RP_DIR" && git init -q && git config user.email t@t && git config user.name t \
    && git add -A && git commit -qm init && git branch -M main ) >/dev/null 2>&1 || true

  # A throwaway repo with NO release-please config.
  PLAIN_DIR="$(mktemp -d)"
  ( cd "$PLAIN_DIR" && git init -q && git config user.email t@t && git config user.name t \
    && git commit -q --allow-empty -m init && git branch -M main ) >/dev/null 2>&1 || true
}

teardown() {
  [ -n "${RP_DIR:-}" ] && rm -rf "$RP_DIR"
  [ -n "${PLAIN_DIR:-}" ] && rm -rf "$PLAIN_DIR"
}

# Build a PreToolUse Bash payload with a command + cwd.
mk() {
  jq -cn --arg c "$1" --arg d "$2" '{tool_input: {command: $c}, cwd: $d}'
}

# Build a payload where tool_input is a bare STRING (the historical bypass).
mk_str() {
  jq -cn --arg c "$1" --arg d "$2" '{tool_input: $c, cwd: $d}'
}

run_guard() {
  output="$(printf '%s' "$1" | /bin/bash "$GUARD")"
  status=$?
  context="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.additionalContext // empty' 2>/dev/null || true)"
}

# --- parse / portability floor --------------------------------------------

@test "release-please-guard.sh parses under /bin/bash (no bash-4 syntax)" {
  run /bin/bash -n "$GUARD"
  [ "$status" -eq 0 ]
}

@test "detect-release-please.sh parses under /bin/bash" {
  run /bin/bash -n "$DETECT"
  [ "$status" -eq 0 ]
}

# --- detection --------------------------------------------------------------

@test "detect exits 0 (present) on a release-please repo" {
  run /bin/bash "$DETECT" "$RP_DIR"
  [ "$status" -eq 0 ]
  case "$output" in *"present=true"*) : ;; *) false ;; esac
}

@test "detect exits 1 (absent) on a plain repo" {
  run /bin/bash "$DETECT" "$PLAIN_DIR"
  [ "$status" -eq 1 ]
  case "$output" in *"present=false"*) : ;; *) false ;; esac
}

# --- warns on manual release operations (rp repo) ---------------------------

@test "gh release create on rp repo -> warn" {
  run_guard "$(mk "gh release create v9.9.9" "$RP_DIR")"
  [ "$status" -eq 0 ]
  [ -n "$context" ]
  case "$context" in *"release-please"*) : ;; *) false ;; esac
}

@test "git tag vX.Y.Z on rp repo -> warn" {
  run_guard "$(mk "git tag -a v1.2.3 -m release" "$RP_DIR")"
  [ "$status" -eq 0 ]
  [ -n "$context" ]
}

@test "git push --tags on rp repo -> warn" {
  run_guard "$(mk "git push origin --tags" "$RP_DIR")"
  [ "$status" -eq 0 ]
  [ -n "$context" ]
}

@test "git push --follow-tags on rp repo -> warn" {
  run_guard "$(mk "git push --follow-tags" "$RP_DIR")"
  [ "$status" -eq 0 ]
  [ -n "$context" ]
}

@test "string-form tool_input still warns (no bypass, no crash)" {
  run_guard "$(mk_str "gh release create v2.0.0" "$RP_DIR")"
  [ "$status" -eq 0 ]
  [ -n "$context" ]
}

# --- stays silent (allow) ---------------------------------------------------

@test "benign command on rp repo -> silent allow" {
  run_guard "$(mk "npm run build" "$RP_DIR")"
  [ "$status" -eq 0 ]
  [ -z "$context" ]
}

@test "gh release create on a NON-rp repo -> silent allow" {
  run_guard "$(mk "gh release create v1.0.0" "$PLAIN_DIR")"
  [ "$status" -eq 0 ]
  [ -z "$context" ]
}

@test "gh release view (read-only) -> silent allow" {
  run_guard "$(mk "gh release view v1.0.0" "$RP_DIR")"
  [ "$status" -eq 0 ]
  [ -z "$context" ]
}

@test "git tag -l (list, no version) -> silent allow" {
  run_guard "$(mk "git tag -l" "$RP_DIR")"
  [ "$status" -eq 0 ]
  [ -z "$context" ]
}

@test "empty payload -> silent allow" {
  run_guard ""
  [ "$status" -eq 0 ]
  [ -z "$context" ]
}

# --- protected-branch merge advisory ---------------------------------------

@test "git merge while on main of rp repo -> warn about release PR flow" {
  # Create a branch to merge so `git merge` is a real merge form.
  ( cd "$RP_DIR" && git checkout -qb feat && git commit -q --allow-empty -m x && git checkout -qq main ) >/dev/null 2>&1 || true
  run_guard "$(mk "git merge feat" "$RP_DIR")"
  [ "$status" -eq 0 ]
  [ -n "$context" ]
  case "$context" in *"release PR"*) : ;; *) false ;; esac
}

@test "git merge --abort -> silent allow (recovery form)" {
  run_guard "$(mk "git merge --abort" "$RP_DIR")"
  [ "$status" -eq 0 ]
  [ -z "$context" ]
}
