# Adversarial Challenge Pattern

Use this pattern when invoking the `adversarial-challenger` agent after the
normal diagnosis loop is going in circles.

## Inputs

Give the challenger only observable facts:

- exact failing command
- exact error output
- affected files
- recent edits
- what has already been tried
- current reproduction or feedback loop
- why the main agent believes it is stuck

Do not give the challenger your preferred root-cause theory up front.

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
