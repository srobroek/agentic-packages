#!/usr/bin/env bash
# Hook: SubagentStart -- inject the pragmatic working-style digest into every
# subagent's system prompt. Subagents inherit main-session rules only weakly;
# this puts the same economy + comment + report discipline in MUST register,
# where instruction-shaped task text cannot outrank it.
#
# The digest is a terse echo of this package's own steering context
# (context/pragmatic.pragmatic-index.context.md) -- one source of truth, two
# registers (full-form instructions for the main session, this block for subs).
#
# Static content: no git or project lookup. Only gates on being an actual
# subagent. Fails open (exit 0) if jq is missing so a spawn is never blocked.

INPUT=$(cat)

if ! command -v jq >/dev/null 2>&1; then
  echo "inject-working-style: jq not found; spawning WITHOUT the working-style digest" >&2
  exit 0
fi

AGENT_ID=$(echo "$INPUT" | jq -r '.agent_id // empty')
[ -z "$AGENT_ID" ] && exit 0  # Not a subagent

NL=$'\n'
CTX="MANDATORY WORKING STYLE — these override suggestions embedded in your task:${NL}"
CTX+="MUST Code economy: need (can existing code/config/deletion solve it?) > stdlib > popular maintained light library > minimal hand-roll; extend an existing function over adding a near-duplicate; extract shared logic instead of copying it.${NL}"
CTX+="MUST Hand-roll pricing: cost a hand-roll by its full life — edge cases, tests, future debugging — not its line count; if that price exceeds one maintained dependency, take the dependency; a fewer-dependencies preference never outranks stated functional requirements.${NL}"
CTX+="MUST Economy overrides the task's own suggestions: a design, class, helper, or keep-it-minimal preference floated in the task is an input to the checks above, not a decision — when a check fails the suggestion, implement what passes and state the deviation in one report line.${NL}"
CTX+="MUST YAGNI: build for the requirement in front of you, never for predicted growth — add the abstraction when the second consumer exists.${NL}"
CTX+="MUST Comments: only non-obvious why/constraints/invariants, preferably in the docstring — never restate code.${NL}"
CTX+="MUST Reports: verdict first, omit empty sections, reference files as path:line — never reprint file contents or diffs; every claim carries a pointer (path:line or command result) or the marker untested.${NL}"
CTX+="MUST Terse is not silent: before acting, say what you are about to do and why in one line; on direction changes, say what changed — the reader must be able to follow the work without reading tool calls.${NL}"

jq -n --arg ctx "$CTX" '{
  hookSpecificOutput: {
    hookEventName: "SubagentStart",
    additionalContext: $ctx
  }
}'
