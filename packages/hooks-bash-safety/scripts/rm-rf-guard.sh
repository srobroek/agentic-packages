#!/usr/bin/env bash
set -euo pipefail

# rm-rf-guard.sh — PreToolUse:Bash guard for `rm -rf` (cross-tool).
#
# Goal: MINIMAL impediment. Recoverability model: anything INSIDE the project's
# git working tree is assumed recoverable (it's in git), so wiping it passes
# SILENTLY — node_modules, dist, ./build, target, a nested subdir, even an
# absolute path that resolves back inside the repo. Only targets that leave that
# safety net get scrutiny.
#
#   DENY  — unrecoverable regardless of git: a system-critical directory as a
#           WHOLE TREE (/, /usr, /etc, /var, ...) or the home directory.
#   ASK   — recoverable-but-worth-a-glance: a path OUTSIDE the working tree, the
#           repo root or its .git dir (wiping those defeats the in-git
#           assumption), an unresolved $var (an empty var expands to /), or a
#           ~/home path.
#   ALLOW — resolves strictly inside the project working tree, or a temp root.

input="$(cat)"

# Cheap pre-jq bail: this guard only ever fires on `rm`. The pattern matches the
# RAW payload string (a superset of real triggers — JSON-escaping never hides the
# literal `rm`), so we skip the jq spawn entirely on the overwhelming majority of
# Bash calls that contain no `rm` at all.
case "$input" in
  *rm*) ;;
  *) exit 0 ;;
esac

# tool_input may be an object ({command:"..."}) OR a bare string. The naive
# `.tool_input.command // .tool_input` form THROWS on a string input (jq cannot
# index a string), which would silently bypass this guard. Branch on type.
#
# ONE jq spawn yields both fields via a merged parse: .cwd on line 1 (a path has
# no newline) and the command as the remainder, so a multi-line command cannot
# bleed into the cwd field.
cwd=""
command=""
{
  IFS= read -r cwd || true
  command="$(cat)"
} < <(
  printf '%s' "$input" | jq -j '
    (.cwd // "") + "\n" +
    (if (.tool_input|type)=="string" then .tool_input
     else (.tool_input.command // "") end)
  ' 2>/dev/null
)

[[ -z "$command" || "$command" == "null" ]] && exit 0

# Working directory the command runs in (both Claude and Codex send .cwd); fall
# back to $PWD. Canonicalize to the PHYSICAL path (resolve symlinks) so it agrees
# with git's --show-toplevel, which is always canonical — otherwise on macOS the
# raw /tmp/x cwd vs canonical /private/tmp/x root would never share a prefix and
# every relative target would read as "outside the tree".
[[ -n "$cwd" && "$cwd" != "null" && -d "$cwd" ]] || cwd="$PWD"
cwd="$(cd "$cwd" 2>/dev/null && pwd -P 2>/dev/null || printf '%s' "$cwd")"
cwd="${cwd%/}"; [[ -z "$cwd" ]] && cwd="/"
# Project root = git working-tree top (canonical). If not a git repo, the working
# dir itself is the root.
root="$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null || true)"
[[ -n "$root" ]] || root="$cwd"
root="${root%/}"; [[ -z "$root" ]] && root="/"

# Find an `rm` invocation whose flags include both recursive and force, in any
# form: -rf, -fr, -r -f, combined with other letters (-rfv), or the long
# options --recursive/--force.
#
# Capture the first `rm` COMMAND-SEGMENT: an `rm` at command position plus every
# token up to the next `; & |` separator. Command position is the start of the
# string OR right after a separator, in BOTH cases allowing:
#   * leading horizontal whitespace / tabs (`  rm -rf /`, a leading-tab form), and
#   * leading command WRAPPERS and ENV-ASSIGNMENTS that keep `rm` at command
#     position: `sudo`/`doas`/`env`/`time`/`nice`/`command`/`exec`/`xargs` and
#     any number of `NAME=value` assignments (`FOO=bar rm -rf /`).
# This closes the prefix-bypass class (sudo/env/leading-space defeating a bare
# `^rm`) while the separator anchor still keeps a quoted/echoed `rm -rf /` inside
# another command's argument from matching.
# Each wrapper may carry option tokens, and an option may take a SEPARATE value
# token (`nice -n 19`, `ionice -c 3`, `doas -u root`, `sudo -u root`). So after
# each `-opt` we allow ONE optional bare (non-dash) value token. The value is
# OPTIONAL, so when the following token is actually `rm` the engine simply does
# not consume it as a value and the required `rm` literal still matches — without
# this, the value (`19`/`3`/`root`) was left where `rm` was expected and the whole
# match failed, silently letting a wrapper-prefixed `rm -rf /` through.
_wrap='(sudo|doas|env|time|nice|command|exec|xargs|stdbuf|nohup|setsid|ionice)[[:space:]]+(-[^[:space:]]+[[:space:]]+([^-][^[:space:]]*[[:space:]]+)?)*'
_envasgn='([A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*[[:space:]]+)*'
rm_args="$(printf '%s' "$command" | grep -oE "(^|[;&|])[[:space:]]*(${_envasgn}|${_wrap})*rm[[:space:]]+[^;&|]*" | head -n1 || true)"
[[ -z "$rm_args" ]] && exit 0

# Tokenize on ALL whitespace (space, tab) — not just space — so a tab-separated
# `rm<TAB>-rf<TAB>/` still isolates the flags and targets.
flags="$(printf '%s' "$rm_args" | tr '[:space:]' '\n' | grep -E '^-' || true)"
has_r=false
has_f=false
# bash 3.2 has no `;;&` case fallthrough, so detect r and f with independent
# tests. Short flags may be bundled (-rf, -fr, -rfv); long flags are spelled out.
while IFS= read -r flag; do
  [[ -z "$flag" ]] && continue
  case "$flag" in
    --recursive) has_r=true ;;
    --force) has_f=true ;;
    --*) ;; # other long options carry no r/f meaning
    -*)
      # Bundled short option group, e.g. -rf or -rfv. Test each letter
      # independently — a single flag can supply both r and f.
      [[ "$flag" == *r* ]] && has_r=true
      [[ "$flag" == *f* ]] && has_f=true
      ;;
  esac
