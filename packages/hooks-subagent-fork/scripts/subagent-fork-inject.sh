#!/usr/bin/env bash
# Hook: SubagentStart — inject the fork_turns discipline so any agent that
# itself spawns sub-subagents (orchestrators, pull-workers) carries the rule.
# Static content; gates only on being an actual subagent. Fails open if jq is
# missing so a spawn is never blocked.

INPUT=$(cat)

FORK_MAX="${SUBAGENT_FORK_GUARD_MAX:-3}"
case "$FORK_MAX" in
  ""|*[!0-9]*) FORK_MAX=3 ;;
esac

if ! command -v jq >/dev/null 2>&1; then
  echo "subagent-fork-inject: jq not found; spawning WITHOUT the fork_turns digest" >&2
  exit 0
fi

AGENT_ID=$(printf '%s' "$INPUT" | jq -r '.agent_id // empty')
[ -z "$AGENT_ID" ] && exit 0  # Not a subagent

NL=$'\n'
CTX="SUBAGENT SPAWN DISCIPLINE — applies when this task spawns further subagents:${NL}"
CTX+="- Always execute with fork_turns=\"none\" unless recent thread context is explicitly required.${NL}"
CTX+="- Format the tool call: spawn_agent(task_name=\"code-reviewer\", fork_turns=\"none\")${NL}"
CTX+="- Put everything the subagent needs into the spawn prompt; forked turns are not a substitute for a complete brief. fork_turns=\"all\", omitted fork_turns, and values above ${FORK_MAX} are denied by policy.${NL}"

jq -n --arg ctx "$CTX" '{
  hookSpecificOutput: {
    hookEventName: "SubagentStart",
    additionalContext: $ctx
  }
}'
