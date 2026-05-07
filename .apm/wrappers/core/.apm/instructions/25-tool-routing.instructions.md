---
description: Tool routing preferences for code discovery, GitHub operations, and MCP usage
applyTo: "**/*"
---

## Code Discovery Priority

1. **codebase-memory-mcp** — preferred for orientation. Use `search_graph`,
   `trace_call_path`, `get_code_snippet` for cross-file navigation, symbol lookup,
   and dependency tracing. Prefer over Grep when understanding relationships.

2. **Grep / Read** — for known patterns. Use when you know the exact string, regex,
   or file path. Faster for simple lookups.

3. **repomix** `pack_codebase` — for bulk snapshot analysis of a directory. Not for
   incremental lookups. Use `grep_repomix_output` to search within packed output.

## GitHub Operations — `gh` CLI

All GitHub operations use `gh` via terminal. Patterns:

- PRs: `gh pr create|view|list|diff|merge|review|checks`
- Issues: `gh issue create|view|list|comment`
- Search: `gh search code "pattern" --repo owner/repo`
- Raw API: `gh api repos/{owner}/{repo}/...`

Use `--json field1,field2` for structured output when parsing is needed.

## Library Documentation — Context7

Use context7 (`resolve-library-id` then `query-docs`) for ANY library or framework
question, even well-known ones. Training data may be stale.

## Package Versions — mcp-package-version

Use `mcp-package-version` to check latest stable versions before adding dependencies.
Prevents hallucinating outdated version numbers.
