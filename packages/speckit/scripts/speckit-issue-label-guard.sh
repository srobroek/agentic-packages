#!/usr/bin/env bash
# Hook: PreToolUse:Bash -- enforce spec: and deferred labels on issue creation
# Blocks (exit 2) if labels missing. Checks both CLI and GraphQL mutations.

# Only activate in speckit projects
[ -d ".specify" ] || exit 0

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

# Check CLI issue creation (gh/glab)
if echo "$COMMAND" | grep -qE '(gh issue create|glab issue create)'; then
  # Require spec: label
  if ! echo "$COMMAND" | grep -qE '\-\-label[= ]*[^ ]*spec:'; then
    echo "BLOCKED: Issue creation missing spec: label. Add --label 'spec:{spec-id}'." >&2
    exit 2
  fi
  # Require phase: label
  if ! echo "$COMMAND" | grep -qE '\-\-label[= ]*[^ ]*phase:'; then
    echo "BLOCKED: Issue creation missing phase: label. Add --label 'phase:{name}'." >&2
    exit 2
  fi
  # Deferred issues need: deferred label + TWO spec: labels (source + target)
  if echo "$COMMAND" | grep -qiE 'deferred|defer'; then
    if ! echo "$COMMAND" | grep -qE '\-\-label[= ]*[^ ]*deferred'; then
      echo "BLOCKED: Deferred issues must have 'deferred' label. Add --label 'deferred'." >&2
      exit 2
    fi
    SPEC_COUNT=$(echo "$COMMAND" | grep -oE '\-\-label[= ]*[^ ]*spec:[^ ]*' | wc -l | tr -d ' ')
    if [ "$SPEC_COUNT" -lt 2 ]; then
      echo "BLOCKED: Deferred issues must have TWO spec: labels -- spec:{source} (where discovered) and spec:{blocking} (what must complete before this work can proceed). Found $SPEC_COUNT." >&2
      exit 2
    fi
  fi
fi

# Check GraphQL issue creation
if echo "$COMMAND" | grep -qE 'gh api graphql.*createIssue'; then
  if ! echo "$COMMAND" | grep -qE 'spec:'; then
    echo "BLOCKED: GraphQL issue creation missing spec: label in mutation." >&2
    exit 2
  fi
fi

exit 0
