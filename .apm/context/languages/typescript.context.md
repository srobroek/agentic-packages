# TypeScript And JavaScript

Keep modules typed and explicit.

Use runtime validation at external boundaries, not deep inside pure domain code.
Keep generated clients and generated types in consumer packages or dedicated
generated packages, not in source-of-truth contract folders.

Use TypeScript tooling, editor integrations exposed by the host, and `rg` for
definitions, references, diagnostics, and rename planning. Do not assume a
TypeScript LSP MCP server is configured.

Use the project setup skill or [toolchain defaults](../toolchain-defaults/toolchain-defaults-index.context.md)
for package managers, frameworks, and test runners.
