# Go

Use `cmd/` for binaries and `internal/` for non-exported implementation code.

Keep packages small and explicit. Avoid framework imports in domain packages.

Use Go tooling, editor integrations exposed by the host, and `rg` for
definitions, references, diagnostics, and rename planning. Do not assume a Go
LSP MCP server is configured.

## Defaults

Keep existing project choices unless the task is explicitly about setup,
migration, or standardization.

- Use the standard library first.
- Use `urfave/cli` for CLIs when basic flag parsing is not enough.
- Use `koanf` for layered configuration.
