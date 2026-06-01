# TypeScript And JavaScript

Keep modules typed and explicit.

Use runtime validation at external boundaries, not deep inside pure domain code.
Keep generated clients and generated types in consumer packages or dedicated
generated packages, not in source-of-truth contract folders.

Use TypeScript tooling, editor integrations exposed by the host, and `rg` for
definitions, references, diagnostics, and rename planning. Do not assume a
TypeScript LSP MCP server is configured.

## Defaults

Keep existing project choices unless the task is explicitly about setup,
migration, or standardization.

- Use Bun for small standalone projects.
- Use pnpm for monorepos.
- Use Zod at runtime boundaries and OpenAPI for HTTP contracts.
- Use Vitest for tests unless the existing stack already standardizes on a
  different runner.
