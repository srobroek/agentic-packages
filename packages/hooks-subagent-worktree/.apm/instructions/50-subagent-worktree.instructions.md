---
description: Declare worktree isolation up front on every subagent spawn (avoids a deny+retry round-trip).
applyTo: "**/*"
---

# Subagent worktree isolation

A `PreToolUse` guard requires every subagent spawn (the `Agent`/`Task` tool) to
declare its worktree-isolation choice. If you do not, the spawn is **denied** and
you must re-issue it — so decide up front and tag the call on the first try.

Choose by what the subagent does to the filesystem:

- **Writes files into THIS repository, and those changes should stay isolated**
  from your working tree → set `isolation: "worktree"` on the `Agent` call. The
  child runs in its own git worktree.
- **Otherwise** → append the exact token `[iso:skip]` to the `description` field
  and do **not** set an `isolation` field. "Otherwise" covers three cases:
  1. read-only (the subagent only inspects, never writes);
  2. it operates on a DIFFERENT repository (e.g. a clone under /tmp), so a
     worktree of *the current repo* is irrelevant;
  3. it WRITES but must edit the parent working tree **directly** — its changes
     are meant to land in your current checkout, so isolating them into a
     throwaway worktree would strip the result.

`[iso:skip]` only means "the current-repo worktree mechanism does not apply." It
does **not** mean "no isolation is needed." This guard sees only one spawn at a
time; it cannot know how many siblings you are launching concurrently. **You**
must guarantee that concurrent writers never share a working tree:

- Spawning several **direct-edit** writers (`coder`, or anything editing the
  parent tree in place) at once → they collide on your checkout. Run them
  serially, give each a disjoint file scope, or use `parallel-coder` (isolated
  worktrees) instead.
- Spawning several **different-repo** writers at once → each must get its **own
  unique checkout path**, not a shared per-repo directory. Pass an explicit
  isolated path per spawn (e.g. `external-repo-worker`, which defaults to a
  unique path per invocation). Two writers in one external checkout corrupt each
  other exactly like two in one worktree would.

Do not add an `isolation` field set to anything other than `"worktree"` — the
tool schema has no `"none"` value, so "no isolation" is expressed only by the
`[iso:skip]` sentinel, never by an isolation field. The guard strips the
`[iso:skip]` token from the description before the spawn proceeds.
