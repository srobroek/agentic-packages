#!/usr/bin/env bash
set -euo pipefail

# subagent-model-guard.sh — PreToolUse:Agent deny gate (cross-tool payload
# shape; Claude-only trigger since Agent/Task is a Claude-specific tool).
#
# Problem: the parent session often runs an expensive top-tier model. A spawn
# that omits `model` and names a subagent_type with no pinned model in its
# definition (a "general-purpose"-shaped agent) silently INHERITS the parent's
# model — burning the expensive model on work that a cheaper one could do.
#
# Policy:
#   ALLOW — `model` is set (caller made an explicit choice), OR `subagent_type`
#           is set and is NOT one of the inherit-by-default types (a pinned
#           agent definition already fixes its own model regardless of what
#           the caller passes).
#   DENY  — `model` is absent AND either `subagent_type` is absent or it is one
#           of the inherit-by-default types. The deny reason is a routing table
#           teaching the caller which model to pass so the retry succeeds.
#
# The inherit-by-default list is deliberately small and overridable per-project
# via SUBAGENT_MODEL_GUARD_INHERIT_TYPES (comma-separated) so a project can add
# its own unpinned custom agent types without waiting on a package release.
#
# Fail-open: missing jq, empty stdin, or malformed JSON all exit 0 with no
# output. A broken guard must never block all delegation.

command -v jq >/dev/null 2>&1 || exit 0

payload="$(cat 2>/dev/null || true)"
[[ -z "$payload" ]] && exit 0

tool=""
model=""
subagent_type=""
{
  IFS= read -r tool || true
  IFS= read -r model || true
  IFS= read -r subagent_type || true
} < <(
  printf '%s' "$payload" | jq -r '
    (.tool_name // ""),
    (if (.tool_input|type)=="object" then (.tool_input.model // "") else "" end),
    (if (.tool_input|type)=="object" then (.tool_input.subagent_type // "") else "" end)
  ' 2>/dev/null
)

# Agent and Task are both observed as tool_name values for subagent spawns
# across harnesses; anything else is not a spawn this guard cares about.
case "$tool" in
  Agent|Task) ;;
  *) exit 0 ;;
esac

[[ -n "$model" && "$model" != "null" ]] && exit 0
[[ "$subagent_type" == "null" ]] && subagent_type=""

# Agent types with no pinned `model:` field in their definition — an
# unspecified spawn rides whatever model the parent session is running.
inherit_types="${SUBAGENT_MODEL_GUARD_INHERIT_TYPES:-general-purpose,Explore,Plan,claude,fork}"

is_inherit_type() {
  local needle="$1" item
  local IFS=,
  for item in $inherit_types; do
    # trim surrounding whitespace so "a, b, c" style overrides still match
    item="${item#"${item%%[![:space:]]*}"}"
    item="${item%"${item##*[![:space:]]}"}"
    [[ "$item" == "$needle" ]] && return 0
  done
  return 1
}

if [[ -n "$subagent_type" ]] && ! is_inherit_type "$subagent_type"; then
  exit 0
fi

read -r -d '' reason <<'EOF' || true
This agent type inherits the session model. Re-issue the Agent call with an explicit model:
- haiku — mechanical work: CI watching/shepherding, log triage, batched gh/git operations, file sweeps, formatting
- sonnet — bounded coding, standard research, PR fix rounds, doc writing, test authoring
- opus or omit-after-deliberation — deep/adversarial research, architecture, cross-cutting synthesis, judge/verification passes (to inherit the top-tier session model intentionally, pass the session's model name explicitly)

Effort is not enforceable per-call (this hook cannot see a `tool_input.effort` field). For reusable agents, pin `effort:` in the agent definition frontmatter (low for mechanical lanes, high+ for verification/judge lanes). Workflow scripts may pass effort per agent() call.
EOF

jq -cn --arg reason "$reason" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}' 2>/dev/null || true
exit 0
