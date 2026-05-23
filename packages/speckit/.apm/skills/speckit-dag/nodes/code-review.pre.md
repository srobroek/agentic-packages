# /speckit.code-review — before you run this

## Came from
- /speckit.qa.run (default)
- /speckit.review.run (acceptable if qa skipped)

## Preconditions
- SOFT: implementation diff present

## Context absorbed from steering
- General-purpose code review: correctness, regressions, security risks, missing tests, performance, maintainability. Complements the spec-aware review.run. Run the /code-review skill as a subagent against the current branch diff. Can run in parallel with /speckit.security-review.
