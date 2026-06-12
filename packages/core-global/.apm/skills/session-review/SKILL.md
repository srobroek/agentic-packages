---
name: session-review
description: Audit the ending session for corrections, lessons, unresolved TODOs, and follow-up work, then recommend handoffs to `handover`, `audit-steering`, `optimize-steering`, or `write-a-skill`. Use when the user says wrap up, review this session, what did we learn, or before a handover.
---

# Session Review

Audit the session for patterns worth capturing. This skill diagnoses — it does
not write rules, edit steering files, or persist memory directly.

## Steps

1. Review the session for user corrections and non-obvious discoveries.
2. Scan changed files for unresolved TODO/FIXME markers without corresponding issues.
3. Flag patterns that should become steering rules, hooks, or skills — but do not create them.
4. Separate what should carry forward versus be dropped.
5. Present findings. Ask before persisting each item. Use the runtime's memory
   feature when one exists; otherwise route durable lessons to `handover` or a
   steering rule.
6. If there is unfinished implementation work, recommend running `handover`.

## Output Format

- Corrections captured: count
- Lessons to save: list (ask before writing)
- TODOs without issues: list
- Proposed improvements: list with recommended action:
  - Steering rule or hook gap → run `audit-steering`
  - Steering doc or compiled-instructions update → run `optimize-steering`
  - New skill idea → run `write-a-skill`
  - APM package or hook install → run `agent-management`

## Steering

- Prefer actionable findings over narrative recap.
- Separate confirmed lessons from speculative ideas.
- If a lesson applies across projects, recommend promotion to global steering.

## References

Read `references/checklist.md` to keep the review consistent.
