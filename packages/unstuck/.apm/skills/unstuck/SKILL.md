---
name: unstuck
description: Escalate stalled debugging by challenging assumptions after the normal diagnosis loop has failed. Use when repeated fixes, same-file re-editing, flaky evidence, circular hypotheses, or going in circles suggest the agent is stuck; bundled diagnose owns first-pass debugging.
---

# Unstuck

Challenge assumptions when debugging is going in circles. In the `core` bundle,
Matt Pocock's `diagnose` skill is installed with `unstuck`; use `diagnose` for
ordinary bug work and return here when the diagnosis loop stalls.

## Trigger Boundary

- Use `diagnose` first when there is no trusted reproduction, fast feedback
  loop, or minimized failing case.
- Use `unstuck` when repeated fixes failed, the same files are being re-edited,
  hypotheses are circular, or evidence contradicts the current framing.
- A `STUCK DETECTOR` hook advisory is a direct trigger: it reports which files
  were re-edited how many times with no commit or passing test run in between.
- Do not use `unstuck` as a replacement for normal test, build, or traceback
  diagnosis.

## Workflow

1. Gather the observable-facts baseline: LOAD references/checklist.md and
   answer each question. If a `STUCK DETECTOR` advisory fired, seed the answers
   from its reported files and re-edit counts instead of re-deriving them.
2. Name the current leading assumption and the evidence for it.
3. Generate 1-3 alternative hypotheses that would explain all observations.
4. Run the smallest check that can disprove the leading assumption.
5. If still stuck, invoke the `adversarial-challenger` agent; LOAD
   references/adversarial.md for the brief format.

## Rules

- Facts first, theories second. Avoid repeating the same failed fix pattern.
- At most one `adversarial-challenger` agent. Give it only observable facts,
  never your theory.
- The challenger investigates and proposes but never implements fixes. Max 5 rounds.
- Do not invoke this skill recursively. On fix failure, re-enter with new evidence.
- If no fast feedback loop exists, stop and use `diagnose` to create one before
  continuing.

## Workflow turbo-path (optional, Claude Code only)

Claude Code only -- on other runtimes, skip this section and follow the Workflow above.

The prose Workflow above is the canonical path and is always sufficient. If dynamic workflows are
enabled (the "workflow" keyword, ultracode, or an explicit ask), the challenger escalation (step 5)
can run as a budget-bounded Workflow loop instead of manual SendMessage rounds. Steps 1-4
(fact-gathering, leading assumption, alternative hypotheses, the disproving check) stay in the main
thread -- they need the live repro and the user.

Shape (author inline):

- One `agent()` per round, `agentType: 'adversarial-challenger'`, `effort: 'xhigh'`, given only the
  observable-facts brief (`references/adversarial.md` format) -- never your theory.
- Loop while rounds < 5 AND a budget guard holds (`budget.total && budget.remaining() > 50_000`),
  feeding each round the prior challenger output + any new evidence from a main-thread check.
- The challenger proposes and never edits; the main thread runs the smallest disproving check
  between rounds. Stop early when a hypothesis is confirmed or refuted.

`adversarial-challenger` resolves to the existing agent definition -- do not duplicate it. This is a
small win (one agent, serial rounds); the prose path remains entirely adequate when workflows are
off.
