---
name: unstuck
description: Escalate stalled debugging by challenging assumptions after the normal diagnosis loop has failed. Use when repeated fixes, same-file re-editing, flaky evidence, circular hypotheses, or going in circles suggest the agent is stuck; bundled diagnose owns first-pass debugging.
---

# Unstuck

Use this skill when debugging is going in circles. In the `core` bundle,
Matt Pocock's `diagnose` skill is installed with `unstuck`; use `diagnose` for
ordinary bug work and return here when the diagnosis loop stalls.

## Trigger Boundary

- Use `diagnose` first when there is no trusted reproduction, fast feedback
  loop, or minimized failing case.
- Use `unstuck` when repeated fixes failed, the same files are being re-edited,
  hypotheses are circular, or evidence contradicts the current framing.
- Do not use `unstuck` as a replacement for normal test, build, or traceback
  diagnosis.

## Workflow

1. Confirm the diagnosis baseline:
   - failing command and exact error
   - smallest known reproduction or why none exists
   - what `diagnose` found or why it was skipped
2. Gather only observable facts:
   - Failing command and exact error
   - Affected files and recent edits
   - `git diff --stat` and `git log --oneline -10`
   - Fixes already tried and their observed results
3. Name the current leading assumption and the evidence for it.
4. Generate 1-3 alternative hypotheses that would explain all observations.
5. Run the smallest check that can disprove the leading assumption.
6. If still stuck, invoke the `adversarial-challenger` agent using
   `references/adversarial.md` as the brief format.

## Rules

- Facts first, theories second. Avoid repeating the same failed fix pattern.
- At most one `adversarial-challenger` agent. Give it only observable facts,
  never your theory.
- The challenger investigates and proposes but never implements fixes. Max 5 rounds.
- Do not invoke this skill recursively. On fix failure, re-enter with new evidence.
- If no fast feedback loop exists, stop and use `diagnose` to create one before
  continuing.

## References

- Read `references/adversarial.md` when invoking `adversarial-challenger`
- Read `references/checklist.md` for the structured debugging checklist
