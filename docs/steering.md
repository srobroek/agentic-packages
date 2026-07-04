# Steering packages

Opt-in opinionated steering (instructions + context). Install only the conventions you want -- bundles never pull steering automatically, so adopting a domain's *opinions* is always a separate, explicit choice from installing its *tools*.

Each steering package is a single always-on `applyTo: "**/*"` pointer instruction plus its own on-demand context depth. Install N steering packages and the compiled root `AGENTS.md`/`CLAUDE.md` gains N pointer lines -- the "steering index" is an emergent compiled artifact, not a hand-maintained hub.

Language steering (`language-steering-<lang>`) carries the opinionated default stack for a language (tooling + library picks); the matching `language-<lang>` bundle carries the non-opinionated structural conventions.

<!-- BEGIN:steering -->
| Steering Package | Description |
| --- | --- |
| `language-steering-go` | Opt-in opinionated Go defaults: prefer the standard library, urfave/cli for CLIs, koanf for layered config. Install to adopt these picks; the language-go package carries the non-opinionated structural conventions. |
| `language-steering-python` | Opt-in opinionated Python defaults: tooling (uv, Ruff, pytest, pyright) and libraries (FastAPI, Pydantic, Litestar). Install to adopt these picks; the language-python package carries the non-opinionated structural conventions. |
| `language-steering-rust` | Opt-in opinionated Rust defaults: cargo/clippy/rustfmt, thiserror for libraries, anyhow for binaries, clap for CLIs. Install to adopt these picks; the language-rust package carries the non-opinionated structural conventions. |
| `language-steering-terraform` | Opt-in opinionated Terraform and HCL defaults: module preference order, remote state with locking, version pinning, and plan/validate discipline. Install to adopt these picks; the language-terraform package carries the non-opinionated structural conventions. |
| `language-steering-typescript` | Opt-in opinionated TypeScript and JavaScript defaults: tooling (Bun, pnpm, Vitest) and contracts (Zod, OpenAPI). Install to adopt these picks; the language-typescript package carries the non-opinionated structural conventions. |
| `steering-architecture` | Cross-cutting design steering: compose over fork, keep generic cores case-agnostic, and make structural invariants a verifiable diff guard. Opt-in steering. |
| `steering-backend` | Opinionated backend conventions: service/function/worker runtime shape, API and cross-boundary contract rules, and background-job (queue, event, scheduled) patterns. Opt-in steering. |
| `steering-data` | Opinionated data conventions: data ownership, database assets, migrations, pipelines, and notebook practices. Opt-in steering. |
| `steering-delivery` | Opinionated delivery cadence: work like a developer who commits continuously. Commit and push after every meaningful, self-contained step; keep commits atomic; leave no unpushed local work stranded in a local or disposable worktree. Always-on steering. Opt-in. |
| `steering-docs-specs` | Opinionated documentation and spec conventions: durable docs structure, markdown practices, project-doc placement, and the SpecKit spec-workflow conventions. Opt-in steering. |
| `steering-frontend` | Opinionated frontend conventions: framework choice by surface (React/Vue/Next/Astro), UI library picks, app vs server state, and browser verification expectations. Opt-in steering -- install to adopt these frontend defaults. |
| `steering-infrastructure` | Opinionated infrastructure conventions: platform code, IaC, deployment config, CI/CD, environments, and observability. Opt-in steering. |
| `steering-pragmatic` | Opinionated pragmatic working style: prioritize accuracy, calibration, and decision usefulness over agreeableness. Analytical and direct by default; distinguish facts from assumptions; avoid hype and sycophancy. Always-on steering. Opt-in. |
| `steering-project-structure` | Opt-in steering: capability-first repository structure and ownership conventions -- repo layout, ownership boundaries, shared libraries, contracts, and where docs/specs/tools live. |
| `steering-speckit` | Opinionated SpecKit workflow steering: the mandatory-gated Phase 1/2/3 DAG, human-gating rules, and command reference. Opt-in -- install alongside the speckit package to adopt this specific spec-driven process. |
| `steering-subagent-routing` | Opt-in steering: model routing and verification policy for delegated subagents -- when to delegate, model/effort choice, parallel work, and who owns verification. |
| `steering-toolchain-defaults` | Opt-in steering: opinionated default stack choices for frontend, infrastructure, and quality/observability. Install to adopt these defaults when setting up or standardizing a project. |
| `steering-tools-scripts` | Opinionated conventions for repo tooling and automation: where scripts, generators, maintained CLIs, and task runners live and how they are structured. Opt-in steering. |
<!-- END:steering -->

---

See also: [bundles](bundles.md) · [skills](skills.md) · [agents](agents.md) · [hooks and MCP](hooks-and-mcp.md) · [external repos](external-repos.md) · [SpecKit](speckit.md)
