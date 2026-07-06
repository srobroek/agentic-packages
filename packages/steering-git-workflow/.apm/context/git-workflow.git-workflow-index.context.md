# Git Workflow

Branching:

- Never start new work on main/master; create or reuse a feature branch.
- Reuse an existing branch/worktree only when it was created for this task.

Shipping (choose one, confirm if ambiguous):

- PR (`gh pr create`) — default for anything reviewed or outward-facing.
  Body: what changed, why, test plan. One close keyword per issue line.
- Local merge to main — only when the user asks or the repo has no PR flow.
  Use `git merge --no-ff` for feature branches; pass an explicit strategy
  flag to `gh pr merge` (`--squash`/`--merge`/`--rebase`).

Before push: run the project's test/verify command if code changed; report
failures instead of pushing over them.

Before merge: destination confirmed, checks green, no uncommitted work left,
ask about deleting the merged branch.

Changesets (repos using them): add one for behavior/API/breaking changes;
skip for docs, tests, CI, and no-behavior refactors.
