# Language Overlays

## TypeScript

- Script: `scripts/setup-ts.sh`
- Ask: target path, package manager, domain, framework, UI kit, state/data
  approach, test runner, generated-client needs.
- Defaults: Bun for small projects, pnpm for monorepos; React + Vite for
  SPA/product UIs, Vue + Vite for app-style UIs, Next.js for SSR/full-stack
  React, Astro for marketing/static/docs.

## Rust

- Script: `scripts/setup-rust.sh`
- Ask: target path, single crate vs workspace, crate kind, async/service needs,
  desktop needs.
- Defaults: cargo, clippy, rustfmt; `thiserror` for libraries, `anyhow` for
  binaries, `clap` for CLIs, Tauri first for desktop.

## Python

- Script: `scripts/setup-python.sh`
- Ask: target path, package name, Python version, API framework, service vs
  library shape.
- Defaults: uv, Ruff, pytest, pyright; FastAPI + Pydantic for APIs, Litestar
  when more structure is needed.

## Go

- Script: `scripts/setup-go.sh`
- Ask: target path, module path, app kind, CLI/config/routing/RPC/SQL needs.
- Defaults: standard library first; `urfave/cli` for CLIs; `koanf` for config.
