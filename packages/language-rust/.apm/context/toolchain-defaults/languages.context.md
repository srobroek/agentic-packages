# Language Defaults

Python defaults:

- Use uv for project and tool environments.
- Use Ruff, pytest, and pyright unless the project already has a coherent
  alternative.
- Prefer FastAPI with Pydantic for APIs. Use Litestar when the project needs
  stronger application structure.

TypeScript defaults:

- Use Bun for small standalone projects.
- Use pnpm for monorepos.
- Use Zod at runtime boundaries and OpenAPI for HTTP contracts.
- Use Vitest for tests unless the existing stack already standardizes on a
  different runner.

Go defaults:

- Use the standard library first.
- Use `urfave/cli` for CLIs when basic flag parsing is not enough.
- Use `koanf` for layered configuration.

Rust defaults:

- Use cargo, clippy, and rustfmt.
- Use `thiserror` for libraries and `anyhow` for binaries.
- Use `clap` for CLIs.
