#!/usr/bin/env bash
# Hook: SubagentStart -- inject the write-docs documentation discipline into
# every subagent's system prompt. Subagents inherit main-session rules only
# weakly: the always-on 75-write-docs instruction that reinforces the skill in
# the main session does NOT reach subagents, so a subagent's only trigger signal
# is the one-line skill description. This restores the same discipline in the
# MUST register, where instruction-shaped task text cannot outrank it.
#
# The digest is a terse echo of this package's own steering (the 75-write-docs
# instruction + context/write-docs.write-docs-index.context.md) and the skill's
# genre rules -- one source of truth, two registers (full-form instruction +
# skill for the main session, this block for subs).
#
# Content is SELF-GATING: it opens with "applies when this task includes
# writing or reviewing any document", so a code-only subagent harmlessly ignores
# it (exactly how 75-write-docs is always present in the main session but only
# conditionally relevant). This mirrors inject-working-style.sh, whose digest
# applies universally; doc discipline does not, hence the conditional lead.
#
# Static content: no git or project lookup. Only gates on being an actual
# subagent. Fails open (exit 0) if jq is missing so a spawn is never blocked.

INPUT=$(cat)

if ! command -v jq >/dev/null 2>&1; then
  echo "inject-doc-discipline: jq not found; spawning WITHOUT the doc-discipline digest" >&2
  exit 0
fi

AGENT_ID=$(echo "$INPUT" | jq -r '.agent_id // empty')
[ -z "$AGENT_ID" ] && exit 0  # Not a subagent

NL=$'\n'
CTX="DOCUMENTATION DISCIPLINE — applies when this task includes writing or reviewing any document (README, docs, PR/release text, spec, ADR, CONTRIBUTING):${NL}"
CTX+="MUST Invoke the write-docs skill before finalizing such a document — even when it is one step of a larger task. The skill loads the genre rules and runs a deterministic slop/status-language linter so the result is objective and example-backed.${NL}"
CTX+="MUST State what the artifact does — never effort, intent, process, or journey; delete any adjective you cannot back with a number, benchmark, or feature list.${NL}"
CTX+="MUST One idea per sentence; lists and tables over prose paragraphs.${NL}"
CTX+="MUST Consumer docs (README, docs/): write for the released artifact — every sentence verifiable against code at HEAD, no roadmap or target states, no internal references (specs, ADRs, tickets).${NL}"
CTX+="NOT Status language (under construction, WIP, coming soon, currently, for now, planned) or history narration in a doc body.${NL}"
CTX+="NOT Slop lexicon (seamless, robust, powerful, comprehensive, leverage, blazingly fast, battle-tested, and similar) or emoji headings.${NL}"

jq -n --arg ctx "$CTX" '{
  hookSpecificOutput: {
    hookEventName: "SubagentStart",
    additionalContext: $ctx
  }
}'
