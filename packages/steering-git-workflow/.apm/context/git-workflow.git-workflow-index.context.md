# Git Workflow

LEGEND: Rules carry stable IDs (GW-n) cited by the enforcing hooks.

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

Verifying work landed:

MUST GW-3: in a squash-merge repo, prove work reached main by CONTENT, not
ancestry. Invalid: `git merge-base --is-ancestor` and `git branch --merged` — a
squashed tip is never an ancestor of main; equally invalid is reading a
non-empty `git merge-tree` as not-landed — a squashed branch keeps its diverged
merge-from-main history. Valid: `git cat-file -e origin/main:<path>`, a file or
tree diff against origin/main, or the change's presence in the squash commit.
When a path is absent from main's tip, an empty `git log origin/main -- <path>`
proves it never landed; a non-empty log means it landed and was later removed
or renamed.

Changesets (repos using them): add one for behavior/API/breaking changes;
skip for docs, tests, CI, and no-behavior refactors.

Session cadence (enforced by stop-hook):

MUST GW-1: commit all tracked changes before ending a session.
MUST GW-2: push all committed work before ending — commits on an unpushed branch may be lost.
