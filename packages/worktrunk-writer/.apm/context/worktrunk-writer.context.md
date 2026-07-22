# Worktrunk delegated-agent lifecycle

OWNERSHIP
MUST Worktrunk own branch-to-path allocation, lifecycle hooks, merge, removal, activity markers, and lifecycle logs.
MUST The parent pre-create one named Worktrunk worktree per delegated tool-using agent before spawning it.
NOT Use harness worktree isolation, raw `git worktree`, or a shared checkout for a tool-using subagent.

LEASE
MUST Run the `worktrunk-writer` skill's prepare command before delegation, then bind the returned harness agent ID before authorizing tool use.
MUST Every tool-using subagent validate its lease before its first tool call and keep every command or write inside the returned path.
MUST Give each read-only reviewer a unique short-lived review branch from the exact review target; remove it after evidence is reported.
DEFAULT A subagent that never invokes a tool requires no worktree.

LIFECYCLE
MUST Treat project-hook approval as a human trust decision; never bypass it with `--yes`.
MUST Use Worktrunk schema 2 for fleet, merge, CI, and cleanup evidence.
MUST Use `wt merge` and `wt remove --foreground`; never force dirty or unintegrated cleanup.
DEFAULT Read Worktrunk command and branch logs by path; record only outcome anchors in the task system.
