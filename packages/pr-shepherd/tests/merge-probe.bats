#!/usr/bin/env bats

setup() {
  export PROBE="$(cd "$BATS_TEST_DIRNAME/.." && pwd)/.apm/skills/pr-shepherd/scripts/merge-probe.sh"
}

@test "draft PR is ignored before release classification" {
  run bash -c 'printf "%s" '\''{"state":"OPEN","isDraft":true,"headRefName":"feature/x","labels":[]}'\'' | "$PROBE" eligibility'
  [ "$status" -eq 0 ]
  [ "$output" = draft ]
}

@test "release-please branch is ignored" {
  run bash -c 'printf "%s" '\''{"state":"OPEN","isDraft":false,"headRefName":"release-please--branches--main","labels":[]}'\'' | "$PROBE" eligibility'
  [ "$status" -eq 0 ]
  [ "$output" = release ]
}

@test "autorelease pending label is ignored" {
  run bash -c 'printf "%s" '\''{"state":"OPEN","isDraft":false,"headRefName":"release-main","labels":[{"name":"autorelease: pending"}]}'\'' | "$PROBE" eligibility'
  [ "$status" -eq 0 ]
  [ "$output" = release ]
}

@test "release-looking title is not a release anchor" {
  run bash -c 'printf "%s" '\''{"state":"OPEN","isDraft":false,"headRefName":"feature/x","title":"chore: release main","labels":[]}'\'' | "$PROBE" eligibility'
  [ "$status" -eq 0 ]
  [ "$output" = eligible ]
}

@test "merged PR is routed to reconciliation" {
  run bash -c 'printf "%s" '\''{"state":"MERGED","isDraft":false,"headRefName":"feature/x","labels":[]}'\'' | "$PROBE" eligibility'
  [ "$status" -eq 0 ]
  [ "$output" = merged ]
}

@test "merged release PR remains excluded" {
  run bash -c 'printf "%s" '\''{"state":"MERGED","isDraft":false,"headRefName":"release-please--branches--main","labels":[{"name":"autorelease: pending"}]}'\'' | "$PROBE" eligibility'
  [ "$status" -eq 0 ]
  [ "$output" = release ]
}

@test "closed-unmerged PR is not eligible" {
  run bash -c 'printf "%s" '\''{"state":"CLOSED","isDraft":false,"headRefName":"feature/x","labels":[]}'\'' | "$PROBE" eligibility'
  [ "$status" -eq 0 ]
  [ "$output" = closed ]
}


# --- conflicts: previously untested entirely -------------------------------
#
# `conflicts` had no coverage before these cases, which is why the path-quoting
# defect survived: git C-quotes an unusual path under --name-only, and that quoted
# form flowed into landing-contract.sh's content-addressed failure-key, silently
# changing the key and breaking bounce deduplication for the PR.

conflict_repo() {
  # A repo where main and feat both modify $1, so the merge conflicts on it.
  local path="$1"
  REPO="$(mktemp -d)"
  cd "$REPO" || return 1
  git init -q -b main .
  git config user.email t@t
  git config user.name t
  mkdir -p "$REPO/.no-hooks"
  git config core.hooksPath "$REPO/.no-hooks"
  printf 'base\n' >"$path"
  printf 'x\n' >plain.txt
  git add -A
  git commit -qm base
  git checkout -q -b feat
  printf 'feat\n' >"$path"
  printf 'y\n' >plain.txt
  git add -A
  git commit -qm feat
  git checkout -q main
  printf 'main\n' >"$path"
  printf 'z\n' >plain.txt
  git add -A
  git commit -qm main
}

@test "conflicts lists a conflicting path and exits 1" {
  conflict_repo simple.txt
  run bash "$PROBE" conflicts main feat
  [ "$status" -eq 1 ]
  [[ "$output" == *"simple.txt"* ]]
  [[ "$output" == *"plain.txt"* ]]
}

@test "conflicts emits a tab-containing path RAW, not C-quoted" {
  conflict_repo "$(printf 'wei\trd.txt')"
  run bash "$PROBE" conflicts main feat
  [ "$status" -eq 1 ]
  # The defect emitted the 11 characters "wei\trd.txt" -- surrounding quotes plus a
  # literal backslash-t. The real path holds one tab character.
  [[ "$output" == *"$(printf 'wei\trd.txt')"* ]]
  [[ "$output" != *'\t'* ]]
  [[ "$output" != *'"wei'* ]]
}

@test "conflicts emits a non-ASCII path RAW, not C-quoted" {
  conflict_repo "café.txt"
  run bash "$PROBE" conflicts main feat
  [ "$status" -eq 1 ]
  [[ "$output" == *"café.txt"* ]]
  [[ "$output" != *'\3'* ]]
}

@test "conflicts reports clean and exits 0 when the merge succeeds" {
  REPO="$(mktemp -d)"
  cd "$REPO" || return 1
  git init -q -b main .
  git config user.email t@t
  git config user.name t
  printf 'a\n' >f.txt
  git add -A
  git commit -qm base
  git checkout -q -b feat
  printf 'b\n' >other.txt
  git add -A
  git commit -qm feat
  git checkout -q main
  run bash "$PROBE" conflicts main feat
  [ "$status" -eq 0 ]
  [ "$output" = clean ]
}

@test "conflicts exits 2 on a bad ref rather than reporting clean" {
  conflict_repo simple.txt
  run bash "$PROBE" conflicts main no-such-ref
  [ "$status" -eq 2 ]
}

@test "conflict paths are sorted bytewise so the failure key is stable" {
  conflict_repo simple.txt
  run bash "$PROBE" conflicts main feat
  [ "$status" -eq 1 ]
  # plain.txt sorts before simple.txt in C collation.
  [[ "${lines[0]}" == "plain.txt" ]]
  [[ "${lines[1]}" == "simple.txt" ]]
}
