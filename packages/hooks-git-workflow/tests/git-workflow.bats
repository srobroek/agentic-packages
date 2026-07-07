#!/usr/bin/env bats
#
# Tests for hooks-git-workflow:
#   - uncommitted-warn.sh  Stop-time dirty-tree / unpushed-commits nudge
#
# Portability floor: bash 3.2.57 + BSD userland.
# Run: bats packages/hooks-git-workflow/tests/git-workflow.bats

setup() {
  # Hermetic git: ignore host system/global config (e.g. a corporate
  # core.hooksPath) so fixture commits are fast and deterministic.
  export GIT_CONFIG_SYSTEM=/dev/null GIT_CONFIG_GLOBAL=/dev/null
  S="$(cd "${BATS_TEST_DIRNAME}/../scripts" && pwd -P)"
  WARN="$S/uncommitted-warn.sh"
  command -v jq >/dev/null 2>&1 || skip "jq not available"
  command -v git >/dev/null 2>&1 || skip "git not available"

  REPO="$(mktemp -d "${BATS_TEST_TMPDIR}/repo.XXXXXX")"
  REPO="$(cd "$REPO" && pwd -P)"
  git -C "$REPO" init -q
  git -C "$REPO" config user.email t@t.t
  git -C "$REPO" config user.name t
}

# --- parse ------------------------------------------------------------------

@test "scripts parse under /bin/bash" {
  run /bin/bash -n "$WARN"; [ "$status" -eq 0 ]
}

# --- uncommitted-warn -------------------------------------------------------

@test "warn: dirty tracked tree -> systemMessage" {
  printf 'v1\n' > "$REPO/f.txt"; git -C "$REPO" add f.txt; git -C "$REPO" commit -q -m init
  printf 'v2\n' > "$REPO/f.txt"   # tracked, uncommitted
  out="$(jq -cn '{stop_hook_active:false}' | (cd "$REPO" && /bin/bash "$WARN") 2>&1)"
  printf '%s' "$out" | jq -e '.systemMessage | test("Uncommitted")' >/dev/null
}

@test "warn: dirty tree message cites GW rule ID" {
  printf 'v1\n' > "$REPO/f.txt"; git -C "$REPO" add f.txt; git -C "$REPO" commit -q -m init
  printf 'v2\n' > "$REPO/f.txt"   # tracked, uncommitted
  out="$(jq -cn '{stop_hook_active:false}' | (cd "$REPO" && /bin/bash "$WARN") 2>&1)"
  printf '%s' "$out" | jq -e '.systemMessage | test("GW-[0-9]")' >/dev/null
}

@test "warn: clean tree -> no output" {
  printf 'v1\n' > "$REPO/f.txt"; git -C "$REPO" add f.txt; git -C "$REPO" commit -q -m init
  out="$(jq -cn '{stop_hook_active:false}' | (cd "$REPO" && /bin/bash "$WARN") 2>&1)"
  [ -z "$out" ]
}

@test "warn: commits ahead of upstream -> systemMessage" {
  BARE="$(mktemp -d "${BATS_TEST_TMPDIR}/bare.XXXXXX")"; git init -q --bare "$BARE"
  printf 'v1\n' > "$REPO/f.txt"; git -C "$REPO" add f.txt; git -C "$REPO" commit -q -m init
  git -C "$REPO" remote add origin "$BARE"
  git -C "$REPO" push -q -u origin HEAD
  printf 'v2\n' > "$REPO/f.txt"; git -C "$REPO" add f.txt; git -C "$REPO" commit -q -m ahead
  out="$(jq -cn '{stop_hook_active:false}' | (cd "$REPO" && /bin/bash "$WARN") 2>&1)"
  printf '%s' "$out" | jq -e '.systemMessage | test("Unpushed")' >/dev/null
}

@test "warn: pushed and clean -> no output" {
  BARE="$(mktemp -d "${BATS_TEST_TMPDIR}/bare.XXXXXX")"; git init -q --bare "$BARE"
  printf 'v1\n' > "$REPO/f.txt"; git -C "$REPO" add f.txt; git -C "$REPO" commit -q -m init
  git -C "$REPO" remote add origin "$BARE"
  git -C "$REPO" push -q -u origin HEAD
  out="$(jq -cn '{stop_hook_active:false}' | (cd "$REPO" && /bin/bash "$WARN") 2>&1)"
  [ -z "$out" ]
}
