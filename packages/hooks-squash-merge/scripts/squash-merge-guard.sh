#!/usr/bin/env bash
set -euo pipefail

# PreToolUse hook: require an explicit merge strategy on `gh pr merge`.
#
# Portability floor: bash 3.2.57 + BSD sed/grep (stock macOS). Only POSIX
# parameter expansion, `case` globbing, and bash `[[ =~ ]]` ERE are used — no
# bash-4 features, no GNU-only regex.
#
# Contract: read a Claude PreToolUse event on stdin, emit a decision on stdout
#   {hookSpecificOutput:{hookEventName,permissionDecision,permissionDecisionReason}}
# and ALWAYS exit 0 (the decision lives in the JSON). When no guard fires, emit
# nothing and exit 0 ("allow" by omission).
#
# Severity (preserved from the original): a `gh pr merge` with NO explicit
# strategy is blocked outright so the merge strategy is always intentional.

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

# Hard block: refuse outright; the user must rephrase with a strategy.
deny() {
  jq -cn --arg reason "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}'
  exit 0
}

lowered="$(printf '%s' "$command" | tr '[:upper:]' '[:lower:]')"

# Only `gh pr merge` is gated.
if ! [[ "$lowered" =~ (^|[[:space:]])gh[[:space:]]+pr[[:space:]]+merge([[:space:]]|$) ]]; then
  exit 0
fi

# Help/usage lookups are not merges — early ALLOW.
if [[ "$lowered" =~ (^|[[:space:]])(--help|-h)([[:space:]]|$) ]]; then
  exit 0
fi

# Strategy detection must be POSITIONAL: a `--squash` that is only the VALUE of
# a subject/body flag (e.g. `-t "use --squash"`) must NOT count as a provided
# strategy. We scan the command token-by-token, quote-aware, and skip the
# argument of any value-taking flag before testing a token as a strategy.
#
# `has_strategy <command>` -> returns 0 if a real strategy token is present.
has_strategy() {
  local s="$1" tok rest expect_value=0

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
    if [[ "$tok" =~ ^--(squash|merge|rebase)([=]|$) ]]; then
      return 0
    fi
    if [[ "$tok" =~ ^-(s|m|r)$ ]]; then
      return 0
    fi
  done

  return 1
}

if has_strategy "$lowered"; then
  exit 0
fi

deny "gh pr merge needs an explicit strategy. Use --squash (or -s) for feature PRs, --merge (-m) for release PRs, or --rebase (-r)."

# Unreachable (deny exits), kept for clarity.
exit 0
