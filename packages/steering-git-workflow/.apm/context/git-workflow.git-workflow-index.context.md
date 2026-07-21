# Git Workflow

LEGEND: Rules carry stable IDs (GW-n) cited by the enforcing hooks.

Branching:

- Never start new work on main/master; create or reuse a feature branch.
- Reuse an existing branch/worktree only when it was created for this task.

Shipping (choose one, confirm if ambiguous):

- PR (`gh pr create`) — default for anything reviewed or outward-facing.
  Agent-authored PRs start as drafts (`gh pr create --draft`). Promote with
  `gh pr ready` only after implementation, local validation, and required
  agent review are complete and no known blocker remains.
  Body: what changed, why, test plan. One close keyword per issue line.
- Local merge to main — only when the user asks or the repo has no PR flow.
  Use `git merge --no-ff` for feature branches; pass an explicit strategy
  flag to `gh pr merge` (`--squash`/`--merge`/`--rebase`).

Beads linkage (when `bd where` succeeds):

- Before PR creation, create one open task bead labeled `pr:merge` and
  `agent:integrator`, with branch/repo/origin metadata. For every closing work
  bead, add `bd dep add <work-bead> <merge-bead>` before approval freezes the
  graph.
- Add a final `## Beads` section with one `Tracks-Bead: <id>` line for each
  work bead represented by the PR, exactly one `Merge-Bead: <id>`, and
  `Closes-Bead: <id>` for each predeclared completion edge. Tracking alone
  does not imply automatic closure.
- Immediately after creation, stamp the PR number/base/head anchors onto the
  merge bead. The merge bead is durable discovery; GitHub history scans are
  not the queue.
- Keep implementation beads open at `state:reported` or `state:approved`
  while their PR is unmerged. The merge integrator verifies landing and
  completion before closing a `Closes-Bead` target.
- Draft PRs are work-in-progress and are not merge-queue entries. Automated
  release PRs are owned by the release system, not the ordinary merge queue.

Before push: run the project's test/verify command if code changed; report
failures instead of pushing over them.

Before merge: destination confirmed, checks green, no uncommitted work left,
ask about deleting the merged branch.

Changesets (repos using them): add one for behavior/API/breaking changes;
skip for docs, tests, CI, and no-behavior refactors.

Session cadence (enforced by stop-hook):

MUST GW-1: commit all tracked changes before ending a session.
MUST GW-2: push all committed work before ending — commits on an unpushed branch may be lost.
