---
name: research
description: Use when the user needs structured research rather than implementation.
---

# Research

Use this skill when the task is primarily investigation rather than code changes.

## Workflow

1. Check for existing local notes or prior research before starting fresh.
2. Break the topic into a small set of concrete research angles.
3. Use parallel subagents for independent angles when the topic splits cleanly.
4. Prefer primary sources and recent material for unstable topics.
5. Save or present findings in a structure the next session can reuse.

## Steering

- Prefer official docs, specs, or primary sources over derivative summaries.
- If the topic involves a library or framework, consult context7 before relying on training data.
- Distinguish facts, inferred conclusions, and open questions.
- Keep research read-only unless the user explicitly asked to save a report.
- Use subagents only for independent angles that do not block the next local step.

## References

Read `references/report-template.md` when producing a written report.
