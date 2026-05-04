---
name: commit-push-pr
description: Use when the user wants the current branch committed, pushed, and opened as a PR.
---

# Commit Push PR

Use this skill when the user explicitly wants a commit, push, and PR creation.

## Workflow

1. Inspect branch status, diff, and recent commit style.
2. Stage the intended changes deliberately -- never blind `git add -A`.
3. Create a conventional commit message that matches the real diff.
4. Push the current branch, setting upstream if needed.
5. Create the PR with a concise summary and test plan.

## Steering

- Treat PR creation as explicit user-directed publication, not a default end state.
- Do not hide broad or risky staging inside an overly generic commit message.
- Prefer a short, factual PR body over template bloat.
- Do NOT add AI-branded footers or attribution to the PR body.
- All `gh` commands MUST go through `gh-api.py` -- direct `gh` is blocked.

## References

Read `references/pr-template.md` when structuring the PR body.
