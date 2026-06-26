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

# Directory the command runs in (for repo-state inspection). Both Claude and
# Codex put it in `.cwd`; fall back to $PWD when absent or not a directory.
cwd="$(printf '%s' "$payload" | jq -r '.cwd // empty' 2>/dev/null || true)"
[[ -n "$cwd" && "$cwd" != "null" && -d "$cwd" ]] || cwd="$PWD"

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

# Would an operation that discards uncommitted TRACKED changes in $cwd actually
# lose work? Shared by `reset --hard`, `restore` (worktree), and `checkout --`.
#
# All three only ever destroy uncommitted changes to tracked files (staged +
# unstaged) — those are gone for good, not in the reflog. Committed content is
# always recoverable, untracked files are untouched, and a `reset --hard` ref
# move stays reflog-recoverable. So the only irreversible loss is a dirty
# tracked tree.
#
# Returns 0 (true, "work would be lost") when the tracked tree is dirty OR when
# we cannot determine the state — fail CLOSED, because the entire purpose of the
# guard is to never silently allow an unrecoverable loss. Returns 1 only when we
# positively confirm a clean tracked tree (untracked-only is clean enough).
uncommitted_work_at_risk() {
  local root status
  # If the command redirects git to a DIFFERENT repo/worktree (-C <path>,
  # --git-dir=, --work-tree=), $cwd is not the repo being acted on and we cannot
  # trust its state. Lowercasing already collapsed `-C` into `-c`, so detect on
  # the original (case-sensitive) command. Undeterminable target → fail closed.
  case " $command " in
    *" -C "*) return 0 ;;
  esac
  if [[ "$command" =~ (^|[[:space:]])--git-dir([[:space:]=]) ]] \
    || [[ "$command" =~ (^|[[:space:]])--work-tree([[:space:]=]) ]]; then
    return 0
  fi

  # Must be inside a work tree; if not (or git is unavailable), fail closed.
  root="$(git -C "$cwd" rev-parse --is-inside-work-tree 2>/dev/null || true)"
  [[ "$root" == "true" ]] || return 0

  # Porcelain v1 with -uno: list only tracked changes (untracked files are
  # excluded by -uno, so an untracked-only working dir reports clean). Any line
  # of output means staged and/or unstaged tracked changes exist → would lose.
  if ! status="$(git -C "$cwd" status --porcelain -uno 2>/dev/null)"; then
    return 0   # status failed — cannot confirm clean, fail closed
  fi
  [[ -n "$status" ]]
}

# Is this `git restore` STAGED-ONLY — i.e. it only unstages the index and never
# touches the working tree? `git restore --staged <path>` moves staged→unstaged
# (reverse of `git add`); the working tree is untouched and it is fully
# reversible, so it is always safe. The working tree IS affected when --worktree
# is given, or when --staged is absent (worktree is restore's default). Short
# flags (-S/-W) collapse ambiguously under lowercasing (-S→-s collides with
# --source's -s), so we classify on the long forms and let any short-flag form
# fall through to the destructive branch (errs toward ask — safe).
restore_is_staged_only() {
  [[ "$lowered" =~ (^|[[:space:]])--staged([[:space:]]|$) ]] || return 1
  [[ "$lowered" =~ (^|[[:space:]])--worktree([[:space:]]|$) ]] && return 1
  return 0
}

# ---------------------------------------------------------------------------
# HARD DENY (locked policy): only truly unrecoverable operations.
#   * git reset --hard  (destroys uncommitted work) — but ONLY when the tracked
#     tree is dirty, since a clean reset --hard loses nothing
#   * git push --force / --force-with-lease / -f  (rewrites remote history)
# ---------------------------------------------------------------------------

# `--hard` may appear ANYWHERE in the reset invocation, not only immediately
# after `reset`: `git reset --hard`, `git reset HEAD --hard`,
# `git reset --hard HEAD~3`, `git reset --soft --hard`, ... The leading
# `([[:space:]]+[^[:space:]]+)*` consumes zero-or-more intervening tokens, so
# both the immediate and the trailing-flag forms are caught.
#
# Only block when work would actually be lost: a dirty tracked tree (or an
# undeterminable state). A clean tracked tree means `reset --hard` discards
# nothing unrecoverable, so it is allowed through.
if match_sub 'reset([[:space:]]+[^[:space:]]+)*[[:space:]]+--hard([[:space:]]|$)'; then
  if uncommitted_work_at_risk; then
    deny "refusing git reset --hard: the working tree has uncommitted changes to tracked files that would be permanently lost. Commit or stash them first."
  fi
