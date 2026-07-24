---
description: GitNexus-first structural code discovery and the graph-reindex lifecycle.
---

# GitNexus first for structural code questions

When a repo is indexed by GitNexus (`.gitnexus/` exists; graph auto-refreshed
after commits by a PostToolUse hook), default to it over grep for anything
structural:

- FIRST tool for "where is X / how does X work": `query({search_query})` —
  execution-flow-grouped results. Use `rg` only for exact text/path lookups.
- Before modifying any function/class/method: `impact({target, direction:
  "upstream"})`; warn the user on HIGH/CRITICAL blast radius.
- Symbol relationships: `context({name})`; connect two points: `trace`.
- Before committing: `detect_changes()` (branch review: `{scope: "compare",
  base_ref: "main"}`).
- Rename via `rename` (call-graph aware), never find-and-replace.

Worktrees: the graph lives in the primary checkout; MCP answers from there
(near-main — fine for architecture). Stale index: `gitnexus analyze` (~100s).

For tool routing, index lifecycle, install gotchas, and the LadybugDB cache
repair note, read [gitnexus context](../context/gitnexus.gitnexus-index.context.md).
