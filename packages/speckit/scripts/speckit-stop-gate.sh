#!/usr/bin/env bash
# Hook: Stop - Warn if speckit workflow has unresolved items
# Checks for unchecked checklist items, pending iterations, open questions

# Only activate in speckit projects
[ -d ".specify" ] || exit 0

WARNINGS=""

# Check for pending iteration files
if ls specs/*/pending-iteration.md &>/dev/null 2>&1; then
  PENDING=$(ls specs/*/pending-iteration.md 2>/dev/null | head -3 | tr '\n' ', ')
  WARNINGS="${WARNINGS}- Pending iteration(s) not yet applied: ${PENDING%, }"$'\n'
fi

# Check for active spec with unchecked tasks
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null)
ACTIVE_SPEC=""
if echo "$CURRENT_BRANCH" | grep -qE '[0-9]{3}-'; then
  ACTIVE_SPEC=$(echo "$CURRENT_BRANCH" | grep -oE '[0-9]{3}-[a-z0-9-]+' | head -1)
fi

if [ -n "$ACTIVE_SPEC" ]; then
  # Task state lives in beads when the repo has a workspace (speckit-beads).
  if command -v bd >/dev/null 2>&1 && bd where >/dev/null 2>&1; then
    # bd 1.1.0 query gotchas (verified live): the hyphenated value MUST be
    # quoted with the wildcard INSIDE the quotes -- unquoted is a parse error
    # and the {error:...} OBJECT makes bare `jq length` count its keys (2).
    # BD_JSON_ENVELOPE= pins the array shape against a session-level =1
    # (which wraps output in {data:[...]}); the jq type-guard maps any
    # non-array (error object, envelope) to 0.
    OPEN_BEADS=$(BD_JSON_ENVELOPE='' bd query "spec_id=\"${ACTIVE_SPEC}*\" AND status!=closed" --json 2>/dev/null | jq 'if type=="array" then length else 0 end' 2>/dev/null)
    if [ -n "$OPEN_BEADS" ] && [ "$OPEN_BEADS" -gt 0 ] 2>/dev/null; then
      WARNINGS="${WARNINGS}- Spec $ACTIVE_SPEC: $OPEN_BEADS open beads (bd ready to continue)"$'\n'
    fi
  elif [ -f "specs/$ACTIVE_SPEC/tasks.md" ]; then
    # Legacy fallback: tasks.md checkmarks (pre-beads repos).
    # `grep -c` prints 0 AND exits 1 on no match. Use `|| true` so grep's own 0
    # stands; then default.
    UNCHECKED=$(grep -c '^\- \[ \]' "specs/$ACTIVE_SPEC/tasks.md" 2>/dev/null || true); UNCHECKED=${UNCHECKED:-0}
    CHECKED=$(grep -c '^\- \[X\]\|^\- \[x\]' "specs/$ACTIVE_SPEC/tasks.md" 2>/dev/null || true); CHECKED=${CHECKED:-0}
    if [ "$UNCHECKED" -gt 0 ] && [ "$CHECKED" -gt 0 ]; then
      WARNINGS="${WARNINGS}- Spec $ACTIVE_SPEC: $UNCHECKED tasks remaining ($CHECKED completed)"$'\n'
    fi
  fi
fi

if [ -n "$WARNINGS" ]; then
  MESSAGE="SPECKIT STOP CHECK: Open items detected:
$WARNINGS
Consider running /handover to save context for next session."
  jq -cn --arg message "$MESSAGE" \
    '{continue:true,systemMessage:$message}' 2>/dev/null || printf '%s\n' "$MESSAGE" >&2
fi

exit 0
