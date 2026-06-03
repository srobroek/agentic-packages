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
6. If still stuck, invoke the `adversarial-challenger` agent; LOAD
   references/adversarial.md for the brief format.

## Rules

- Facts first, theories second. Avoid repeating the same failed fix pattern.
- At most one `adversarial-challenger` agent. Give it only observable facts,
  never your theory.
- The challenger investigates and proposes but never implements fixes. Max 5 rounds.
- Do not invoke this skill recursively. On fix failure, re-enter with new evidence.
- If no fast feedback loop exists, stop and use `diagnose` to create one before
  continuing.

## Workflow turbo-path (optional, Claude only)

The prose Workflow above is the default. IF dynamic workflows are enabled (the "workflow" keyword,
ultracode, or an explicit ask), the challenger escalation (step 6) can run as a budget-bounded
Workflow loop instead of manual SendMessage rounds. Steps 1-5 (fact-gathering, leading assumption,
alternative hypotheses, the disproving check) stay in the main thread -- they need the live repro
and the user. Workflows are a Claude-only feature; where they are unavailable, follow the prose
steps.

Shape (author inline):

- One `agent()` per round, `agentType: 'adversarial-challenger'`, `effort: 'xhigh'`, given ONLY the
  observable-facts brief (`references/adversarial.md` format) -- never your theory.
- Loop while rounds < 5 AND a budget guard holds (`budget.total && budget.remaining() > 50_000`),
  feeding each round the prior challenger output + any new evidence from a main-thread check.
- The challenger proposes and never edits; the main thread runs the smallest disproving check
  between rounds. Stop early when a hypothesis is confirmed or refuted.

`adversarial-challenger` resolves to the existing agent definition -- do not duplicate it. This is a
small win (one agent, serial rounds); the prose path remains entirely adequate when workflows are
off.

## References

- When invoking `adversarial-challenger`, LOAD references/adversarial.md
- For the structured debugging checklist, LOAD references/checklist.md
