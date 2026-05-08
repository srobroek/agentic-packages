---
name: codebase-memory
description: Use for graph-aware codebase exploration, tracing, and reference lookup.
---

# Codebase Memory

Use this skill when graph-aware codebase tooling is more effective than manual file search.

## Preferred Flow

1. Choose the intent first: explore, trace, reference, or quality.
2. Start with the lightest graph-aware query that can answer the question.
3. Read only the specific code snippets or graph results needed to confirm the answer.
4. Fall back to plain file search only when the graph tooling cannot answer the question.

## Intent Routing

- Explore architecture or locate symbols: use `get_graph_schema` → `get_architecture` → `search_graph` → `get_code_snippet`
- Trace callers, callees, or impact: `references/trace.md`
- Check tool capabilities or query patterns: `references/reference.md`
- Look for dead code, hotspots, or refactor targets: `references/quality.md`

## Steering

- Prefer graph-aware lookup before broad grep when the tool can answer the question.
- Use the code graph to narrow the search surface, then verify against real code.
- Keep the answer grounded in observed results, not assumed graph completeness.

## Scripts

- Index refresh helper: `scripts/index.sh`
