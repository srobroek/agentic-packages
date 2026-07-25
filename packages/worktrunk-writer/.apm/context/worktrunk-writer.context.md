# Worktrunk delegated-agent lifecycle

OWNERSHIP
MUST Worktrunk own branch-to-path allocation, lifecycle hooks, merge, removal, activity markers, and lifecycle logs.
MUST The parent pre-create one named Worktrunk worktree per claim-holder or independently dispatched tool user before task delivery.
DEFAULT A claim-holder may explicitly bind throwaway child contexts to its own path and lease.
NOT Use harness worktree isolation, raw `git worktree`, or an unbound shared checkout.

LEASE
MUST Run the `worktrunk-writer` skill before delegation; nothing else starts the contract. Its hook advises an unleased task-bearing spawn but cannot deny one, because a spawn payload does not say whether the child will write.
MUST Treat enforcement as binding once the protocol starts: a bound runtime context, a leased checkout, and a `WAIT` allocation are all policed, and cross-lease access is rejected.
MUST Bind the parent-visible runtime handle and hook-visible context acknowledgement before task delivery; the identities are not interchangeable.
MUST A Beads-backed agent use its bound T0 action only to claim and validate; repository tools start after validation.
MUST Keep every command or write inside the returned path.
MUST A Claude Agent Bash call from an inherited parent directory start with `cd -- <leased-path>`; Codex sets `workdir` to that path.
MUST Give each read-only reviewer a unique short-lived review branch from the exact review target; remove it after evidence is reported.
DEFAULT A subagent that never invokes a tool requires no worktree.

LIFECYCLE
MUST Treat project-hook approval as a human trust decision; never bypass it with `--yes`.
MUST Pin `list.json-schema=2` and read `branch` plus `worktree.path` for
  fleet, merge, CI, and cleanup evidence.
MUST Use `wt merge` and `wt remove --foreground`; never force dirty or unintegrated cleanup.
DEFAULT Read Worktrunk command and branch logs by path; record only outcome anchors in the task system.
