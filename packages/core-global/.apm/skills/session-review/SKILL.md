---
name: session-review
description: Use when wrapping up a session. Audits corrections, lessons, TODOs, and follow-up work. Presents findings and recommends handoffs to handover, revise-claude-md, steering-audit, or memory.
---

# Session Review

Audit the session for patterns worth capturing. This skill diagnoses — it does
not write rules, edit CLAUDE.md, or save memory directly.

## Steps

1. Review the session for user corrections and non-obvious discoveries.
2. Scan changed files for unresolved TODO/FIXME markers without corresponding issues.
3. Flag patterns that should become steering rules, hooks, or skills — but do not create them.
4. Separate what should carry forward versus be dropped.
5. Present findings. Ask before saving each item to long-term memory.
6. If there is unfinished implementation work, recommend running **handover**.

## Output Format

- **Corrections captured**: count
- **Lessons to save**: list (ask before writing)
- **TODOs without issues**: list
- **Proposed improvements**: list with recommended action:
  - Steering rule → run **steering-audit**
  - CLAUDE.md update → run **revise-claude-md**
  - New skill idea → run **write-a-skill**
  - Hook needed → run **agent-management**

## Steering

- Prefer actionable findings over narrative recap.
- Separate confirmed lessons from speculative ideas.
- If a lesson applies across projects, recommend promotion to global steering.

## References

Read `references/checklist.md` to keep the review consistent.
