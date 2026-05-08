# External Agent Marketplaces

Use external agent marketplaces through APM, not by vendoring their broad agent
catalogs into this repository.

## Codex Compatibility

- `wshobson/agents` is APM-consumable and installs Claude plugin agents into
  `.codex/agents/*.toml` when installed with `--target codex`.
- `VoltAgent/awesome-claude-code-subagents` is APM-consumable and installs its
  category agents into `.codex/agents/*.toml` when installed with
  `--target codex`.
- Claude commands from external plugins are not generally converted into Codex
  commands. Treat commands as Claude-only unless APM later adds Codex command
  support.
- Project setup should browse registered marketplaces with APM and recommend
  packages. It should not crawl raw upstream repositories during normal setup.

## Marketplace Shape

`wshobson-agents` currently exposes 81 granular plugins and 185 agent entries
across 120 unique agent names. Prefer it as the default external agent source
because packages are narrower and often include paired skills.

Important plugin groups:

- languages: `python-development`, `javascript-typescript`,
  `systems-programming`, `jvm-languages`, `web-scripting`,
  `functional-programming`, `julia-development`,
  `arm-cortex-microcontrollers`, `shell-scripting`, `dotnet-contribution`
- development: `backend-development`, `frontend-mobile-development`,
  `multi-platform-apps`, `developer-essentials`, `ui-design`,
  `debugging-toolkit`
- quality: `comprehensive-review`, `performance-testing-review`, `plugin-eval`
- workflows: `git-pr-workflows`, `full-stack-orchestration`, `tdd-workflows`,
  `conductor`, `agent-teams`
- security: `security-scanning`, `security-compliance`,
  `backend-api-security`, `frontend-mobile-security`, `reverse-engineering`,
  `block-no-verify`
- infrastructure: `deployment-strategies`, `deployment-validation`,
  `kubernetes-operations`, `cloud-infrastructure`, `cicd-automation`
- utilities: `code-refactoring`, `dependency-management`, `error-debugging`,
  `team-collaboration`

`voltagent-subagents` currently exposes 10 broad category plugins and 144
unique agent names. Use it when the project needs broad category coverage or a
specialist not covered well by wshobson.

VoltAgent category packages:

- `voltagent-core-dev`
- `voltagent-lang`
- `voltagent-infra`
- `voltagent-qa-sec`
- `voltagent-data-ai`
- `voltagent-dev-exp`
- `voltagent-domains`
- `voltagent-biz`
- `voltagent-meta`
- `voltagent-research`

## Routing Policy

Prefer wshobson when both sources provide the same role, unless VoltAgent's
agent prompt is materially better for the current project.

Use `.apm/runtime-agent-overrides.yml` for runtime model/effort patches only.
The main session should pass task-specific tool instructions when invoking an
agent. Examples:

- coding agents: use Context7 for current library docs and codebase-memory-mcp
  for graph-aware orientation before editing
- large changes: use repomix when a compact source bundle is useful
- frontend/UI agents: use Playwright for browser verification and Stitch when
  design generation or design reference work is relevant
- review agents: verify findings from source and tests before reporting

Do not route all external coding agents through a generic first-party `coder`
agent. Prefer installed language/framework specialists first; keep a generic
coder only as a fallback when no specialist is installed.
