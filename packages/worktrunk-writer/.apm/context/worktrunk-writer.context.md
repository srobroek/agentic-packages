# Worktrunk delegated-agent lifecycle

OWNERSHIP
MUST Worktrunk own branch-to-path allocation, lifecycle hooks, merge, removal, activity markers, and lifecycle logs.
MUST The parent pre-create one named Worktrunk worktree per claim-holder or independently dispatched tool user before spawning it.
DEFAULT A claim-holder may explicitly bind throwaway child contexts to its own path and lease.
NOT Use harness worktree isolation, raw `git worktree`, or an unbound shared checkout.

LEASE
MUST Run the `worktrunk-writer` skill's prepare command before delegation, then bind the returned harness agent ID before authorizing tool use.
MUST A Beads-backed agent use its bound T0 action only to claim and validate; repository tools start after validation.
MUST Keep every command or write inside the returned path.
MUST Give each read-only reviewer a unique short-lived review branch from the exact review target; remove it after evidence is reported.
DEFAULT A subagent that never invokes a tool requires no worktree.

LIFECYCLE
MUST Treat project-hook approval as a human trust decision; never bypass it with `--yes`.
MUST Use the Worktrunk 0.62 JSON-array contract with top-level `branch` and
  `path` for fleet, merge, CI, and cleanup evidence.
MUST Use `wt merge` and `wt remove --foreground`; never force dirty or unintegrated cleanup.
DEFAULT Read Worktrunk command and branch logs by path; record only outcome anchors in the task system.
