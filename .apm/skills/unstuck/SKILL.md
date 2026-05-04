---
name: unstuck
description: Use when debugging has stalled. Reframes the problem and challenges weak assumptions.
---

# Unstuck

Use this skill when debugging is going in circles.

## Workflow

1. State the failing behavior precisely.
2. Gather only observable facts:
   - Failing command and exact error
   - Affected files and recent edits
   - `git diff --stat` and `git log --oneline -10`
3. Challenge the current assumption set.
4. Generate 1-3 alternative hypotheses.
5. Test the smallest discriminating check first.
6. If needed, escalate to deeper rounds (config check, source tracing, adversarial challenge).

## Rules

- Facts first, theories second. Avoid repeating the same failed fix pattern.
- At most one challenger subagent. Give it only observable facts, never your theory.
- The challenger investigates and proposes but never implements fixes. Max 5 rounds.
- Do not invoke this skill recursively. On fix failure, re-enter with new evidence.

## References

- Read `references/adversarial.md` when spawning a challenger subagent
- Read `references/checklist.md` for the structured debugging checklist
