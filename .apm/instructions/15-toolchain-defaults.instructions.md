---
description: Always-loaded compact toolchain defaults for project setup and broad workflow.
applyTo: "**/*"
---

# Toolchain Defaults

For new projects, packages, or scaffold changes, use the `project-setup` skill
and scripts instead of hand-rolling setup files.

Default choices:

- Python: uv, Ruff, pytest, pyright; FastAPI + Pydantic for APIs, Litestar when
  more structure is needed.
- TypeScript: Bun for small projects, pnpm for monorepos; Zod + OpenAPI;
  Vitest for tests.
- Frontend: React + Vite for SPA/product UIs, Vue + Vite for app-style UIs,
  Next.js for SSR/full-stack React, Astro for marketing/static/docs.
- Go: standard library first; `urfave/cli` for CLIs; `koanf` for config.
- Rust: cargo, clippy, rustfmt; `thiserror` for libraries, `anyhow` for
  binaries, `clap` for CLIs.
- Infrastructure: Terraform/OpenTofu first, CDK opt-in, Kubernetes/Helm opt-in.
- Orchestration: `just`, `mise`, and `moon` are independent setup choices.
- Quality: layered tests, structured logging, OpenTelemetry for services and
  workers, conditional security scanners.
