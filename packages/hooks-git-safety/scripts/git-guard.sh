#!/usr/bin/env bash
set -euo pipefail

payload="$(cat)"
if [[ -z "$payload" ]]; then
  exit 0
fi

# tool_input can be an object ({command:"..."}) OR a bare string. The naive
# `.tool_input.command // .tool_input` form THROWS on a string ("Cannot index
# string with command") and, with stderr swallowed, leaves $command empty —
# silently bypassing every guard. Type-check first so both shapes are read.
command="$(
  printf '%s' "$payload" | jq -r '
    if (.tool_input | type) == "string" then .tool_input
    else (.tool_input.command // empty)
    end
  ' 2>/dev/null || true
)"

if [[ -z "$command" || "$command" == "null" ]]; then
  exit 0
fi

lowered="$(printf '%s' "$command" | tr '[:upper:]' '[:lower:]')"

# Hard reject: the operation is refused outright.
deny() {
  jq -cn --arg reason "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}'
  exit 0
}

# Soft block: surface the reason and require the user to confirm before running.
ask() {
  jq -cn --arg reason "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$reason}}'
  exit 0
}

# Strip ONE shell-ish token off the front of $1, quote-aware, and print the
# remainder. A token runs until the first UNQUOTED whitespace; embedded single-
# or double-quoted segments (which may contain spaces) are consumed whole. This
# correctly skips `'/path with space'`, `"x y"`, `user.name='A B'`, and plain
# tokens. (BSD/bash-3.2 safe: only `case` globbing + parameter expansion.)
strip_one_token() {
  local s="$1" chunk
  while [[ -n "$s" ]]; do
    case "$s" in
      [[:space:]]*) break ;;            # unquoted whitespace ends the token
      \'*)                              # single-quoted segment
        s="${s#\'}"
        s="${s#*\'}"
        ;;
      \"*)                              # double-quoted segment
        s="${s#\"}"
        s="${s#*\"}"
        ;;
      *)                                # run of bare chars up to space/quote
        chunk="${s%%[[:space:]\'\"]*}"
        if [[ -z "$chunk" ]]; then
          # Defensive: nothing consumable; drop one char to avoid a stall.
          s="${s#?}"
        else
          s="${s#"$chunk"}"
        fi
        ;;
    esac
  done
  printf '%s' "$s"
}

# Strip a leading `git` token plus any global options before the subcommand.
#
# We cannot model quoted/spaced global-option arguments (e.g.
# `git -C '/path with space' reset --hard`) inside one ERE, so instead we peel
# tokens off the front one at a time, then match the subcommand on whatever
# remains. This neutralises the `-C <spaced path>` bypass.
#
# Returns the remainder (subcommand + its args) on stdout, lowercased.
strip_git_prefix() {
  local rest="$1"
  local before

  # Trim leading whitespace.
  rest="${rest#"${rest%%[![:space:]]*}"}"

  # Must start with the `git` token (word boundary: space or end after it).
  case "$rest" in
    git|git[[:space:]]*) ;;
    *) printf '%s' ""; return 0 ;;
  esac
  rest="${rest#git}"
  rest="${rest#"${rest%%[![:space:]]*}"}"

  # Peel leading global options until we reach the subcommand (a token that does
  # NOT start with `-`). `-c`/`-C` take a SEPARATE following argument token that
  # may be single/double quoted (and therefore contain spaces).
  while :; do
    before="$rest"
    case "$rest" in
      # -c / -C with a SEPARATE argument token (`-C <path>`, `-c name=value`).
      # After lowercasing both `-C` and `-c` appear as `-c`.
      -c[[:space:]]*)
        rest="${rest#-c}"
        rest="${rest#"${rest%%[![:space:]]*}"}"   # drop spaces after the flag
        rest="$(strip_one_token "$rest")"          # drop the (quote-aware) arg
        rest="${rest#"${rest%%[![:space:]]*}"}"   # drop trailing spaces
        ;;
      # Any other leading option token (--bare, -p, --no-pager, --git-dir=...,
      # --work-tree=..., --paginate, ...). These carry no separate arg token,
      # but an inline value may be quoted/spaced (--git-dir='/a b'), so strip it
      # quote-aware too.
      -*)
        rest="$(strip_one_token "$rest")"          # drop the option token
        rest="${rest#"${rest%%[![:space:]]*}"}"   # drop following spaces
        ;;
      # Subcommand reached (or empty).
      *)
        break
        ;;
    esac
    # Guard against a token we could not consume (avoid an infinite loop).
    if [[ "$rest" == "$before" ]]; then
      break
    fi
  done

  printf '%s' "$rest"
}

