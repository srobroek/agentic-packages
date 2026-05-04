---
name: catchup
description: Use when resuming work in an existing project. Restores context from a handover instead of rediscovering it.
---

# Catchup

Use this skill to resume work from the latest saved handover.

## When To Use

- Starting a new session in an active project
- Recovering after context loss or `/clear`
- Re-entering a branch with prior unfinished work

## Workflow

1. Detect repo root and current branch.
2. Look for matching handovers under `~/.claude/handover/`.
3. Prefer an exact branch match; if multiple candidates exist, pick the most relevant.
4. Read the chosen handover fully and treat it as the authoritative recovery prompt.
5. Fall back to lightweight git inspection only if no handover exists.

## Rules

- Prefer handover state over reconstructing context from scratch.
- Do not re-summarize a handover that already contains a recovery plan.
- Only use git fallback when no handover is available.
- Keep the resume flow fast and factual.

## References

Read `references/selection.md` when choosing between multiple handover candidates.
