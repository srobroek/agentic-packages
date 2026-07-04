---
description: Choose subagent worktree isolation deliberately; commit isolated work before finishing; clean up worktrees and build artifacts when done.
applyTo: "**/*"
---

# Subagent worktree isolation

A `PreToolUse:Agent` hook posts a **non-blocking advisory** on every subagent
spawn that has not declared isolation. It never denies the spawn — it only
reminds you to choose deliberately. You decide, by what the subagent does:

- **Writes files into THIS repository AND runs in parallel with other writers**
  → set `isolation: "worktree"` on the `Agent` call. The child runs in its own
  git worktree, branched from your current `HEAD` (the repo sets
  `worktree.baseRef: "head"`) as `worktree-<name>`. This is what keeps
  concurrent writers from colliding on one working tree.
- **Only inspects; never writes** → no isolation needed. The child shares your
  working directory read-only.
- **Writes a DIFFERENT repository on its own private path** (e.g. a clone under
  `/tmp`) → no worktree of THIS repo needed. But if you run several such writers
  at once, give each its own unique checkout path — two writers sharing one
  external checkout corrupt each other exactly like two sharing one worktree.
- **A lone writer of THIS repo** (no concurrent siblings) → isolation is
  optional; editing the current tree directly is fine when nothing else writes
  it at the same time.

Once `isolation` is set on the call, the advisory stays silent — you have made
the choice.

## Commit isolated work before finishing

If a subagent runs in a worktree (`isolation: "worktree"`), instruct it to
**commit its work before it returns**. The worktree *branch* persists after the
subagent finishes, but uncommitted changes in that worktree can be lost when the
worktree is later cleaned up. A committed `worktree-<name>` branch is safe and
can be merged, cherry-picked, or reviewed by the parent afterward. This applies
only to isolated subagents — a subagent editing the shared tree directly leaves
its changes in your checkout as usual.

## Clean up worktrees and build artifacts when done

A finished worktree is not free to leave behind: each one accumulates its own
compilation artifacts (a Rust `target/` dir alone can reach tens of GB), and
dead worktrees silently fill the disk. Whoever creates a worktree owns its
removal:

- When an agent finishes and its branch is committed (and merged or harvested),
  remove the worktree: `rm -rf <worktree>/target` (and other build dirs such as
  `node_modules/`) followed by `git worktree remove <worktree>` and
  `git worktree prune`.
- Orchestrators that fan out parallel worktree agents must sweep after fan-in:
  once each child's result is collected, its worktree and artifacts go.
- Periodically check `git worktree list` for strays and remove any worktree
  whose work is done. Do not rely on a shared build directory to contain the
  cost — the fix is not letting dead worktree artifacts accumulate.

## You own concurrency safety

The advisory evaluates one spawn at a time and cannot see how many siblings you
are launching alongside it. Silence does not mean your fan-out is safe. When you
launch several writers at once, guarantee they never share a working tree: give
each its own `isolation: "worktree"` (or a `parallel-coder`-style dispatcher
that worktrees each child), assign disjoint file scopes, or run them serially.
