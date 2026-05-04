---
name: github-admin
description: Use for GitHub operations beyond local git, including issues, labels, projects, and PR admin.
---

# GitHub Admin

Use this skill for GitHub-hosted workflow operations that do not belong inside a repo-specific bootstrap or local git-only skill.

## Preferred Flow

1. Use normal `gh` commands for interactive one-off work, including simple reads, single PR/issue operations, and repository administration.
2. Use `scripts/gh-api.py` only when repeated operations, retries, rate limits, batch execution, project automation, or many content-creating requests matter.
3. Prefer plain `gh api` for one-off REST or GraphQL calls; switch to the wrapper when issuing a sequence of mutative API calls.
4. Keep local git operations in the git-focused skills; use this skill only for GitHub-hosted concerns.

## Steering

- Plain `gh` is the default for interactive usage.
- Do not route one-off mutative commands through `scripts/gh-api.py` solely because they mutate GitHub state.
- Use `scripts/gh-api.py` for large or repeated batch work where throttling, retries, or rate-limit accounting are useful.
- Prefer REST over GraphQL except for operations with no REST equivalent (`addBlockedBy`, `addSubIssue`, project field mutations).
- Use `--body-file` for PR/issue bodies, never inline `--body` with long text.

## Scripts

- Rate-limited GitHub wrapper: `scripts/gh-api.py`

## References

- Read `references/usage.md` when routing a GitHub CLI command or deciding wrapper vs plain `gh`.
- Read `references/projects-and-rate-limits.md` when working with GitHub Projects, batch operations, or rate limit concerns.
