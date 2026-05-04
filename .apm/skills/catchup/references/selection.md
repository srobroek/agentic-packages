# Catchup Selection Rules

- Match project name first.
- Prefer exact branch match over keyword matches.
- If the handover is stale, warn but still use it.
- If the recorded worktree no longer exists, note it and continue with the handover body.
- If there is no handover, inspect:
  - `git branch --show-current`
  - `git status --short`
  - recent active spec artifacts if `.specify/` exists

