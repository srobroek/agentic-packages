---
name: commit-push-merge
description: Use only for explicit direct-merge requests. Commit, push, and merge with confirmation.
---

# Commit Push Merge

Use this skill only when the user explicitly wants a direct merge workflow.

## Workflow

1. Inspect status, diff, and recent commit style.
2. Stage the intended changes deliberately.
3. Create a conventional commit message aligned with the diff.
4. Push the feature branch.
5. Confirm the merge target with the user before merging.
6. Report the resulting merge state clearly.

## Steering

- Prefer `commit-push-pr` unless the user clearly wants direct merge behavior.
- NEVER merge to the main branch implicitly -- always confirm with the user.
- Confirm branch deletion separately; do not assume cleanup preferences.
- Treat this as a high-trust workflow, not a casual default.
- All `gh` commands MUST go through `gh-api.py` -- direct `gh` is blocked.

## References

Read `references/merge-checklist.md` before executing the merge step.
