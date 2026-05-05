---
name: code-review
description: Use for review requests. Prioritizes bugs, regressions, risks, and missing tests.
---

# Code Review

Use this skill when the user asks for a review.

## Review Order

1. Correctness and regressions
2. Safety and security risks
3. Missing or weak tests
4. Performance issues
5. Maintainability concerns

## Rules

- Findings first, ordered by severity, with file references (`file:line`)
- Typical targets: current diff, a specific file, or a PR by number/URL
- Output: **Summary** (1-2 sentences), **Suggestions** (`[file:line]` each), **Blockers** (critical only)
- Use a subagent only when the diff is large enough that an independent read materially improves coverage

## References

- PR-focused checklist: Read `references/pr-review.md` when reviewing a pull request
