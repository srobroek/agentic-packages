# /speckit.fix-findings — before you run this

## Came from
- /speckit.review.run · /speckit.qa.run (when findings surfaced)

## Preconditions
- SOFT: `specs/<feat>/review-report.md` or `qa-report.md` with findings

## Context absorbed from steering
- Automated analyze-fix-reanalyze loop bounded by `max_iterations` (default 10 in our override).