fi

# Force push rewrites remote history and can destroy other people's commits —
# locked policy classifies this as a hard deny.
if match_sub 'push([[:space:]]+[^[:space:]]+)*[[:space:]]+(--force-with-lease|--force|-f)([[:space:]=]|$)'; then
  deny "refusing git force push (hard block: rewrites remote history, can destroy commits)"
fi

# ---------------------------------------------------------------------------
# ASK (recoverable ops): confirm before running.
# ---------------------------------------------------------------------------

# `git checkout -- <path>` discards uncommitted worktree changes to those paths
# (old-style equivalent of `restore --worktree`). Only an uncommitted change is
# at risk — committed content is recoverable — so ask only when the tree is
# dirty (or its state is undeterminable); a clean tree loses nothing.
if match_sub 'checkout([[:space:]]+[^[:space:]]+)*[[:space:]]+--([[:space:]]|$)'; then
  if uncommitted_work_at_risk; then
    ask "git checkout -- discards uncommitted changes to the named paths — confirm to proceed."
  fi
fi

# `git restore` matched at command position (subcommand form only — not a stray
# `--source`/`--staged` appearing in some other command's args).
if match_sub 'restore([[:space:]]|$)'; then
  # --staged WITHOUT --worktree only unstages the index; the working tree is
  # untouched and it is fully reversible — always allow. Any form that touches
  # the working tree (default, or explicit --worktree) discards uncommitted
  # changes, so ask only when those changes actually exist.
  if ! restore_is_staged_only && uncommitted_work_at_risk; then
    ask "git restore discards uncommitted changes to the named paths — confirm to proceed."
  fi
fi

# Destructive git clean. Force is requested via --force OR a flag cluster that
# contains `f` in ANY ordering: -f, -df, -fd, -xdf, -dfx, ... Match a cluster of
# lowercase short flags that includes an `f`.
if match_sub 'clean([[:space:]]+[^[:space:]]+)*[[:space:]]+(--force|-[a-z]*f[a-z]*)([[:space:]]|$)'; then
  ask "destructive git clean removes untracked files — confirm to proceed."
fi

# Branch deletion. `git branch -d`/`--delete` is the SAFE, merge-checked delete:
# git refuses it unless the branch is fully merged, so the commits stay
# reachable elsewhere — allow silently. Only a FORCE delete (`-D`, or
# `--delete --force`/`-df`) removes a possibly-unmerged branch, so ask on that.
# -d and -D differ ONLY by case, which the lowercased view collapses, so detect
# force on the original case-preserving $command (as the -C check does).
if match_sub 'branch[[:space:]]+(--delete|-[a-z]*d[a-z]*)([[:space:]]|$)'; then
  if [[ "$command" =~ (^|[[:space:]])-[a-zA-Z]*[Df][a-zA-Z]*([[:space:]]|$) ]] \
    || [[ "$command" =~ (^|[[:space:]])--force([[:space:]]|$) ]]; then
    ask "git branch force-deletion removes a possibly-unmerged branch — confirm to proceed."
  fi
fi

if match_sub 'stash[[:space:]]+(drop|clear)'; then
  ask "git stash drop/clear permanently discards stashed work — confirm to proceed."
fi

if match_sub 'tag([[:space:]]+[^[:space:]]+)*[[:space:]]+(-d|--delete)([[:space:]]|$)'; then
  ask "git tag deletion — confirm to proceed."
fi

# git worktree remove refuses to delete a worktree with uncommitted or untracked
# changes UNLESS --force, so the plain form is safe — allow it. Only the force
# form can discard uncommitted work, so ask on --force/-f.
if match_sub 'worktree[[:space:]]+remove([[:space:]]|$)'; then
  if [[ "$command" =~ (^|[[:space:]])(--force|-[a-zA-Z]*f[a-zA-Z]*)([[:space:]]|$) ]]; then
    ask "git worktree remove --force discards any uncommitted changes in that worktree — confirm to proceed."
  fi
fi

exit 0
