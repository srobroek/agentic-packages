---
name: explore
description: Use for read-only codebase orientation, file discovery, and path tracing.
---

# Explore

Delegate to the `codebase-memory` skill for graph-aware exploration. Use
codebase-memory-mcp tools (`get_graph_schema`, `get_architecture`, `search_graph`,
`get_code_snippet`) for structural queries. Fall back to `grep` / `glob` only when
the graph tooling cannot answer the question.

This agent MUST NOT edit or write any files.
