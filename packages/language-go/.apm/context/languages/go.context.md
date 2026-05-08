# Go

Use `cmd/` for binaries and `internal/` for non-exported implementation code.

Keep packages small and explicit. Avoid framework imports in domain packages.

Use Go tooling, editor integrations exposed by the host, and `rg` for
definitions, references, diagnostics, and rename planning. Do not assume a Go
LSP MCP server is configured.

Use the project setup skill or [toolchain defaults](../toolchain-defaults/toolchain-defaults-index.context.md)
for `urfave/cli`, `koanf`, routing, RPC, and SQL tooling defaults.
