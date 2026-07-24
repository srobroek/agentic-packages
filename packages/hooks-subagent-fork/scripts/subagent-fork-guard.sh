#!/usr/bin/env bash
set -euo pipefail

# subagent-fork-guard.sh — PreToolUse:Agent deny gate for Codex fork_turns.
#
# Problem: Codex `spawn_agent` DEFAULTS to a full-history fork — the released
# binary documents "Full-history forks (`fork_turns` omitted or \"all\")".
# Copying the entire parent thread into a subagent burns tokens quadratically
# across a fan-out and leaks parent context into roles designed to receive a
# bounded brief. Subagents in this fleet are written to work from their spawn
# prompt alone.
#
# Policy (deny + self-correction guidance, per constitution III — no "ask"),
# applied only to Codex-shaped spawn payloads (Claude Agent calls carry no
# task_name/agent_type/fork_turns fields and pass through untouched):
#   * fork_turns omitted             -> deny (omitted == "all" upstream)
#   * fork_turns == "all"            -> deny
#   * numeric fork_turns > FORK_MAX  -> deny (default 3)
#   * "none" or number <= FORK_MAX   -> allow
#
# Default 3, not 5: the cap counts turns but cost lives in turn content the
# hook cannot see, so it is a heuristic backstop. The legitimate "recent
# thread context explicitly required" case is the immediately preceding
# exchange (1-3 turns); needing more is the signal to write a complete spawn
# brief instead. A false deny costs one self-correcting retry; a false allow
# can fork a huge context tail — asymmetric costs favor the stricter default.
# SUBAGENT_FORK_GUARD_MAX relaxes it per-project without a release.
#
# Fail-open: missing jq, empty stdin, or malformed JSON exit 0 with no
# output. A broken guard must never block all delegation.

command -v jq >/dev/null 2>&1 || exit 0

payload="$(cat 2>/dev/null || true)"
[[ -z "$payload" ]] && exit 0

fork_max="${SUBAGENT_FORK_GUARD_MAX:-3}"
case "$fork_max" in
  ''|*[!0-9]*) fork_max=3 ;;
esac

tool=""
fork_turns=""
has_fork_turns="false"
is_codex_spawn="false"
{
  IFS= read -r tool || true
  IFS= read -r fork_turns || true
  IFS= read -r has_fork_turns || true
  IFS= read -r is_codex_spawn || true
} < <(
  printf '%s' "$payload" | jq -r '
    (.tool_name // ""),
    (if (.tool_input|type)=="object"
     then (.tool_input.fork_turns // "" | tostring)
     else "" end),
    (if (.tool_input|type)=="object"
     then (.tool_input | has("fork_turns"))
     else false end),
    (if (.tool_input|type)=="object"
     then ((.tool_input | has("task_name")) or (.tool_input | has("agent_type")) or
           (.tool_input | has("fork_turns")) or (.tool_input | has("fork_context")))
     else false end)
  ' 2>/dev/null
)

case "$tool" in
  Agent|Task) ;;
  *) exit 0 ;;
esac

# Claude Agent/Task spawns never carry Codex spawn fields; leave them alone.
[[ "$is_codex_spawn" == "true" ]] || exit 0

deny() {
  jq -cn --arg reason "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}' 2>/dev/null || true
  exit 0
}

format_hint="Format: spawn_agent(task_name=\"code-reviewer\", fork_turns=\"none\")."

if [[ "$has_fork_turns" != "true" || -z "$fork_turns" || "$fork_turns" == "null" ]]; then
  deny "Subagent spawn blocked: fork_turns was omitted, and Codex defaults an omitted fork_turns to \"all\" (full-history fork of the parent thread). Re-issue with an explicit fork_turns=\"none\" and put everything the subagent needs into the spawn prompt. ${format_hint} Use a small number (<= ${fork_max}) only when recent thread context is explicitly required."
fi

if [[ "$fork_turns" == "all" ]]; then
  deny "Subagent spawn blocked: fork_turns=\"all\" copies the entire parent thread into the subagent. Re-issue with fork_turns=\"none\" and put everything the subagent needs into the spawn prompt. ${format_hint} Use a small number (<= ${fork_max}) only when recent thread context is explicitly required."
fi

if [[ "$fork_turns" =~ ^[0-9]+$ ]] && (( fork_turns > fork_max )); then
  deny "Subagent spawn blocked: fork_turns=${fork_turns} exceeds the maximum of ${fork_max}. Re-issue with fork_turns=\"none\" (preferred — pass needed context in the spawn prompt) or a value <= ${fork_max} when recent thread context is explicitly required. ${format_hint}"
fi

exit 0