done <<<"$flags"

if [[ "$has_r" != true || "$has_f" != true ]]; then
  exit 0
fi

# Everything after `rm` that is not an option = the target paths. Strip the
# command-position prefix (separator + leading whitespace + wrappers/env-assigns)
# up to and including the `rm` token, then tokenize on all whitespace.
targets="$(printf '%s' "$rm_args" | sed -E "s/^[;&|]?[[:space:]]*(${_envasgn}|${_wrap})*rm[[:space:]]+//" | tr '[:space:]' '\n' | grep -vE '^-' || true)"
display_targets="$(printf '%s' "$targets" | tr '\n' ' ' | sed 's/[[:space:]]*$//')"

# Emit a decision and exit. We emit only "deny" (block; reason fed to the model,
# which re-issues — no human, so it works in auto mode) or "allow" + a relevant
# additionalContext (a non-blocking warn). We deliberately never emit "ask": that
# waits for a HUMAN and would stall a non-interactive run. The `2>/dev/null ||
# true` before exit 0 keeps a jq hiccup from exiting NONZERO (a Codex block).
decide() {
  # $1 = deny|warn, $2 = reason/context
  case "$1" in
    deny)
      jq -cn --arg reason "$2" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}' 2>/dev/null || true
      ;;
    warn)
      jq -cn --arg ctx "$2" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow",additionalContext:$ctx}}' 2>/dev/null || true
      ;;
  esac
  exit 0
}

# Critical top-level directories whose WHOLE-TREE deletion is unrecoverable.
CRIT="/usr /etc /bin /sbin /lib /lib64 /var /opt /root /boot /dev /proc /sys /System /Library /Applications /private /Users"

