---
name: code-review
description: Review code changes for bugs, regressions, security risks, and missing tests, reporting findings by severity. Use when the user asks to review a diff or the current changes, check a change for bugs or regressions, audit a change set, or review a PR by number or URL.
---

# Code Review

Review a diff, file, or PR and report findings ordered by severity.

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
- If the runtime supports subagents, use one only when the diff is large enough that an independent read materially improves coverage

## References

- PR-focused checklist: when reviewing a pull request, LOAD references/pr-review.md
