# Project Structure Reference

Use capability-first paths and layer language steering with file globs.

Top-level directories:

- `apps/` for user-facing surfaces: `web`, `admin`, `mobile`, `desktop`,
  `marketing`, `docs`.
- `services/` for long-lived backend deployables: `api`, `graphql`, `rpc`,
  `webhooks`, `auth`, `billing`, `notifications`.
- `functions/` for serverless handlers, nested by platform such as
  `aws-lambda` or `cloudflare`.
- `workers/` for background jobs, queues, schedulers, and consumers, nested by
  platform.
- `libs/` for internal shared code by architectural role: `domain`,
  `application`, `adapters`, `config`, `testing`, `ui`, `types`.
- `packages/` only for externally published or independently versioned
  packages.
- `schemas/` for shared/public contracts. Generated clients live with consumers
  or in packages.
- `data/` for shared data assets where no single owner exists. Owner-specific
  data stays under the owner.
- `infrastructure/` for shared platform/IaC: `terraform`, `cdk`, `kubernetes`,
  `helm`, `policies`, `pipelines`, `scripts`, and shared `environments`.
- `tools/` for maintained CLIs, generators, MCP implementations, and repo tools.
- `scripts/` for thin automation.
- `docs/`, `specs/`, `tests/`, `assets/`, and `archive/` for cross-cutting
  project material.

Purity rule: `libs/domain` contains domain logic only and must not import
network, database, filesystem, framework, or cloud SDK dependencies.

AI/product agents are owned by services or libraries; do not create a root
`agents/` directory for product code.