# norm_abs <path> -> absolute, lexically-normalized path resolved against $cwd.
# PURE-LEXICAL: never touches the filesystem (the target may be about to be
# deleted, and following symlinks could be wrong). Resolves `.` and `..`
# textually, so `../inside-root` correctly normalizes back inside the tree.
norm_abs() {
  local p="$1" abs comp out=""
  case "$p" in
    /*) abs="$p" ;;
    *)  abs="$cwd/$p" ;;
  esac
  local -a parts=()
  # Split on '/' only for this read; read never globs, so a literal '*' in the
  # path (e.g. dist/*) is preserved as an ordinary component.
  IFS=/ read -r -a parts <<<"$abs"
  if [[ ${#parts[@]} -gt 0 ]]; then
    for comp in "${parts[@]}"; do
      case "$comp" in
        ''|.) ;;                 # skip empty (from // or leading /) and '.'
        ..)  out="${out%/*}" ;;  # pop the last segment
        *)   out="$out/$comp" ;;
      esac
    done
  fi
  [[ -z "$out" ]] && out="/"
  printf '%s' "$out"
}

# severity <target> -> echoes deny|ask|allow for ONE literal (unexpanded) token.
# Targets come from the JSON command string and are never shell-expanded, so
# `rm -rf /*` arrives as the token `/*`, `$HOME` arrives literally, etc.
severity() {
  local t="$1" d crit_glob abs
  [[ -z "$t" ]] && { echo allow; return; }

  # Strip ONE matched pair of surrounding quotes so a quoted target classifies
  # the same as the bare form. Without this, `rm -rf "/etc"` / `rm -rf '/'` keep
  # their quote chars, miss the exact-root case below, and slip through as allow
  # (a confirmed catastrophic bypass).
  case "$t" in
    \"*\") t="${t#\"}"; t="${t%\"}" ;;
    \'*\') t="${t#\'}"; t="${t%\'}" ;;
  esac
  [[ -z "$t" ]] && { echo allow; return; }

  # Catastrophic exact roots / home — unrecoverable. Checked BEFORE the generic
  # "$" rule below so the known-bad $HOME/${HOME}/~ forms deny. The quoted '~' /
  # '$HOME' patterns match the LITERAL unexpanded tokens from the JSON command
  # string; expanding them (SC2088/SC2016) would break the match.
  # shellcheck disable=SC2088,SC2016
  case "$t" in
    /|//|'/*'|'~'|'~/'|'$HOME'|'${HOME}'|"$HOME"|'$home'|'${home}')
      echo deny; return ;;
  esac

  # Whole-tree deletion of a critical system dir: the dir itself, dir/, or
  # dir/* (literal token). Quoted-RHS [[ == ]] forces a LITERAL compare, so a
  # deeper path like /var/folders/x falls through (handled below), not denied.
  for d in $CRIT; do
    crit_glob="$d/*"
    if [[ "$t" == "$d" || "$t" == "$d/" || "$t" == "$crit_glob" ]]; then
      echo deny; return
    fi
  done

  # Path-traversal / redundant-syntax catastrophes: a token like `/etc/..`,
  # `/usr/../etc`, `////`, `/.`, `/./`, or `/etc/.` is not LITERALLY `/` or a CRIT
  # dir, but NORMALIZES to one. Re-run the catastrophic checks against the
  # lexically-normalized absolute path so the raw comparisons above cannot be
  # dodged with `..`, `.`, or doubled-slash segments. Gate on any token that
  # could normalize differently — it contains `..`, a `.` path segment, or a
  # doubled slash — and has no `$` (variables are handled below). norm_abs is
  # pure-lexical (no FS access).
  if [[ "$t" != *'$'* && ( "$t" == *..* || "$t" == */. || "$t" == */./* || "$t" == *//* ) ]]; then
    local nabs; nabs="$(norm_abs "$t")"
    if [[ "$nabs" == "/" ]]; then echo deny; return; fi
    for d in $CRIT; do
      if [[ "$nabs" == "$d" ]]; then echo deny; return; fi
    done
  fi

  # An UNRESOLVED variable expansion ($DIR, ${DIR}, and any token containing $):
  # the guard cannot see what path it resolves to (an empty/unset var even makes
  # `$DIR/x` collapse toward `/`), so it cannot verify what would be deleted.
  # DENY and have the agent resolve it to a literal first — auditable, no human.
  # Checked before the ~/subpath rule so a `$HOME/x`-style token is treated as a
  # variable, not a home subpath.
  case "$t" in
    *'$'*) echo deny-var; return ;;
  esac

  # A ~/subpath is outside the project working tree but the agent named it
  # explicitly and home files are recoverable enough -> non-blocking warn.
  # shellcheck disable=SC2088
  case "$t" in
    '~/'*) echo warn; return ;;
  esac

  # Resolve against the working dir and judge by the project working tree FIRST
  # (before the temp-root shortcut below) — otherwise a repo that itself lives
  # under /tmp would have its own root/.git wrongly allowed by the temp rule.
  abs="$(norm_abs "$t")"

  # The repo root itself or its .git dir: deleting these destroys the very git
  # state the recoverability assumption relies on -> warn (proceed, but informed).
  if [[ "$abs" == "$root" || "$abs" == "$root/.git" || "$abs" == "$root/.git/"* ]]; then
    echo warn; return
  fi

  # Strictly inside the working tree -> recoverable via git -> allow silently.
  if [[ "$abs" == "$root/"* ]]; then
    echo allow; return
  fi

  # Outside the tree, but a temp / scratch root — always safe to wipe.
  case "$abs" in
    /tmp|/tmp/*|/private/tmp|/private/tmp/*|/var/folders/*|/private/var/folders/*)
      echo allow; return ;;
  esac

  # Anything else resolved outside the project working tree -> warn.
  echo warn
}

# Most-severe target wins. Precedence: deny-crit > deny-var > warn > allow.
# (deny-crit and deny-var both block; deny-crit's message is the more urgent.)
worst="allow"
while IFS= read -r target; do
  [[ -z "$target" ]] && continue
  sev="$(severity "$target")"
  case "$sev" in
    deny)      worst="deny-crit"; break ;;   # legacy alias; nothing more severe
    deny-crit) worst="deny-crit"; break ;;
    deny-var)  [[ "$worst" != "deny-crit" ]] && worst="deny-var" ;;
    warn)      case "$worst" in deny-crit|deny-var) ;; *) worst="warn" ;; esac ;;
  esac
done <<<"$targets"

case "$worst" in
  deny-crit)
    decide deny "blocked by BS-8 (no rm -rf on system-critical path): rm -rf targets a system-critical or home path ('$display_targets'); this is unrecoverable and is blocked."
    ;;
  deny-var)
    decide deny "blocked by BS-9 (no rm -rf with unexpanded variable): rm -rf '$display_targets' contains an unexpanded shell variable (e.g. \$DIR / \${DIR}), so the guard cannot verify which path will be deleted. Re-run with the variable resolved to a literal path (e.g. run \`echo \"\$DIR\"\` first, then pass the actual path) so the deletion target is auditable."
    ;;
  warn)
    decide warn "BS-10 (warn on rm -rf outside working tree): rm -rf '$display_targets' is not inside the project's git working tree (it's outside the repo, or the repo root/.git itself), so it is not git-recoverable. Make sure this is the intended target. Proceeding."
    ;;
  *)
    exit 0   # inside the git working tree, or a temp dir — allow silently
    ;;
esac
