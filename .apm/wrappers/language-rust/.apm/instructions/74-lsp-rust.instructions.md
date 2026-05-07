---
description: Rust LSP server usage via mcp-language-server
applyTo: "**/*.rs"
---

## lsp-rust

Use `lsp-rust` for compiler-accurate symbol navigation in Rust:

- **go-to-definition**: resolve use statements, trait impls, macro expansions
- **find-references**: all usages of a symbol across crates
- **diagnostics**: type errors and borrow checker findings from rust-analyzer
- **rename**: safe symbol rename with all references updated

Prefer lsp-rust over Grep for symbol lookups — it understands trait resolution,
macro hygiene, and feature-gated code that text search misses.

Fall back to Grep only for string literals or cfg attributes.
