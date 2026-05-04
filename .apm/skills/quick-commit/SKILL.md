---
name: quick-commit
description: Use for a fast local commit without opening a PR.
---

# Quick Commit

Use this skill for fast local commits without PR creation.

## Workflow

1. Run `scripts/status.sh` to inspect git status and changeset needs.
2. Decide whether a changeset is required using `references/changeset-policy.md`.
3. Stage the intended files deliberately -- avoid blind `git add -A`.
4. Write a concise conventional commit message aligned with the actual diff.
5. Commit and show the resulting head commit.

## Steering

- Do not hide broad staging behind a vague commit message.
- Keep the commit message aligned with the actual diff, not intended future work.
- If a changeset is required, create it before committing.
- Never commit files that likely contain secrets (.env, credentials).

## Scripts

- Status inspection: `scripts/status.sh`

## References

Read `references/changeset-policy.md` when deciding whether a changeset entry is needed.
