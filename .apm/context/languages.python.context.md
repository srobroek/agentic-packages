# Python

Use `src/<package>/` layouts with `api`, `domain`, `application`, `adapters`,
and `settings.py` for services.

Keep domain code independent from framework and IO concerns.

Use Python tooling, editor integrations exposed by the host, and `rg` for
definitions, references, diagnostics, and rename planning. Do not assume a
Python LSP MCP server is configured.

## Defaults

Keep existing project choices unless the task is explicitly about setup,
migration, or standardization.

- Use uv for project and tool environments.
- Use Ruff, pytest, and pyright unless the project already has a coherent
  alternative.
- Prefer FastAPI with Pydantic for APIs. Use Litestar when the project needs
  stronger application structure.
