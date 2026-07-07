#!/usr/bin/env bash
set -euo pipefail

payload="$(cat)"
if [[ -z "$payload" ]]; then
  exit 0
fi

# Cheap pre-jq bail: every guard below acts ONLY on a `git` subcommand, so if the
# raw payload mentions no `git` at all there is nothing to inspect. This skips the
# jq spawn (the dominant per-call cost) for the common case — non-git Bash calls —
# on the PreToolUse hot path. It is a pure SUPERSET filter on the literal bytes
# (the token still has to survive the structured checks below), so it can never
# mask a command that jq + the matchers would have flagged.
case "$payload" in
  *git*) ;;
  *) exit 0 ;;
esac

# Parse the payload in a SINGLE jq pass (was two: command, then cwd). tool_input
# can be an object ({command:"..."}) OR a bare string; the naive
# `.tool_input.command // .tool_input` THROWS on a string ("Cannot index string
# with command") and, with stderr swallowed, leaves $command empty — silently
# bypassing every guard — so type-check first. We emit cwd on line 1 (a path
# never contains a newline) then the command as the remainder, so a multi-line
# command cannot bleed into cwd. No eval; bash-3.2 safe.
cwd=""
command=""
{
  IFS= read -r cwd || true
  command="$(cat)"
} < <(
  printf '%s' "$payload" | jq -j '
    (.cwd // "") + "\n" +
    (if (.tool_input | type) == "string" then .tool_input
     else (.tool_input.command // "") end)
  ' 2>/dev/null
)

if [[ -z "$command" || "$command" == "null" ]]; then
  exit 0
fi

# Directory the command runs in (for repo-state inspection). Both Claude and
# Codex put it in `.cwd`; fall back to $PWD when absent or not a directory.
[[ -n "$cwd" && "$cwd" != "null" && -d "$cwd" ]] || cwd="$PWD"

lowered="$(printf '%s' "$command" | tr '[:upper:]' '[:lower:]')"

# Decision helpers. The `2>/dev/null || true` guard before `exit 0` is
# load-bearing on BOTH: under `set -euo pipefail` a jq hiccup would otherwise
# exit the script NONZERO, which Codex's exit-code contract reads as a hard
# block. Emit best-effort, then exit 0 so the DECISION lives in the JSON, not
# the exit code (the repo's established cross-tool contract — same as
# subagent-worktree-guard and chezmoi-guard).

# deny: BLOCK the command. The reason is fed back to the model (Claude), which
# adapts and re-issues — no human is involved, so it does not stall auto mode.
# Reserved for operations that genuinely must not run as written: here, a
# destructive op whose target the guard cannot verify because it hides behind an
# unexpanded shell variable. (`ask` — the human-confirmation decision — is never
# emitted by this guard, as it WOULD stall a non-interactive run.)
deny() {
  jq -cn --arg reason "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}' 2>/dev/null || true
  exit 0
}

# warn: ALLOW the command but inject a RELEVANT advisory naming exactly what is
# at risk for this invocation. The command proceeds (auto mode handles it); the
# note just lets the agent confirm intent. Used for recoverable, intentional ops
# (reset --hard / checkout -- / restore / clean on a dirty tree, force push).
warn() {
  jq -cn --arg reason "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow",additionalContext:$reason}}' 2>/dev/null || true
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
      # Long global options that take a SEPARATE value token in SPACE form
      # (`--git-dir <path>`, `--work-tree <path>`, `--namespace <ns>`,
      # `--super-prefix <p>`). The `=value` inline forms are handled by the
      # generic `-*` branch below; here we must additionally consume the value
      # token (which may be quoted with spaces) so it is not mistaken for the
      # subcommand — otherwise `--git-dir 'a b' reset --hard` leaves `'a b'` as
      # the apparent subcommand and the reset/--hard match is lost.
      --git-dir[[:space:]]*|--work-tree[[:space:]]*|--namespace[[:space:]]*|--super-prefix[[:space:]]*|--exec-path[[:space:]]*)
        rest="$(strip_one_token "$rest")"          # drop the option token
        rest="${rest#"${rest%%[![:space:]]*}"}"   # drop spaces after the flag
        rest="$(strip_one_token "$rest")"          # drop the (quote-aware) value
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

# A THIRD view: the command with all single/double quote CHARACTERS removed, so a
# flag or value that was quoted (`reset '--hard'`, `checkout '--' f`, `clean '-f'`,
# or a `--git-dir 'a b'` whose inner space split the token) collapses to its bare
# form. Matching against this catches the quote-obfuscation class that breaks the
# `--hard([[:space:]]|$)`-style anchors on the raw `lowered`/`sub` views. (Quotes
# only ever wrap tokens here; removing them cannot fabricate a destructive verb.)
unquoted="$(printf '%s' "$lowered" | tr -d '"'"'")"
sub_unquoted="$(strip_git_prefix "$unquoted")"

# Leading `git` plus global options, when args are NOT quoted-with-spaces.
git='git([[:space:]]+-[^[:space:]]+([[:space:]]+[^[:space:]]+)?)*[[:space:]]+'

# match_sub <ere-without-git-prefix>
# True if the pattern matches the unquoted-prefix form OR the stripped-subcommand
# form, on EITHER the raw or the quote-collapsed view. The stripped forms have no
# leading `git`, so they are anchored at start.
match_sub() {
  local pat="$1"
  if [[ "$lowered" =~ ${git}${pat} ]]; then return 0; fi
  if [[ -n "$sub" && "$sub" =~ ^${pat} ]]; then return 0; fi
  if [[ "$unquoted" =~ ${git}${pat} ]]; then return 0; fi
  if [[ -n "$sub_unquoted" && "$sub_unquoted" =~ ^${pat} ]]; then return 0; fi
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
# fall through to the destructive branch (errs toward warn — safe).
restore_is_staged_only() {
  [[ "$lowered" =~ (^|[[:space:]])--staged([[:space:]]|$) ]] || return 1
  [[ "$lowered" =~ (^|[[:space:]])--worktree([[:space:]]|$) ]] && return 1
  return 0
}

# Does the command redirect git to a DIFFERENT repo/worktree through an
# UNEXPANDED shell variable or `~` — e.g. `git -C "$DIR" ...`,
# `git --git-dir=$X ...`, `git --work-tree=~/wt ...`? When it does, the guard
# cannot resolve WHICH working tree the destructive op will hit, so it cannot
# verify what is at risk. Policy: deny and have the agent resolve the variable
# to a literal first (so the target is auditable) rather than guess. Tested on
# the original case-preserving $command so `-C` is not confused with `-c`.
redirect_target_unverifiable() {
  # The redirect VALUE may be a quoted path that contains spaces (e.g.
  # `-C 'sp $D'`, `--git-dir='a b/$X'`), so the `$`/`~` we care about can sit
  # PAST an internal space. The earlier `[^[:space:]]*[\$~]` form stopped at the
  # first space and missed it. Instead, after the flag, allow any run of
  # non-quote, non-separator characters (which MAY include spaces) up to a `$`
  # or `~`. `[^'"\;&|]` keeps the scan inside a single (quoted or bare) argument
  # without crossing into the next command or a closing quote+space boundary.
  local val="[^\"'\\;&|]*[\$~]"
  # -C <value> (space form; the value token follows the flag).
  if [[ "$command" =~ (^|[[:space:]])-C[[:space:]]+[\"\']?${val} ]]; then
    return 0
  fi
  # --git-dir / --work-tree, in `=value` or ` value` form.
  if [[ "$command" =~ (^|[[:space:]])--git-dir[[:space:]=][\"\']?${val} ]] \
    || [[ "$command" =~ (^|[[:space:]])--work-tree[[:space:]=][\"\']?${val} ]]; then
    return 0
  fi
  return 1
}

# ---------------------------------------------------------------------------
# Locked policy: this guard NEVER hard-blocks. Every git op it covers loses at
# most uncommitted/local/remote-rewritable state — all recoverable in the sense
# that matters (no machine-wide, unrecoverable destruction like `rm -rf /`). So:
#   * reset --hard, push --force, checkout --, restore, clean -f  -> NON-BLOCKING
#     WARN, and only when this specific invocation would actually lose work
#     (dirty tree / real force). A no-loss invocation passes SILENTLY.
#   * branch -D, tag -d, stash drop/clear, worktree remove --force are DROPPED
#     entirely: all are reflog/gc-recoverable, so auto mode just handles them.
# A warn names exactly what is at risk for THIS command (relevance) and exits 0.
#
# EXCEPTION — unverifiable target: when one of these destructive ops is pointed
# at another tree through an UNEXPANDED variable (`git -C "$DIR" reset --hard`,
# `--git-dir=$X`, `--work-tree=~/wt`), the guard cannot see which tree will be
# hit, so it cannot judge the risk. That case DENIES (block + tell the agent to
# resolve the variable to a literal path first) — the agent re-issues an
# auditable command with no human involved.
# ---------------------------------------------------------------------------

# Patterns for the destructive subcommands this guard covers. A redirect through
# an unexpanded variable is only a problem when one of these actually runs.
reset_hard_pat='reset([[:space:]]+[^[:space:]]+)*[[:space:]]+--hard([[:space:]]|$)'
checkout_dd_pat='checkout([[:space:]]+[^[:space:]]+)*[[:space:]]+--([[:space:]]|$)'
restore_pat='restore([[:space:]]|$)'
clean_force_pat='clean([[:space:]]+[^[:space:]]+)*[[:space:]]+(--force|-[a-z]*f[a-z]*)([[:space:]]|$)'

# Deny FIRST when a DESTRUCTIVE op rides on an unverifiable (variable/~) target.
# A `restore --staged` (without --worktree) only unstages the index and is fully
# reversible no matter which tree it points at, so it is NOT destructive and must
# be excluded from this deny (else `git -C "$D" restore --staged f` false-denies).
if redirect_target_unverifiable \
  && { match_sub "$reset_hard_pat" || match_sub "$checkout_dd_pat" \
       || { match_sub "$restore_pat" && ! restore_is_staged_only; } \
       || match_sub "$clean_force_pat"; }; then
  deny "blocked by GS-2 (no destructive op via unexpanded variable): this destructive git op targets another working tree through an unexpanded shell variable or '~' (e.g. -C \"\$DIR\" / --git-dir=\$X / --work-tree=~/...), so the guard cannot verify which tree's uncommitted work it would discard. Re-run with the variable resolved to a literal path (e.g. run \`echo \"\$DIR\"\` first, then pass the actual path) so the target is auditable."
fi

# `--hard` may appear ANYWHERE in the reset invocation, not only immediately
# after `reset`: `git reset --hard`, `git reset HEAD --hard`,
# `git reset --hard HEAD~3`, `git reset --soft --hard`, ... The leading
# `([[:space:]]+[^[:space:]]+)*` consumes zero-or-more intervening tokens, so
# both the immediate and the trailing-flag forms are caught.
#
# Only warn when work would actually be lost: a dirty tracked tree (or an
# undeterminable state). A clean tracked tree means `reset --hard` discards
# nothing, so it passes silently.
if match_sub "$reset_hard_pat"; then
  if uncommitted_work_at_risk; then
    warn "GS-3 (warn: reset --hard discards uncommitted tracked changes): the working tree has uncommitted changes to tracked files (staged + unstaged) that will be permanently discarded and are NOT in the reflog. Commit or stash them first if you need them. Proceeding."
  fi
fi

# Force push rewrites only REMOTE history (remote-rewritable, not machine-
# destructive), so it is a non-blocking warn rather than a hard block.
if match_sub 'push([[:space:]]+[^[:space:]]+)*[[:space:]]+(--force-with-lease|--force|-f)([[:space:]=]|$)'; then
  warn "GS-4 (warn: force push rewrites remote history): git push --force/--force-with-lease rewrites the remote branch history and can overwrite commits pushed by others. Verify the remote ref is what you expect before proceeding. Proceeding."
fi

# ---------------------------------------------------------------------------
# Recoverable working-tree ops: warn (only when work is at risk), never block.
# ---------------------------------------------------------------------------

# `git checkout -- <path>` discards uncommitted worktree changes to those paths
# (old-style equivalent of `restore --worktree`). Only an uncommitted change is
# at risk — committed content is recoverable — so warn only when the tree is
# dirty (or its state is undeterminable); a clean tree loses nothing.
if match_sub "$checkout_dd_pat"; then
  if uncommitted_work_at_risk; then
    warn "GS-5 (warn: checkout -- discards uncommitted changes): git checkout -- <path> discards uncommitted working-tree changes to the named paths (gone for good, not recoverable from the reflog). Proceeding."
  fi
fi

# `git restore` matched at command position (subcommand form only — not a stray
# `--source`/`--staged` appearing in some other command's args).
if match_sub "$restore_pat"; then
  # --staged WITHOUT --worktree only unstages the index; the working tree is
  # untouched and it is fully reversible — always allow silently. Any form that
  # touches the working tree (default, or explicit --worktree) discards
  # uncommitted changes, so warn only when those changes actually exist.
  if ! restore_is_staged_only && uncommitted_work_at_risk; then
    warn "GS-5 (warn: restore discards uncommitted changes): git restore (working tree) discards uncommitted changes to the named paths (not recoverable from the reflog). Proceeding."
  fi
fi

# Destructive git clean. Force is requested via --force OR a flag cluster that
# contains `f` in ANY ordering: -f, -df, -fd, -xdf, -dfx, ... Match a cluster of
# lowercase short flags that includes an `f`. Stay SILENT when there is nothing
# untracked to remove (a clean clean loses nothing).
if match_sub "$clean_force_pat"; then
  # If `clean -nd` (dry-run) prints nothing, there are no untracked files to
  # delete -> pass silently. Any output (or an undeterminable state) -> warn.
  clean_preview="$(git -C "$cwd" clean -nd 2>/dev/null || printf '%s' "UNDETERMINABLE")"
  if [[ -n "$clean_preview" ]]; then
    warn "GS-6 (warn: clean -f deletes untracked files): git clean -f permanently deletes untracked files in the working tree (with -x, also ignored files); they are not recoverable. Proceeding."
  fi
fi

# branch -D, tag -d, stash drop/clear, and worktree remove --force are
# intentionally NOT guarded: each only removes a ref or a stash entry, while the
# underlying commits/objects stay reachable via the reflog (and survive until
# gc), so the operation is recoverable. Auto mode handles them.

exit 0
