# Rust

Keep crates domain-driven.

Keep pure library crates free of runtime and framework dependencies unless the
crate's purpose is explicitly integration or platform glue.

Use cargo, rust-analyzer integrations exposed by the host editor, and `rg` for
definitions, references, diagnostics, and rename planning. Do not assume a Rust
LSP MCP server is configured.
