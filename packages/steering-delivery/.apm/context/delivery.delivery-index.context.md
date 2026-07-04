# Delivery Cadence

Work like a developer who commits continuously, not one who dumps a finished
branch at the end.

- Commit and push after every meaningful, self-contained step — a passing unit
  of work, a green refactor, a completed sub-task — not once at the end.
- Keep commits atomic: one logical change each, with a message that matches the
  diff. Do not batch unrelated work, or a whole feature, into one large commit.
- Leave no unpushed local work at a stopping point. Push committed work to its
  remote branch so nothing lives only in a local or disposable (`/tmp`) worktree
  that may not survive. If a push is blocked, say so explicitly rather than
  silently leaving work local.
- Before ending a session or handing off, confirm the tree is clean and the
  branch is pushed. Verify what actually landed (`git log`, `git status`) — do
  not assume a chained commit-and-push succeeded.

This is the default working rhythm, not something to do only when asked. It does
not override the rules on when to open PRs, merge, or run other outward-facing
actions — those still need their normal triggers and confirmations. It concerns
how you preserve work in progress, not when you publish or release it.
