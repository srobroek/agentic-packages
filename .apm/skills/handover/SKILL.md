---
name: handover
description: Use when ending a session or switching context. Saves a recovery prompt for the next session.
---

# Handover

Use this skill when ending a session with incomplete work, handing off to a later session, or switching away from a complex branch.

## Workflow

1. Detect repo root, branch, and active worktree if relevant.
2. Gather the current implementation state:
   - changed files and git status
   - active spec/task progress
   - architectural decisions made this session
   - open risks or blockers
   - next concrete steps
3. Write a complete recovery prompt to `~/.claude/handover/`.
4. Replace any older handover for the same project and branch.

## Rules

- The saved handover MUST be self-contained -- no external context needed to resume.
- Record exact file paths and next steps, not vague summaries.
- If work is mid-refactor, explain the incomplete state explicitly.
- NEVER store ephemeral state in global memory -- handover files are the session bridge.

## References

Read `references/template.md` when structuring the handover file.