# The token-peeling loop above is intentionally conservative. To keep behaviour
# robust we build TWO views of the command and match guards against either:
#   1) the raw lowered command (catches the common, unquoted invocations); and
#   2) a "subcommand" view with the git prefix + quoted global-opt args removed
#      (catches `git -C '/spaced path' <subcmd>` bypasses).
sub="$(strip_git_prefix "$lowered")"

# Leading `git` plus global options, when args are NOT quoted-with-spaces.
git='git([[:space:]]+-[^[:space:]]+([[:space:]]+[^[:space:]]+)?)*[[:space:]]+'

# match_sub <ere-without-git-prefix>
# True if the pattern matches the unquoted-prefix form OR the stripped-subcommand
# form. The stripped form has no leading `git`, so it is anchored at start.
match_sub() {
  local pat="$1"
  if [[ "$lowered" =~ ${git}${pat} ]]; then
    return 0
  fi
  if [[ -n "$sub" && "$sub" =~ ^${pat} ]]; then
    return 0
  fi
  return 1
}

# ---------------------------------------------------------------------------
# HARD DENY (locked policy): only truly unrecoverable operations.
#   * git reset --hard  (destroys uncommitted work, no per-file confirmation)
#   * git push --force / --force-with-lease / -f  (rewrites remote history)
# ---------------------------------------------------------------------------

# `--hard` may appear ANYWHERE in the reset invocation, not only immediately
# after `reset`: `git reset --hard`, `git reset HEAD --hard`,
# `git reset --hard HEAD~3`, `git reset --soft --hard`, ... The leading
# `([[:space:]]+[^[:space:]]+)*` consumes zero-or-more intervening tokens, so
# both the immediate and the trailing-flag forms are caught.
if match_sub 'reset([[:space:]]+[^[:space:]]+)*[[:space:]]+--hard([[:space:]]|$)'; then
  deny "refusing git reset --hard (hard block: destroys uncommitted work)"
fi

# Force push rewrites remote history and can destroy other people's commits —
# locked policy classifies this as a hard deny.
if match_sub 'push([[:space:]]+[^[:space:]]+)*[[:space:]]+(--force-with-lease|--force|-f)([[:space:]=]|$)'; then
  deny "refusing git force push (hard block: rewrites remote history, can destroy commits)"
fi

# ---------------------------------------------------------------------------
# ASK (recoverable ops): confirm before running.
# ---------------------------------------------------------------------------

if match_sub 'checkout([[:space:]]+[^[:space:]]+)*[[:space:]]+--([[:space:]]|$)'; then
  ask "git checkout -- discards local changes to the named paths — confirm to proceed."
fi

if match_sub 'restore([[:space:]].*)?(--staged|--worktree|--source)'; then
  ask "git restore can discard local changes — confirm to proceed."
fi

# Destructive git clean. Force is requested via --force OR a flag cluster that
# contains `f` in ANY ordering: -f, -df, -fd, -xdf, -dfx, ... Match a cluster of
# lowercase short flags that includes an `f`.
if match_sub 'clean([[:space:]]+[^[:space:]]+)*[[:space:]]+(--force|-[a-z]*f[a-z]*)([[:space:]]|$)'; then
  ask "destructive git clean removes untracked files — confirm to proceed."
fi

# Branch deletion: --delete, or a short-flag cluster containing `d`/`D`
# (lowercased to `d`): -d, -D, -dr, ... `--delete`/`--merged` etc. are excluded
# because the cluster form is single-dash only.
if match_sub 'branch[[:space:]]+(--delete|-[a-z]*d[a-z]*)([[:space:]]|$)'; then
  ask "git branch deletion — confirm to proceed."
fi

if match_sub 'stash[[:space:]]+(drop|clear)'; then
  ask "git stash drop/clear permanently discards stashed work — confirm to proceed."
fi

if match_sub 'tag([[:space:]]+[^[:space:]]+)*[[:space:]]+(-d|--delete)([[:space:]]|$)'; then
  ask "git tag deletion — confirm to proceed."
fi

if match_sub 'worktree[[:space:]]+remove([[:space:]]|$)'; then
  ask "git worktree remove deletes the worktree checkout — confirm to proceed."
fi

exit 0
