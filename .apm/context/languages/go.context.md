# Go

Use `cmd/` for binaries and `internal/` for non-exported implementation code.

Keep packages small and explicit. Avoid framework imports in domain packages.

When `lsp-go` is configured, use it for definitions, references, diagnostics,
and safe renames before text search.

Use the project setup skill or [toolchain defaults](../toolchain-defaults/toolchain-defaults-index.context.md)
for `urfave/cli`, `koanf`, routing, RPC, and SQL tooling defaults.
