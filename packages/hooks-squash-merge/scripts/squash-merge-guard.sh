#!/usr/bin/env bash
set -euo pipefail

# PreToolUse hook: require an explicit merge strategy on `gh pr merge`.
#
# Portability floor: bash 3.2.57 + BSD sed/grep (stock macOS). Only POSIX
# parameter expansion, `case` globbing, and bash `[[ =~ ]]` ERE are used — no
# bash-4 features, no GNU-only regex.
#
# Contract: read a Claude PreToolUse event on stdin, emit a decision on stdout
#   {hookSpecificOutput:{hookEventName,permissionDecision,additionalContext}}
# and ALWAYS exit 0 (the decision lives in the JSON). When no guard fires, emit
# nothing and exit 0 ("allow" by omission).
#
# Severity: a `gh pr merge` with NO explicit strategy emits a non-blocking
# advisory (allow + additionalContext) so the merge strategy is always visible.

payload="$(cat)"
if [[ -z "$payload" ]]; then
  exit 0
fi

# tool_input is either an object ({command:"..."}) OR a bare string. Type-check
# first so a string-form input is not silently dropped (the naive jq idiom
# throws on a string and bypasses the guard).
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

# Non-blocking advisory: allow the command and surface context to the model.
warn() {
  jq -cn --arg ctx "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow",additionalContext:$ctx}}' 2>/dev/null || true
  exit 0
}

lowered="$(printf '%s' "$command" | tr '[:upper:]' '[:lower:]')"

# Only `gh pr merge` is gated.  The leading anchor requires `gh` to sit at
# command position — start-of-string or right after a real shell separator
# (; & | && ||) with optional spaces — so an echoed or commented literal such
# as `echo gh pr merge` does NOT match.  The trailing boundary accepts
# whitespace, shell punctuation, or end-of-string so `gh pr merge;` / `gh pr
# merge|cat` / `gh pr merge>out` are all caught.
if ! [[ "$lowered" =~ (^|[;&|])[[:space:]]*gh[[:space:]]+pr[[:space:]]+merge([[:space:];|&\)>#]|$) ]]; then
  exit 0
fi

# Help/usage lookups are not merges — early ALLOW.
if [[ "$lowered" =~ (^|[[:space:]])(--help|-h)([[:space:]]|$) ]]; then
  exit 0
fi

# Truncate at the first shell separator so that tokens belonging to a CHAINED
# command (e.g. `gh pr merge && git rebase -r`) are not mistaken for strategy
# flags of the gh-pr-merge invocation itself.  We work on the ORIGINAL-CASE
# command so that -R/--repo (uppercase) is never folded into -r (rebase).
# Strategy detection must be POSITIONAL: a `--squash` that is only the VALUE of
# a subject/body flag (e.g. `-t "use --squash"`) must NOT count as a provided
# strategy. We scan the command token-by-token, quote-aware, and skip the
# argument of any value-taking flag before testing a token as a strategy.
#
# truncate_at_separator <string> -> prints the portion before the first
#   unquoted shell separator (&& || ; & | — in that priority order).
truncate_at_separator() {
  local s="$1" result="" tok rest
  while [[ -n "$s" ]]; do
    # Trim leading whitespace, accumulating it.
    local leading="${s%%[![:space:]]*}"
    s="${s#"$leading"}"
    [[ -z "$s" ]] && break

    # Check for multi-char separators before peeling a token.
    # Use parameter-expansion prefix check (portable bash 3.2): &&, ||.
    if [[ "${s:0:2}" == "&&" || "${s:0:2}" == "||" ]]; then
      break
    fi

    # Peel ONE quote-aware token or separator character.
    case "$s" in
      \'*)
        rest="${s#\'}"
        tok="'${rest%%\'*}'"
        s="${rest#*\'}"
        ;;
      \"*)
        rest="${s#\"}"
        tok="\"${rest%%\"*}\""
        s="${rest#*\"}"
        ;;
      ';'*|'&'*)
        # Unquoted ; or & separator — stop here.
        break
        ;;
      \|*)
        # Unquoted | separator — stop here.
        break
        ;;
      *)
        tok="${s%%[[:space:]]*}"
        if [[ "$tok" == "$s" ]]; then
          s=""
        else
          s="${s#"$tok"}"
        fi
        # If the token itself contains a shell separator (e.g. "merge;"),
        # truncate the token at the first such character and stop.
        local sep_idx=${#tok}
        local i=0
        while [[ $i -lt ${#tok} ]]; do
          local ch="${tok:$i:1}"
          if [[ "$ch" == ";" || "$ch" == "&" || "$ch" == "|" ]]; then
            sep_idx=$i
            break
          fi
          i=$((i+1))
        done
        if [[ $sep_idx -lt ${#tok} ]]; then
          tok="${tok:0:$sep_idx}"
          result="${result}${leading}${tok}"
          break
        fi
        ;;
    esac
    result="${result}${leading}${tok}"
  done
  printf '%s' "$result"
}

# `has_strategy <command>` -> returns 0 if a real strategy token is present.
has_strategy() {
  # Truncate to just the gh-pr-merge portion before token-scanning, and work
  # on the original-case string so -R is never mistaken for -r.
  local s
  s="$(truncate_at_separator "$1")"
  local tok rest expect_value=0

  # value-taking flags whose NEXT token is data, not a strategy.
  # (-t/--title -b/--body -F/--body-file -R/--repo --match-* etc.)
  while [[ -n "$s" ]]; do
    # Trim leading whitespace.
    s="${s#"${s%%[![:space:]]*}"}"
    [[ -z "$s" ]] && break

    # Peel ONE quote-aware token off the front.
    case "$s" in
      \'*)
        rest="${s#\'}"
        tok="${rest%%\'*}"
        s="${rest#*\'}"
        ;;
      \"*)
        rest="${s#\"}"
        tok="${rest%%\"*}"
        s="${rest#*\"}"
        ;;
      *)
        tok="${s%%[[:space:]]*}"
        if [[ "$tok" == "$s" ]]; then
          s=""
        else
          s="${s#"$tok"}"
        fi
        ;;
    esac

    # If the previous token was a value-taking flag, this token is its DATA.
    # Skip it without strategy testing.
    if [[ "$expect_value" -eq 1 ]]; then
      expect_value=0
      continue
    fi

    # Inline `--flag=value` forms carry their value in the same token, so they
    # never consume the following token.
    case "$tok" in
      -t=*|--title=*|-b=*|--body=*|-F=*|--body-file=*|-R=*|--repo=*|--match-head-commit=*|--author-email=*)
        continue
        ;;
      -t|--title|-b|--body|-F|--body-file|-R|--repo|--match-head-commit|--author-email)
        expect_value=1
        continue
        ;;
    esac

    # A real strategy token, anchored so `--mergetool` does NOT match the
    # `merge` alternation and a short flag is the whole token.
    # Case-sensitive match: -R is --repo (value-taking, handled above) and must
    # NOT be treated as the -r rebase shorthand.
    if [[ "$tok" =~ ^--(squash|merge|rebase)([=]|$) ]]; then
      return 0
    fi
    if [[ "$tok" =~ ^-(s|m|r)$ ]]; then
      return 0
    fi
  done

  return 1
}

# Pass original-case command so -R is not folded to -r.
if has_strategy "$command"; then
  exit 0
fi

warn "gh pr merge has no explicit strategy. Pick one so the merge is intentional: --squash (-s) for feature PRs, --merge (-m) for release PRs, or --rebase (-r). Proceeding with gh's default."

# Unreachable (warn exits), kept for clarity.
exit 0
