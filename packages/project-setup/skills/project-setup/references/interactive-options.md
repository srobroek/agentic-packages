# Interactive Options

Ask for every configurable option that is not already provided. Use these
defaults only when the user accepts defaults or explicitly asks the agent to
choose.

Use `script-capabilities.md` as the authoritative list of supported setup
flags, targets, and overlay executors. Do not run setup scripts with `--help` or
inspect scripts to discover options while interviewing the user.

## Prompting Rules

- Ask explicit questions; do not ask the user to fill a freeform template unless
  they request one.
- Ask one compact group at a time and wait for the answer before asking the next
  group.
- For each group, include 2-5 likely options plus "custom" when useful.
- Surface the recommended option, but do not silently choose it.
- Before running scripts, show the exact command and `apm.yml` dependencies.
- Treat scripts as executors. Run them only after final confirmation.

## Question Flow

1. What are we setting up? Ask for project name, directory, description,
   owner/org, visibility, and license.
2. Is this a new repo, an existing repo retrofit, or a package added to a
   monorepo?
3. Should the layout be single-project or monorepo?
4. Which capabilities should exist? Ask for apps, services, functions, workers,
   libs, packages, schemas, data, infrastructure, tools, docs.
5. Which languages and frameworks apply to each selected target?
6. Which orchestration/tooling should be enabled: just, mise, moon, package
   managers, test commands, quality gates?
7. What workflow/process level does the user want: none, lightweight specs,
   full SpecKit, selected Matt Pocock workflow skills, or custom?
8. Which APM packages should be installed? Present bundle recommendations
   first, then let the user select additional skills, agents, and MCP entries
   that are not already included by selected bundles.
9. Should git/GitHub actions run: git init, remote creation, initial
   commit/push?
10. Which verification steps should run now?

## Project Identity

- `--name`: project name. Required.
- `--dir`: project directory. Default: current directory.
- `--org`: GitHub owner/org. Required when creating a remote.
- `--description`: one-line description.
- `--license`: `apache-2.0` default, `mit` optional.
- visibility: private default, public optional.
- git behavior: init git or skip.
- GitHub behavior: create remote or skip.

## Setup Mode

- new project
- add package to existing monorepo
- retrofit APM/project steering into an existing repo

## Layout

- `single`: universal root plus selected target.
- `monorepo`: capability-first directories.

Universal root:

```text
apm.yml, .apm/, .codex/, .github/, docs/, specs/, infrastructure/, tests/,
scripts/, assets/, archive/, README.md, justfile, .pre-commit-config.yaml
```

Capability targets:

- `apps/web`, `apps/admin`, `apps/mobile`, `apps/desktop`, `apps/marketing`,
  `apps/docs`
- `services/api`, `services/graphql`, `services/rpc`, `services/webhooks`,
  `services/auth`, `services/billing`, `services/notifications`
- `functions/aws-lambda`, `functions/cloudflare`
- `workers/aws-lambda`, `workers/cloudflare`
- `libs/domain`, `libs/application`, `libs/adapters`, `libs/config`,
  `libs/testing`, `libs/ui`, `libs/types`
- `packages/<name>`
- `schemas/openapi`, `schemas/graphql`, `schemas/asyncapi`,
  `schemas/jsonschema`, `schemas/protobuf`
- `data/shared`, `data/datasets`, `data/pipelines`, `data/notebooks`
- `infrastructure/terraform`, `infrastructure/cdk`,
  `infrastructure/kubernetes`, `infrastructure/helm`,
  `infrastructure/policies`, `infrastructure/pipelines`
- `tools/<name>`

## Orchestration

Composable choices:

- `just`
- `mise`
- `moon`

Default for new projects: ask. Recommend `just` and `mise`; add `moon` for
multi-package monorepos or when the user wants task graph orchestration.

## Spec Mode

- `none`: create `specs/` only.
- `lightweight`: specs plus lightweight/tinyspec workflow.
- `full`: full Specify/SpecKit install, workflows, extensions, and scoped steering.

Default: ask whether the project is lightweight or full SpecKit. Use `none`
only when explicitly selected.

## APM

- create/update `apm.yml`
- install APM package now
- compile Codex steering now
- patch/audit generated runtime agents now
- compile Claude only when explicitly requested
- project-local primitive escape hatch: default false
- selected bundles: installed through `apm install <bundle>@srobroek-agentic`
- selected agents: saved under `x-agentic.selected_agents`
- selected skills: saved under `x-agentic.selected_skills`
- selected MCP packages/servers: installed through APM packages and recorded
  under `x-agentic.selected_mcp` when the script supports it
- optional external skills: selected as `apm install <name>@srobroek-agentic` arguments;
  let APM resolve them instead of writing marketplace refs directly into
  `dependencies.apm`
  when possible

## TypeScript

- package manager: Bun for small projects, pnpm for monorepos.
- app framework: React + Vite, Vue + Vite, Next.js, Astro.
- backend framework: Hono, Fastify, NestJS.
- UI kit: shadcn/ui, Base UI, PrimeVue, Nuxt UI, none/custom.
- state: store-first app state, TanStack Query for server state.
- target path.

## Python

- Python version.
- API framework: FastAPI + Pydantic default, Litestar for more structure.
- package/tooling: uv, Ruff, pytest, pyright.
- target path and package name.

## Go

- module path.
- app kind: CLI, service, library, tool.
- CLI framework: `urfave/cli` for CLIs.
- config: `koanf` when config is needed.
- optional: chi, connect-go, sqlc.
- target path.

## Rust

- workspace or single crate.
- crate kind: CLI, library, service, desktop.
- CLI: `clap`.
- errors: `thiserror` for libraries, `anyhow` for binaries.
- service: `axum` and `tokio` only when async HTTP/service domain is selected.
- desktop: Tauri first.
- target path.

## Infrastructure

- Terraform/OpenTofu default.
- CDK opt-in.
- Kubernetes/Helm opt-in.
- policies/pipelines/scripts as needed.
- cloud/provider and environment names.

## Quality And Security

- pre-commit. Default: yes.
- agent quality hooks by selected language. Default: yes for selected language
  overlays; ask before disabling. These are project-local APM runtime hooks:
  advisory after significant selected-language edits, blocking only before an
  agent runs `git commit`.
- gitleaks/secret scanning. Default: yes.
- dependency updates: Renovate or Dependabot.
- conditional scanners for matching files: IaC, containers, SAST.
- test command defaults by selected language.
