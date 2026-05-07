---
description: Go LSP server usage via mcp-language-server
applyTo: "**/*.go"
---

## lsp-go

Use `lsp-go` for compiler-accurate symbol navigation in Go:

- **go-to-definition**: resolve package imports, function calls, interface implementations
- **find-references**: all usages of a symbol across modules
- **diagnostics**: type errors and vet findings from gopls
- **rename**: safe symbol rename with all references updated

Prefer lsp-go over Grep for symbol lookups — it understands interface
satisfaction, embedded structs, and vendored module resolution.

Fall back to Grep only for string literals or build tags.
