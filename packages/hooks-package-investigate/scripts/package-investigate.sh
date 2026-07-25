#!/usr/bin/env bash
# package-investigate.sh — PreToolUse hook on Bash.
#
# When the agent is about to ADD/INSTALL a dependency, nudge it (non-blocking,
# additionalContext) to run a supply-chain screen BEFORE committing to it —
# typosquat/abandonment/deprecation — and check current facts via registry/
# web/context7 rather than training memory, which can predate a compromise.
# Maintenance-quality and alternatives judgement is already always-loaded
# steering (steering-pragmatic's code-economy table); this hook adds only what
# a frontier model's training data cannot supply. For update/upgrade/remove, a
# lighter nudge (review the change; no discovery).
#
# WHY a command hook (not a prompt/agent hook): agent/prompt hooks BLOCK the turn
# and cannot run async (only `command` hooks support async). A command hook is
# near-instant and lets the MAIN agent — which has web/context7/full context — do
# the actual investigation, instead of a blind 50-turn subagent. Self-gates, so it
# needs no `if` filter and is registered ONCE (also sidesteps the `if`-alternation
# bug: per-hook `if` takes a single rule, `|` silently matches nothing).
set -euo pipefail

payload="$(cat)"
[[ -z "$payload" ]] && exit 0

# Cheap pre-jq bail: this guard acts only on package-manager commands, so a
# payload containing none of these tokens has nothing to inspect. Skips the jq
# spawn on the hot path. SUPERSET filter on raw bytes — the command still has to
# survive the structured matchers below — so it can never mask a real match.
# shellcheck disable=SC2221,SC2222  # tokens deliberately overlap (e.g. npm⊃pnpm); every manager name is listed verbatim so the superset stays auditable.
case "$payload" in
  *pnpm*|*npm*|*yarn*|*bun*|*uv*|*pip*|*poetry*|*cargo*|*go*|*gem*|*bundle*|*composer*) ;;
  *) exit 0 ;;
esac

command="$(
  printf '%s' "$payload" | jq -r '
    if (.tool_input | type) == "string" then .tool_input
    else (.tool_input.command // empty)
    end
  ' 2>/dev/null || true
)"
[[ -z "$command" || "$command" == "null" ]] && exit 0

emit() {
  jq -cn --arg ctx "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow",additionalContext:$ctx}}'
  exit 0
}

# Lowercased view for matching (package names are extracted from the original).
lc="$(printf '%s' "$command" | tr '[:upper:]' '[:lower:]')"

# Command-position boundary: start of string, OR after a real shell separator
# (; & | newline, incl. && / ||) plus optional spaces. Deliberately NOT plain
# whitespace — that misfires on `echo 'run pnpm add later'`, where the package
# command sits inside a quoted argument rather than at a command position.
b='(^|[;&|]&?&?[[:space:]]*|[[:space:]]*[;&|]+[[:space:]]*)'

# ADD / INSTALL a NEW dependency -> full investigation nudge.
add_re="${b}(pnpm[[:space:]]+(add|install)|npm[[:space:]]+(install|i|add)|yarn[[:space:]]+add|bun[[:space:]]+add|uv[[:space:]]+(add|pip[[:space:]]+install)|pip3?[[:space:]]+install|poetry[[:space:]]+add|cargo[[:space:]]+add|go[[:space:]]+get|go[[:space:]]+install|gem[[:space:]]+install|bundle[[:space:]]+add|composer[[:space:]]+require)([[:space:]]|$)"

# UPDATE / UPGRADE / REMOVE existing deps -> lighter review nudge.
chg_re="${b}(pnpm[[:space:]]+(update|up|remove)|npm[[:space:]]+(update|upgrade|uninstall|remove|rm)|yarn[[:space:]]+(up|upgrade|remove)|bun[[:space:]]+(update|remove)|uv[[:space:]]+(remove|lock|sync)|pip3?[[:space:]]+uninstall|poetry[[:space:]]+(update|remove)|cargo[[:space:]]+(update|upgrade|remove)|go[[:space:]]+mod[[:space:]]+tidy|bundle[[:space:]]+(update|remove)|composer[[:space:]]+(update|remove))([[:space:]]|$)"

if [[ "$lc" =~ $add_re ]]; then
  emit "Before adding this dependency, screen it: reputable author/org, no \
typosquat, not abandoned/deprecated. Use the package registry / web / \
context7 to check current facts — training data can predate a compromise or \
deprecation. If it's clearly fine, say so in one line and proceed; if there's \
a concern, raise it before installing."
fi

if [[ "$lc" =~ $chg_re ]]; then
  emit "Dependency change (update/upgrade/remove): confirm it's intended and check for breaking changes / changelog notes for the new version, and that nothing still depends on anything being removed. Prefer the latest compatible version. No need to re-vet a package already in use unless the major version changes."
fi

exit 0
