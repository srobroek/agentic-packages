---
description: Declare worktree isolation up front on every subagent spawn (avoids a deny+retry round-trip).
applyTo: "**/*"
---

# Subagent worktree isolation

A `PreToolUse` guard requires every subagent spawn (the `Agent`/`Task` tool) to
declare how the child relates to the filesystem. If you do not, the spawn is
**denied** and you must re-issue it — so decide up front and tag the call on the
first try.

Pick exactly ONE, by what the subagent does:

- **Writes files into THIS repository, and those changes should stay isolated**
  from your working tree → set `isolation: "worktree"` on the `Agent` call. The
  child runs in its own git worktree.
- **Only inspects; never writes** → append `[iso:readonly]` to the
  `description`.
- **Writes a DIFFERENT repository on its own private path** (e.g. a clone it
  makes under `/tmp`) → append `[iso:extern]`. This is safe ONLY because the
  clone is agent-private and ephemeral. A **shared external checkout** (another
  long-lived working copy, a dotfiles/chezmoi source, anything a person or
  another agent also edits) is **not** `[iso:extern]` — two agents writing it
  race exactly like two agents in this repo. Have the child clone to its own
  path, or do not parallelize the write.
- **Writes THIS repository's working tree directly** — the result must land in
  your current checkout, so a throwaway worktree would strip it → append
  `[iso:direct]`. **This is allowed only when you are already in a git
  worktree.** If you are on the **primary checkout**, the spawn is denied: move
  into a worktree first (`claude --worktree <name>`, or `git worktree add`) and
  re-issue from there, so the child's direct writes never collide on the shared
  primary tree.

Do not add an `isolation` field set to anything other than `"worktree"` (or
`"remote"`) — the tool schema has no `"none"` value, so "no isolation" is
expressed only by an `[iso:*]` sentinel, never by an isolation field. The guard
strips the matched sentinel from the description before the spawn proceeds.

## The guard cannot see concurrent siblings

The guard evaluates one spawn at a time; it has no visibility into how many
other subagents you are launching alongside this one. A tag being *allowed*
only means that spawn is individually well-formed — it does not mean your
overall fan-out is safe. **You** are responsible for guaranteeing that
concurrent writers never share a working tree:

- Spawning several **`[iso:direct]`** writers at once (e.g. multiple `coder`
  agents editing the parent tree in place) → they collide on your checkout
  exactly as if two people ran uncoordinated `git` commands in the same
  directory. Run them serially, give each a disjoint file scope, or use
  `isolation: "worktree"` (or a `parallel-coder`-style dispatcher that puts
  each child in its own worktree) instead.
- Spawning several **`[iso:extern]`** writers at once → each must get its
  **own unique checkout path**, not a shared per-repo clone directory. Pass an
  explicit isolated path per spawn (e.g. `external-repo-worker`, which
  defaults to a unique path per invocation). Two writers sharing one external
  checkout corrupt each other exactly like two writers sharing one worktree
  would — `[iso:extern]`'s safety guarantee depends on the clone being
  private to that one spawn.
