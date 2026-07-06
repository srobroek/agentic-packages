---
name: session-review
description: Audit the ending session for corrections, lessons, and follow-up work. Triggers on "wrap up", "review this session", "what did we learn", or before a handover.
---

# Session Review

Audit the session for patterns worth capturing. This skill diagnoses — it does
not write rules, edit steering files, or persist memory directly.

## Steps

1. Review the session for user corrections and discoveries the user would not find in docs or code comments.
2. Scan changed files for unresolved TODO/FIXME markers without corresponding issues.
3. Flag patterns that should become steering rules, hooks, or skills — but do not create them.
4. Separate what should carry forward versus be dropped.
5. Present findings. Ask before persisting each item:
   - If a memory tool is available, write there.
   - Otherwise route durable lessons to `handover` or a steering rule.
6. If there is unfinished implementation work, recommend running `handover`.

## Drop vs. carry criteria

- **Drop:** one-off context, session noise, content already captured in steering.
- **Carry:** user corrections, discoveries the user would not find in docs or code comments, recurring patterns not tied to this repo's structure, stack, or one-off decisions.

## Output Format

- Corrections captured: count
- Lessons to save: list (ask before writing)
- TODOs without issues: list
- Proposed improvements: list with recommended action:
  - Steering rule or hook gap → run `audit-steering`
  - Steering doc or compiled-instructions update → run `audit-steering`
  - New skill idea → run `write-agentic`
  - APM package or hook install → run `agent-management`

## Steering

- Prefer actionable findings over narrative recap.
- Separate confirmed lessons from speculative ideas.
- If a lesson is not tied to this repo's structure, stack, or one-off decisions, recommend promotion to global steering.

## References

Read `references/checklist.md` to keep the review consistent.
