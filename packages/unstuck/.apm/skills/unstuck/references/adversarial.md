# Adversarial Challenge Pattern

Use this pattern when invoking the `adversarial-challenger` agent after the
normal diagnosis loop is going in circles.

## Inputs

Give the challenger only observable facts -- the answers gathered via
`references/checklist.md` plus why the main agent believes it is stuck. Never
include the preferred root-cause theory.

## Challenge Pass

1. Reproduce the failure independently.
2. Trace the execution path without assuming the previous fix attempts were correct.
3. Identify the hidden assumption behind each attempted fix.
4. Generate 1-3 alternative root causes.
5. Propose the smallest diagnostic that would disprove the current leading theory.

## Output Shape

- Assumptions identified
- Independent findings
- Alternative hypotheses
- Strongest counter-argument
- Next confirming test
