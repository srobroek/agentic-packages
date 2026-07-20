#!/usr/bin/env bash
# Hook: PreToolUse:Bash - PR title/body guidance (Claude + Codex).
#
# Always-on advisory (allow + additionalContext) on `gh pr create` / `gh pr
# edit`: PR titles become changelog entries via squash merge, so they must be
# written for end users. Carries the title/body-format half of the retired
# speckit-pr-issue-refs.sh (the issue-refs half is gone -- task state lives in
# beads, not GitHub issues).
#
# Self-gating: silent unless the payload is a gh pr create/edit command in a
# speckit project. Fail open on missing jq. bash 3.2 / BSD safe.

[ -d ".specify" ] || exit 0

INPUT=$(cat 2>/dev/null || true)
[ -z "$INPUT" ] && exit 0

# Cheap pre-jq bail: only gh pr commands are of interest.
case "$INPUT" in
  *gh*pr*) ;;
  *) exit 0 ;;
esac

command -v jq >/dev/null 2>&1 || exit 0

COMMAND=$(printf '%s' "$INPUT" | jq -r '
  if (.tool_input|type)=="string" then .tool_input
  else (.tool_input.command // empty) end' 2>/dev/null)
[ -z "$COMMAND" ] && exit 0

# Trigger on PR creation/edit (gh directly or via a gh-api.py wrapper).
printf '%s' "$COMMAND" | grep -qE '(gh pr (create|edit)|gh-api\.py.*pr create|glab mr create)' || exit 0

# `read -d ''` reaches EOF and returns nonzero after filling the var; guard it
# so `set -e` callers and strict shells do not abort.
read -r -d '' CONTEXT << 'GUIDANCE' || true
PR TITLE = CHANGELOG ENTRY (via squash merge). Write for end users.

TITLE FORMAT:
- Minor fix: "fix: catalog refresh fails when offline"
- Minor feature: "feat: show version at startup for diagnostics"
- Major feature: "feat: automatic software detection via Windows registry and WMI"
- Breaking change: "feat!: migrate config from TOML to SQLite-backed storage"
- NEVER include spec IDs, task refs, phase names, or internal jargon

PR BODY FORMAT -- scale detail to significance:

MAJOR FEATURES (new capability, large scope):
## Summary
<2-3 sentences: what this adds and why users care>

## What's new
- Bullet points of user-visible changes
- Each bullet is a concrete capability, not an implementation detail

## Breaking changes
<only if applicable -- what breaks, what users need to do>

MINOR CHANGES & BUG FIXES (targeted fix or small enhancement):
## Summary
- Short bullet(s) describing what changed and why

BREAKING CHANGES -- always flag explicitly:
- Add `!` after type in title: "feat!: ..." or "fix!: ..."
- Include a "## Breaking changes" section explaining what breaks and migration steps

Spec context goes at the bottom under "## Spec Context" (not in the title).
The release-please draft PR will be manually curated before publish -- raw material matters.
GUIDANCE

jq -n --arg ctx "$CONTEXT" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: $ctx
  }
}'
exit 0
