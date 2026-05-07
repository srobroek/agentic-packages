---
description: TypeScript LSP server usage via mcp-language-server
applyTo: "**/*.{ts,tsx,js,jsx,mts,cts}"
---

## lsp-typescript

Use `lsp-typescript` for compiler-accurate symbol navigation in TypeScript/JavaScript:

- **go-to-definition**: resolve imports, function calls, type references
- **find-references**: all usages of a symbol across the project
- **diagnostics**: type errors and lint issues from the TypeScript compiler
- **rename**: safe symbol rename with all references updated

Prefer lsp-typescript over Grep for symbol lookups — it understands type
narrowing, overloads, and re-exports that text search misses.

Fall back to Grep only for string literals or patterns that aren't symbol-based.
