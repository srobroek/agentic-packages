# Script Capabilities

This file is the project setup skill's static execution contract. Use it during
the interview and confirmation phases instead of running scripts to discover
flags.

## Main Executor

`scripts/project-setup.sh` creates the universal project scaffold, writes APM
metadata, registers the `srobroek-agentic` marketplace by default,
installs/compiles APM by default, and chains language overlays.

Codex execution note: the main executor writes `.git`, `.codex`, and `.agents`.
Those paths are protected as read-only inside Codex `workspace-write`, so run
the executor with sandbox escalation when using Codex shell tools.

Required input:

- `--name <name>`
- `--org <owner>` unless `--no-repo` is selected

Project identity and repository:

- `--dir <path>`
- `--description <text>`
- `--license apache-2.0|mit`
- `--public`
- `--no-repo`
- `--no-git`

Shape:

- `--layout single|monorepo`
- `--monorepo`
- `--target <path>` repeatable

Process and SpecKit:

- `--spec-mode none|lightweight|full`
- `--speckit`
- `--speckit-integration codex|claude`
- `--speckit-script sh|ps`

Tooling:

- `--just`
- `--mise`
- `--moon`

APM:

- `--apm-install`
- `--no-apm-install`
- `--apm-compile`
- `--no-apm-compile`
- `--compile-claude`
- `--marketplace-repo <owner/repo>`
- `--marketplace-name <name>`
- `--skip-marketplace-register`
- `--agentic-packages <package@marketplace>`
- `--apm-dependency <package@marketplace>` repeatable
- `--selected-bundle <name>` repeatable
- `--selected-agent <name>` repeatable
- `--selected-skill <name>` repeatable
- `--selected-mcp <name>` repeatable

`scripts/apm-discover.sh` resolves APM, registers/updates the default
marketplace when needed, and prints the browse output that package
recommendations must use. Supported flags:

- `--marketplace-repo <owner/repo>`
- `--marketplace-name <name>`
- `--profile <name>` repeatable
- `--select-package <package@marketplace>` repeatable; accepts any package from
  the remote marketplace browse output and adds missing packages to the
  preference index
- `--selection-note <text>`
- `--preferences-file <path>`
- `--no-update-preferences`
- `--first-party-only`
- `--include-upstream-agents` backward-compatible no-op; upstream marketplaces
  are included by default
- `--include-wshobson-agents` backward-compatible explicit include
- `--include-voltagent-subagents` backward-compatible explicit include
- `--extra-marketplace <name=owner/repo>` repeatable
- `--skip-marketplace-register`

Language overlays:

- `--lang ts|rust|python|go`
- `--lang-args "<overlay args>"`

## Language Executors

Run overlays only after the main project choices are confirmed.

| Script | Domain | Required Choices |
|--------|--------|------------------|
| `scripts/setup-ts.sh` | TypeScript frontend/backend/package targets | target path, package manager, framework/domain, UI kit when applicable |
| `scripts/setup-python.sh` | Python API/library/service targets | target path, package name, Python version, framework/domain |
| `scripts/setup-go.sh` | Go CLI/service/library targets | target path, module path, app kind, companion libraries |
| `scripts/setup-rust.sh` | Rust CLI/library/service/desktop targets | target path, crate/workspace shape, crate kind |

## Capability Targets

Use `--target` for every selected capability path. Common targets:

- apps: `apps/web`, `apps/admin`, `apps/mobile`, `apps/desktop`,
  `apps/marketing`, `apps/docs`
- services: `services/api`, `services/graphql`, `services/rpc`,
  `services/webhooks`, `services/auth`, `services/billing`,
  `services/notifications`
- functions: `functions/aws-lambda`, `functions/cloudflare`
- workers: `workers/aws-lambda`, `workers/cloudflare`
- libs: `libs/domain`, `libs/application`, `libs/adapters`, `libs/config`,
  `libs/testing`, `libs/ui`, `libs/types`
- contracts: `schemas/openapi`, `schemas/graphql`, `schemas/asyncapi`,
  `schemas/jsonschema`, `schemas/protobuf`
- data: `data/shared`, `data/datasets`, `data/pipelines`, `data/notebooks`
- infrastructure: `infrastructure/terraform`, `infrastructure/cdk`,
  `infrastructure/kubernetes`, `infrastructure/helm`,
  `infrastructure/policies`, `infrastructure/pipelines`
- tooling: `tools/<name>`, `packages/<name>`

## Confirmation Output

Before execution, show:

- the exact `scripts/project-setup.sh ...` command
- any overlay commands that will run afterward
- the package install list, using `apm install <name>@srobroek-agentic`
- selected bundles and what each bundle includes
- selected agents and skills recorded in `x-agentic`
- selected MCP entries and whether they come from a bundle or direct package
- verification commands and skipped checks

## Discovery Prohibitions

These are not setup discovery mechanisms:

- `fd marketplace.json ...`
- `jq ... <local-skills-checkout>/marketplace.json`
- `jq ... <local-agentic-packages-checkout>/marketplace.json`
- scanning `<local-skills-checkout>/agents`
- scanning `<local-agentic-packages-checkout>/agents`
- scanning `~/.config/agentic-tools/agents`
- scanning local skill directories to infer the package catalogue

Use APM marketplace commands instead. Local file scans are allowed only when
debugging the APM package repository itself, not when setting up a project.

Do not use `apm search` during project setup discovery. Use
`apm marketplace browse srobroek-agentic` and any other selected marketplace
names, then classify the returned packages.
