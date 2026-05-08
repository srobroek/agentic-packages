# srobroek/agentic-packages

APM package repository for shared agentic tooling:

- instructions and context for progressive steering
- Claude and Codex agent definitions
- Claude and Codex hook manifests
- finalizers that patch generated runtime agents after APM install

## Bundle usage

The `core` bundle is the deterministic shared project baseline. It installs the
core agents, code-intelligence skills, project lifecycle skills, agentic
maintenance skills, first-party `write-a-skill`, and Matt Pocock's
`diagnose`, `grill-me`, and `grill-with-docs` workflows. It also installs
Hobson `context-management` and `agent-orchestration` for baseline context and
coordination support.

Personal workflow tools such as Salesforce or activity tracking remain outside
`core` and are available only through the explicit `work-tools` bundle.

Additional bundles:

- `developer-tools`: Hobson developer essentials, debugging, review, PR, and
  documentation generation workflows
- `code-intelligence`: graph/index/search/research skills plus `pr-reviewer`,
  Hobson documentation generation, and C4 architecture support
- `project-lifecycle`: catchup, handover, commit, PR, merge, and verify flow
- `quality`: cross-language review, verification, testing, TDD, and review
  workflows
- `speckit`: SpecKit skill and agents
- `agentic-maintenance`: steering audit, steering optimization, prompt lookup,
  first-party skill writing, documentation standards, and plugin evaluation
- `debugging`: diagnose, unstuck, adversarial challenger, error diagnosis, and
  incident debugging workflows
- `frontend`: Impeccable, Interface Design, Stitch skills, Playwright browser
  automation MCP, and Hobson frontend/UI/accessibility agents
- `docs-architecture`: Hobson HADS, code docs, documentation generation, and C4
  workflows
- `infrastructure`: Hobson cloud, Kubernetes, CI/CD, deployment, Terraform, and
  observability workflows
- `security`: Hobson security scanning, compliance, API/frontend security, and
  reverse-engineering workflows
- `data-ai`: Hobson LLM application, data engineering, MLOps, and database
  workflows
- `governance`: Hobson MCP protection, signed audit trails, review policy, and
  git hook bypass protection workflows
- `planning-product`: first-party debate/research plus Matt PRD, issue, TDD,
  triage, zoom-out, and architecture workflows
- `language-typescript`, `language-python`, `language-go`, `language-rust`,
  `language-terraform`, `language-shell`, `language-dotnet`, `language-jvm`,
  `language-web-scripting`, `language-functional`, `language-julia`, and
  `language-arm-cortex`: language-specific bundles

`sniff` still exists as an individual first-party skill, but it is not part of
`core` or `debugging`.

From this package directory:

```bash
apm run build-packages
apm run build-marketplace
apm compile --validate --local-only --target codex
```

Use `uv tool run --from apm-cli apm ...` for local validation when `apm` is not
installed on the machine yet.

## Project usage

Register the marketplace, browse available packages, then add selected package
entries to the project `apm.yml`. Project setup should call the finalizers from
`apm_modules/_local/agentic-packages` or the installed Git dependency path. See
`templates/project-apm.yml`.

For marketplace installation:

```bash
apm marketplace add srobroek/agentic-packages --name srobroek-agentic
apm marketplace browse srobroek-agentic
apm install core@srobroek-agentic
```

For direct GitHub installation:

```yaml
dependencies:
  apm:
    - srobroek/agentic-packages
```

The important order is:

```bash
apm install --target claude,codex,agent-skills
apm compile --target codex --no-constitution
apm run write-claude-pointers
apm run patch-agentic-tools
apm run audit-agentic-tools
```

Do not compile Claude by default. Compiled `CLAUDE.md` files duplicate full
instruction bodies. The setup flow writes minimal `CLAUDE.md` pointer files
beside generated `AGENTS.md` files instead, so Claude users can follow the same
progressive-disclosure index through Claude Code's eager `@AGENTS.md` import.

`patch-agentic-tools` is required because APM's conversion does not preserve
all Codex and Claude runtime-specific model, effort, sandbox, and permission
fields for first-party agents. External marketplace agents can be audited and
patched only through explicit project policy.

Shared agentic assets are authored under `.apm/`. Installable curated APM
packages are materialized under `packages/` by `apm run build-packages`; do not
edit generated runtime directories or dotfiles. After changing agents, skills,
hooks, instructions, contexts, MCP definitions, or setup scripts, regenerate the
packages and marketplace, then reinstall the package in consuming projects.
