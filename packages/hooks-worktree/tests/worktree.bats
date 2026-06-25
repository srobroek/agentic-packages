#!/usr/bin/env bats
# Tests for the worktree lifecycle hooks (create + cleanup).
#
# These exercise the real git plumbing against throwaway repos so the
# adversarial cases from the audit fix-list are covered end to end:
#   - worktree-create: a path-traversal worktree_name is rejected and no
#     directory escapes the managed /tmp/claude-worktrees tree.
#   - worktree-cleanup: when CWD is the MAIN repo (not a linked worktree) the
#     hook must NOT stash the user's WIP.
#   - worktree-cleanup: a linked worktree containing only UNTRACKED files must
#     still be removed (force-remove for managed paths), not silently skipped.

SCRIPT_DIR="${BATS_TEST_DIRNAME}/../scripts"
CREATE="${SCRIPT_DIR}/worktree-create.sh"
CLEANUP="${SCRIPT_DIR}/worktree-cleanup.sh"

setup() {
  WORK="$(mktemp -d "${TMPDIR:-/tmp}/wt-bats.XXXXXX")"
  REPO="${WORK}/main"
  mkdir -p "$REPO"
  git -C "$REPO" init -q
  git -C "$REPO" config user.email t@example.com
  git -C "$REPO" config user.name "Test User"
  git -C "$REPO" config commit.gpgsign false
  printf 'hello\n' > "${REPO}/file.txt"
  git -C "$REPO" add file.txt
  git -C "$REPO" commit -qm "init"
}

teardown() {
  # Best-effort: prune any worktrees we created, then nuke the temp tree.
  git -C "$REPO" worktree prune 2>/dev/null || true
  [ -n "$WORK" ] && rm -rf "$WORK"
}

# --- worktree-create: name sanitization -------------------------------------

@test "create: path-traversal worktree_name is rejected (non-zero exit)" {
  run bash "$CREATE" <<EOF
{"cwd": "${REPO}", "worktree_name": "../../escape", "git_ref": "HEAD"}
EOF
  [ "$status" -ne 0 ]
  # No worktree directory should have been created anywhere.
  [ -z "$(git -C "$REPO" worktree list --porcelain | grep -c '^worktree' | sed 's/^1$//')" ] || true
  # The escape target must not exist.
  [ ! -e "${WORK}/escape" ]
  [ ! -e "/tmp/claude-worktrees/escape" ]
}

@test "create: slashed worktree_name is rejected" {
  run bash "$CREATE" <<EOF
{"cwd": "${REPO}", "worktree_name": "foo/bar", "git_ref": "HEAD"}
EOF
  [ "$status" -ne 0 ]
}

@test "create: dotdot-embedded worktree_name is rejected" {
  run bash "$CREATE" <<EOF
{"cwd": "${REPO}", "worktree_name": "a..b", "git_ref": "HEAD"}
EOF
  [ "$status" -ne 0 ]
}

@test "create: whitespace name is collapsed and accepted (not falsely rejected)" {
  run bash "$CREATE" <<EOF
{"cwd": "${REPO}", "worktree_name": "  my feature  ", "git_ref": "HEAD"}
EOF
  [ "$status" -eq 0 ]
  # Emitted path lands under the managed tree with a dash-collapsed name.
  [[ "$output" == /tmp/claude-worktrees/*/my-feature ]]
  [ -d "$output" ]
  # cleanup of the created managed worktree
  git -C "$REPO" worktree remove --force "$output" 2>/dev/null || true
  rm -rf "$output"
}

@test "create: leading-dash name is defanged (stripped) not used as an option" {
  run bash "$CREATE" <<EOF
{"cwd": "${REPO}", "worktree_name": "-rf", "git_ref": "HEAD"}
EOF
  [ "$status" -eq 0 ]
  [[ "$output" == */rf ]]
  git -C "$REPO" worktree remove --force "$output" 2>/dev/null || true
  rm -rf "$output"
}

@test "create: missing cwd exits non-zero" {
  run bash "$CREATE" <<'EOF'
{"worktree_name": "x", "git_ref": "HEAD"}
EOF
  [ "$status" -ne 0 ]
}

@test "create: malformed stdin does not crash the guard" {
  run bash "$CREATE" <<'EOF'
this is not json at all }{
EOF
  # jq fails -> empty cwd -> clean non-zero exit, no stack trace / set -e abort.
  [ "$status" -ne 0 ]
}

# --- worktree-cleanup: main-repo guard --------------------------------------

@test "cleanup: CWD is MAIN repo with WIP -> must NOT stash" {
  # Dirty the main worktree.
  printf 'uncommitted\n' >> "${REPO}/file.txt"
  before="$(git -C "$REPO" stash list | wc -l | tr -d ' ')"

  run bash "$CLEANUP" <<EOF
{"cwd": "${REPO}"}
EOF
  [ "$status" -eq 0 ]

  after="$(git -C "$REPO" stash list | wc -l | tr -d ' ')"
  # No new stash entry was created on the main repo.
  [ "$before" = "$after" ]
  # The WIP is still present in the working tree.
  git -C "$REPO" status --porcelain | grep -q 'file.txt'
}

@test "cleanup: empty/no cwd is a no-op exit 0" {
  run bash "$CLEANUP" <<'EOF'
{}
EOF
  [ "$status" -eq 0 ]
}

@test "cleanup: non-git cwd is a no-op exit 0" {
  outside="${WORK}/not-a-repo"
  mkdir -p "$outside"
  run bash "$CLEANUP" <<EOF
{"cwd": "${outside}"}
EOF
  [ "$status" -eq 0 ]
}

# --- worktree-cleanup: linked worktree with untracked files -----------------

@test "cleanup: linked managed worktree with UNTRACKED file is removed (not silent no-op)" {
  # Build a managed worktree under /tmp/claude-worktrees so MANAGED=1 and the
  # force-remove path is taken even though only untracked files are present.
  repo_name="$(basename "$REPO")"
  managed_root="/tmp/claude-worktrees/${repo_name}"
  mkdir -p "$managed_root"
  wt="${managed_root}/cleanup-untracked-$$"
  git -C "$REPO" worktree add -q "$wt" -b "worktree-cleanup-untracked-$$" HEAD

  # Only an UNTRACKED file (no staged/committed change). A plain
  # `worktree remove` (non-force) would refuse this; force-remove must succeed.
  printf 'scratch\n' > "${wt}/untracked.txt"

  [ -d "$wt" ]
  run bash "$CLEANUP" <<EOF
{"cwd": "${wt}"}
EOF
  [ "$status" -eq 0 ]

  # The worktree directory must be gone — proving removal happened.
  [ ! -d "$wt" ]
  # git no longer lists it as a worktree.
  ! git -C "$REPO" worktree list --porcelain | grep -q "^worktree ${wt}$"

  rm -rf "$managed_root"
}

@test "cleanup: linked managed worktree branch is deleted" {
  repo_name="$(basename "$REPO")"
  managed_root="/tmp/claude-worktrees/${repo_name}"
  mkdir -p "$managed_root"
  wt="${managed_root}/cleanup-branch-$$"
  branch="worktree-cleanup-branch-$$"
  git -C "$REPO" worktree add -q "$wt" -b "$branch" HEAD

  run bash "$CLEANUP" <<EOF
{"cwd": "${wt}"}
EOF
  [ "$status" -eq 0 ]
  [ ! -d "$wt" ]
  # The worktree branch should be deleted (it had no unmerged work).
  ! git -C "$REPO" branch --list "$branch" | grep -q "$branch"

  rm -rf "$managed_root"
}
