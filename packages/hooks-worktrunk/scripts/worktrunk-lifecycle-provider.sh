#!/usr/bin/env bash
#
# WorktreeCreate / WorktreeRemove provider: route the harness's native worktree
# lifecycle through Worktrunk.
#
# STOPGAP. The official Worktrunk plugin registers both events upstream, but the
# release installed today (v1.0.0) declares only Notification, SessionEnd and
# UserPromptSubmit. Once an installed plugin version registers them, this script
# is redundant -- and two providers race, because the harness takes the first
# hook printing a non-empty path. Check the installed plugin's
# hooks/hooks.json before assuming this is still needed.
#
# Modelled on the upstream implementation at
# ~/.claude/plugins/cache/worktrunk/worktrunk/d422b1b9be26/hooks/hooks.json,
# which the eventual plugin update will also ship.
#
# Neither event carries permissionDecision, so neither can deny. WorktreeCreate
# must print the created path on stdout; WorktreeRemove exits non-zero only to
# abort the removal.
set -euo pipefail

payload="$(cat || true)"
[[ -z "$payload" ]] && exit 0

command -v wt >/dev/null 2>&1 || exit 0

event="$(printf '%s' "$payload" | jq -r '.hook_event_name // empty')"

case "$event" in
  WorktreeCreate)
    # `.name` is the only identifier the harness sends. The retired
    # hooks-worktree script read `.worktree_name`/`.git_ref`, which never exist.
    name="$(printf '%s' "$payload" | jq -er '.name')"
    wt switch --create "$name" --no-cd --format=json | jq -er '.path'
    ;;
  WorktreeRemove)
    path="$(printf '%s' "$payload" | jq -er '.worktree_path')"
    wt remove --foreground "$path"
    ;;
  *)
    exit 0
    ;;
esac
