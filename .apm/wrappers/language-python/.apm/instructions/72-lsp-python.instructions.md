---
description: Python LSP server usage via mcp-language-server
applyTo: "**/*.{py,pyi}"
---

## lsp-python

Use `lsp-python` for compiler-accurate symbol navigation in Python:

- **go-to-definition**: resolve imports, function calls, class references
- **find-references**: all usages of a symbol across the project
- **diagnostics**: type errors from pyright's static analysis
- **rename**: safe symbol rename with all references updated

Prefer lsp-python over Grep for symbol lookups — it understands dynamic
imports, __all__ exports, and type stub resolution that text search misses.

Fall back to Grep only for string patterns or runtime-constructed identifiers.
