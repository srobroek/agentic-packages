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
     worktree of the current repo is irrelevant;
  3. it WRITES but must edit the parent working tree **directly** — its changes
     are meant to land in your current checkout, so isolating them into a
     throwaway worktree would strip the result.

Do not add an `isolation` field set to anything other than `"worktree"` — the
tool schema has no `"none"` value, so "no isolation" is expressed only by the
`[iso:skip]` sentinel, never by an isolation field. The guard strips the
`[iso:skip]` token from the description before the spawn proceeds.
