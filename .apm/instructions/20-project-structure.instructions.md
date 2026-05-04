---
description: Project structure and ownership routing for capability-first repos.
applyTo: "**/*"
---

# Project Structure

Use capability-first paths so steering can compose by domain and language.
Prefer `apps/`, `services/`, `functions/`, `workers/`, `libs/`, `packages/`,
`schemas/`, `data/`, `infrastructure/`, `tools/`, `scripts/`, `docs/`, `specs/`,
`tests/`, `assets/`, and `archive/`.

Keep `libs/` organized by architectural role. `libs/domain` is pure domain
logic: no network, database, filesystem, framework, or cloud SDK imports.

Use owner-local folders for owned assets: service data under `services/*/data`,
service contracts under `services/*/contracts`, and prompts/evals under the
owning service or library. Use root `schemas/` only for shared/public contracts.

See [project shape details](../context/project-structure.context.md).
