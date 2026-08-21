# Subagent worktree isolation

A `PreToolUse:Agent` hook posts a **non-blocking advisory** (full text in the
hook's own heredoc) on every subagent spawn that has not declared isolation --
never a deny, just a reminder to choose deliberately. Silent once `isolation`
is set on the call.

Nuance the advisory doesn't cover: several writers of a **different** repo, on
private paths, still corrupt each other if they share one external checkout --
give each its own path, same rule as sharing a worktree.

A committed `worktree-<name>` branch is safe to merge, cherry-pick, or review
afterward -- only isolated subagents need this; one editing the shared tree
directly leaves its changes in your checkout as usual.

## You own concurrency safety

The advisory evaluates one spawn at a time and cannot see how many siblings you
are launching alongside it. Silence does not mean your fan-out is safe. When you
launch several writers at once, guarantee they never share a working tree: give
each its own `isolation: "worktree"` (or a `parallel-coder`-style dispatcher
that worktrees each child), assign disjoint file scopes, or run them serially.
