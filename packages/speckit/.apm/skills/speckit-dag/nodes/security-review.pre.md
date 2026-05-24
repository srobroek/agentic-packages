# /speckit.security-review — before you run this

## Came from
- /speckit.tasks (pre-impl — review plan/tasks for security concerns)
- /speckit.qa.run (post-impl — review implementation diff)
- /speckit.review.run (only if user explicitly skips qa)

## Preconditions
- SOFT: implementation diff present (post-impl path)

## Context absorbed from steering
- Dedicated security audit. In pre-impl, reviews plan and tasks for security risks. In post-impl, reviews the actual code diff. Run the /security-review skill as a subagent. In pre-impl, runs in parallel with /speckit.critique.run. In post-impl, runs in parallel with /speckit.code-review.
