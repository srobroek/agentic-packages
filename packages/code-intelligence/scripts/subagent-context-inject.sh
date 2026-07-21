#!/usr/bin/env bash
# Hook: SubagentStart -- inject project context + MCP guidance into subagents
# Fires for all subagent types. Injects additionalContext into the agent's system prompt.

INPUT=$(cat)
AGENT_TYPE=$(echo "$INPUT" | jq -r '.agent_type // empty')
AGENT_ID=$(echo "$INPUT" | jq -r '.agent_id // empty')
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')

[ -z "$AGENT_ID" ] && exit 0  # Not a subagent

# Resolve repo root (works from worktrees too)
REPO_ROOT=$(git -C "$CWD" rev-parse --show-toplevel 2>/dev/null)
[ -z "$REPO_ROOT" ] && exit 0

BRANCH=$(git -C "$REPO_ROOT" branch --show-current 2>/dev/null)
PROJECT=$(basename "$REPO_ROOT")

# Base context for ALL subagents: project identity + code-discovery routing.
# Working-style discipline (code economy, comments, report format) lives in the
# steering-pragmatic package's SubagentStart hook, not here -- this package owns
# only the code-intelligence routing concern.
NL=$'\n'
CTX="Project: $PROJECT. Branch: $BRANCH. "
CTX+="For code discovery use Serena for semantic symbols, references, and edits; use rg for exact text and paths; use context7 for library documentation. Fall back to direct file inspection when semantic tools cannot answer.${NL}"

# Adversarial challenger: reinforce isolation
if [ "$AGENT_TYPE" = "adversarial-challenger" ]; then
    CTX+="IMPORTANT: You are investigating independently. "
    CTX+="Do NOT read spec files, conversation history, or CLAUDE.md reasoning sections. "
    CTX+="Work ONLY from the Problem Brief provided in your prompt. "
    CTX+="You may read source code, run tests, and grep -- but form your own hypotheses. "
fi

# Extra context for implementation agents
if [ "$AGENT_TYPE" = "speckit-implement-task" ]; then
    # Detect test/check command from task runner
    if [ -f "$REPO_ROOT/justfile" ]; then
        CTX+="Verify changes with: just check (see justfile for details). "
    elif [ -f "$REPO_ROOT/Taskfile.yml" ] || [ -f "$REPO_ROOT/Taskfile.yaml" ]; then
        CTX+="Verify changes with: task check (see Taskfile for details). "
    elif [ -f "$REPO_ROOT/package.json" ]; then
        CTX+="Verify changes with: pnpm test. "
    fi
    CTX+="Commit with conventional format (feat/fix/docs/refactor/chore). "
    MAIN_BRANCH=$(git -C "$REPO_ROOT" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
    [ -z "$MAIN_BRANCH" ] && MAIN_BRANCH="main"
    # tr cannot expand one byte into two; collapse newlines to single spaces
    # and rely on jq for JSON-safe encoding below.
    CHANGED=$(git -C "$REPO_ROOT" diff --name-only "$MAIN_BRANCH" 2>/dev/null | head -10 | tr '\n' ' ')
    [ -n "$CHANGED" ] && CTX+="Files changed on branch: $CHANGED. "
fi

# Build the JSON with jq so backslashes, quotes, and newlines in the repo
# path or branch name are encoded correctly (hand-rolled sed escaping
# produced invalid JSON for paths containing a backslash).
jq -n --arg ctx "$CTX" '{
  hookSpecificOutput: {
    hookEventName: "SubagentStart",
    additionalContext: $ctx
  }
}'
