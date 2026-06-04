# Skill Recommendations

Use this reference during project setup after collecting project goals and before running APM install commands. The APM marketplace browse result is the authoritative
catalogue; this file documents how to present it, not a static recommendation
source.

## Marketplace Discovery

Use APM as the only catalogue interface. Resolve the command in this order:

```bash
apm --version
mise exec -- apm --version
uv tool run --from apm-cli apm --version
```

Then run the same command form for every APM action. If none of those command
forms works, stop and report that APM is not available. Do not search local
checkouts for `marketplace.json`, do not read local skills repositories
directly, and do not scan `~/.config/agentic-tools` to build recommendations.

Register the marketplace when needed:

```bash
apm marketplace add srobroek/agentic-packages --name srobroek-agentic
```

Register optional upstream agent marketplaces only when the user chooses to
browse them:

```bash
apm marketplace add wshobson/agents --name wshobson-agents
apm marketplace add VoltAgent/awesome-claude-code-subagents --name voltagent-subagents
```

Then discover and install available packages with:

```bash
apm marketplace list
apm marketplace browse srobroek-agentic
apm install core@srobroek-agentic
```

Project setup should recommend only from packages returned by
`apm marketplace browse <marketplace-name>`, scoped
`apm search "<query>@<marketplace>"`, and the user's selected stack/process.
The default first-party marketplace is `srobroek-agentic`; optional upstream
marketplaces include `wshobson-agents` and `voltagent-subagents`. Do not use
unscoped `apm search`. If a marketplace is not available yet, fix or report
marketplace registration. Do not use a local package path fallback during
interactive recommendations.

## Recommendation Format

Present marketplace output in this order:

1. `Bundles`: package groups that install a coherent set of steering, skills,
   agents, hooks, and the standalone mandatory baseline MCP packages.
2. `Skills`: additional skills not already included by selected bundles.
3. `Agents`: additional agents not already included by selected bundles.
4. `MCP`: optional MCP-only packages or project-local MCP servers not already
   provided by the mandatory baseline.
5. `Skipped`: relevant but not recommended, with a short reason.
6. `Available Packages`: the complete package list from the marketplace, grouped
   compactly by namespace.

Each section should split entries into `recommended`, `optional`, and `available`.
For every selection, show the exact install metadata:

- bundles/packages: `--apm-dependency <name>@<marketplace>`
- local agents: `--selected-agent <name>`
- local skills: `--selected-skill <name>`
- MCP packages: `--apm-dependency <name>@<marketplace>`

For every package recommendation, include the exact `apm install` package
argument. Current APM accepts `name@marketplace` on the install command line,
but rejects that syntax if it is written directly into `dependencies.apm`.

For the full list, use the actual `apm marketplace browse srobroek-agentic`
result and render package names compactly. Expected groups for the default
marketplace:

- `Core`: `core`
- `External bundles`: `hyperresearch`, `impeccable`, `interface-design`,
  `stitch-skills`
- `MCP packages`: optional first-party `mcp-*` packages such as
  `mcp-playwright`
- `First-party skills`: every package backed by `srobroek/agentic-packages/.apm/skills/*`
- `Matt Pocock`: every `matt-*` package

Expected optional upstream marketplace groups:

- `wshobson-agents`: plugin packages with agents, commands, and many
  progressive-disclosure skills
- `voltagent-subagents`: broad agent-category packages without skills

When `wshobson-agents` and `voltagent-subagents` overlap on the same agent
name, recommend wshobson first by default. It has the stronger package shape for
project setup: more granular plugins, paired skills, commands in some packages,
newer repository activity in the checked snapshot, and more current toolchain
language in many overlapping prompts. Recommend VoltAgent first only when:

- the agent exists only in VoltAgent
- the user wants a broad category pack rather than a narrower workflow package
- the VoltAgent prompt is materially better for the specific project domain
- the project explicitly chooses VoltAgent as the upstream source

## Curated Upstream Profiles

Use these profiles to rank recommendations after browsing the marketplaces.
They are not a copied catalogue. If a listed package is not returned by
`apm marketplace browse <marketplace>`, omit it and report the mismatch.

Prefer wshobson packages for overlapping agent names. Prefer VoltAgent packages
for broad specialist coverage that wshobson does not cover cleanly.

### Core Coding

Recommended:

- `developer-essentials@wshobson-agents`
- `debugging-toolkit@wshobson-agents`
- `code-refactoring@wshobson-agents`
- `dependency-management@wshobson-agents`

Optional broad agents:

- `voltagent-core-dev@voltagent-subagents`
- `voltagent-dev-exp@voltagent-subagents`

### Backend And APIs

Recommended:

- `backend-development@wshobson-agents`
- `api-scaffolding@wshobson-agents`
- `api-testing-observability@wshobson-agents`

Optional broad agents:

- `voltagent-core-dev@voltagent-subagents`

### Frontend And Product UI

Recommended:

- `frontend-mobile-development@wshobson-agents`
- `ui-design@wshobson-agents`
- `accessibility-compliance@wshobson-agents`
- `application-performance@wshobson-agents`

Pair with first-party/third-party design packages when relevant:

- `impeccable@srobroek-agentic`
- `interface-design@srobroek-agentic`
- `stitch-skills@srobroek-agentic`

### Language Specialists

Recommended by selected language:

- Python: `python-development@wshobson-agents`
- JavaScript/TypeScript: `javascript-typescript@wshobson-agents`
- Systems: `systems-programming@wshobson-agents`
- JVM/.NET: `jvm-languages@wshobson-agents`,
  `dotnet-contribution@wshobson-agents`
- Shell: `shell-scripting@wshobson-agents`

Optional broad specialist pack:

- `voltagent-lang@voltagent-subagents`

### Quality And Security

Recommended:

- `comprehensive-review@wshobson-agents`
- `unit-testing@wshobson-agents`
- `tdd-workflows@wshobson-agents`
- `security-scanning@wshobson-agents`
- `security-compliance@wshobson-agents`
- `backend-api-security@wshobson-agents`
- `frontend-mobile-security@wshobson-agents`

Optional broad agents:

- `voltagent-qa-sec@voltagent-subagents`

### Infrastructure And Operations

Recommended:

- `cloud-infrastructure@wshobson-agents`
- `kubernetes-operations@wshobson-agents`
- `cicd-automation@wshobson-agents`
- `deployment-strategies@wshobson-agents`
- `deployment-validation@wshobson-agents`
- `incident-response@wshobson-agents`
- `observability-monitoring@wshobson-agents`

Optional broad agents:

- `voltagent-infra@voltagent-subagents`

### Data And AI

Recommended:

- `data-engineering@wshobson-agents`
- `data-validation-suite@wshobson-agents`
- `machine-learning-ops@wshobson-agents`
- `llm-application-dev@wshobson-agents`
- `agent-orchestration@wshobson-agents`

Optional broad agents:

- `voltagent-data-ai@voltagent-subagents`

### Documentation And Architecture

Recommended:

- `code-documentation@wshobson-agents`
- `documentation-generation@wshobson-agents`
- `documentation-standards@wshobson-agents`
- `c4-architecture@wshobson-agents`

### Research, Business, And Product

Recommended when relevant:

- `business-analytics@wshobson-agents`
- `startup-business-analyst@wshobson-agents`
- `voltagent-research@voltagent-subagents`
- `voltagent-biz@voltagent-subagents`

### Governance And Agent Systems

Recommended only when the project explicitly needs governance or agent
orchestration:

- `agent-teams@wshobson-agents`
- `plugin-eval@wshobson-agents`
- `protect-mcp@wshobson-agents`
- `signed-audit-trails@wshobson-agents`
- `review-agent-governance@wshobson-agents`
- `voltagent-meta@voltagent-subagents`

Do not require the user to pick from the recommendation set only. The full list
is part of the selection prompt.

Current packaging note: `core@srobroek-agentic` installs first-party shared agents, skills, hooks, instructions, contexts, and scripts. The mandatory MCP baseline is separate and must be installed via `mcp-codebase-memory@srobroek-agentic`, `mcp-context7@srobroek-agentic`, `mcp-package-version@srobroek-agentic`, and `mcp-repomix@srobroek-agentic`. Serena is the preferred optional package for semantic code tools when a project needs agent-accessible symbol navigation.

Broad upstream agent catalogs should come from `wshobson-agents` or
`voltagent-subagents`, not from vendored files in `srobroek-agentic`. Agent
selection is still saved in `apm.yml` under `x-agentic.selected_agents` so
routing can prefer the selected project agent set. External skills such as Matt
Pocock skills are exposed as individual marketplace entries and should be
selected as `matt-*` packages unless the user wants the full upstream set.
Optional MCPs that are not mandatory baseline, such as browser automation, are
exposed as explicit `mcp-*` packages.

## Bundle Deduping

Ask for bundles first. For each bundle, show what it includes:

- skills
- agents
- standalone mandatory baseline MCP packages, or optional explicit `mcp-*` packages
- hooks
- steering/rules

After the user selects bundles, expand those bundles into a coverage set and
remove the covered entries from the individual `Skills`, `Agents`, and `MCP`
selection lists. Do not ask the user to select the same capability twice.

When an individual entry overlaps with a selected bundle but provides a
different upstream source or newer/latest-tracking dependency, show it under
`Skipped` or `Optional Replacement`, not under normal selection.

The final plan should have three blocks:

1. `Selected bundles`
2. `Additional selections`
3. `Covered by bundles`

## Base Package

Always recommend the local shared package for managed projects:

```bash
apm install core@srobroek-agentic
```

The mandatory MCP baseline is not hidden inside `core@srobroek-agentic`.
Install `mcp-codebase-memory@srobroek-agentic`,
`mcp-context7@srobroek-agentic`, `mcp-package-version@srobroek-agentic`, and
`mcp-repomix@srobroek-agentic` as explicit packages for normal managed
projects. Treat a missing baseline MCP after setup as a repair issue, not as a
reason to add duplicate manual MCP declarations.

For semantic code tools, prefer Serena as the optional MCP package:
`mcp-serena@srobroek-agentic`. During setup, read
`references/serena.md` and `../../indexes/serena-language-servers.json`, run
the listed `mise use ...` commands in the project root for detected
runtime-supported Serena languages, then initialize the project with
`serena project create` so `.serena/project.yml` captures project languages,
ignore paths, workspace folders, mode defaults, and write permissions. Do not
generate `added_modes` or `--add-mode` for Serena 1.2.0; use project
`base_modes`/`default_modes` and repeatable CLI `--mode` only. For large
repositories, follow with `serena project index`.

Do not use local skills or `srobroek/agentic-packages` checkouts as a setup
fallback. Development of the package repository itself is separate from project
setup.

## Agent Selection

Agent recommendations should be derived from marketplace/package metadata and
the selected project shape, not from local filesystem scans. Present selected
agents as an active routing subset saved under `x-agentic.selected_agents`.

Avoid selecting every related agent. Prefer 5-12 active agents for a normal
project and add specialists later when the project needs them.

## Post-Install Agent Patching

Run package patch/audit scripts after installing agents:

```bash
apm run patch-agentic-tools
apm run audit-agentic-tools
```

Post-patching should enforce first-party `x-agentic` metadata and report
external agents that lack Codex model/effort/sandbox metadata. Do not silently
rewrite all external agents. External-agent patching must be driven by an
explicit policy keyed by marketplace/plugin/agent when a project chooses local
routing overrides.

## Matt Pocock Workflow Set

Recommend when the user wants a lightweight PRD -> issues -> TDD workflow,
stronger issue slicing, or architecture-focused engineering skills without the
full SpecKit workflow.

Prefer individual marketplace entries. Verified examples:

```bash
apm install matt-to-prd@srobroek-agentic matt-to-issues@srobroek-agentic matt-tdd@srobroek-agentic
```

Use these individual package names:

| Need | Dependency |
|------|------------|
| PRD synthesis | `matt-to-prd@srobroek-agentic` |
| Issue slicing | `matt-to-issues@srobroek-agentic` |
| TDD loop | `matt-tdd@srobroek-agentic` |
| Bug diagnosis | `matt-diagnose@srobroek-agentic` |
| Issue triage | `matt-triage@srobroek-agentic` |
| Architecture deepening | `matt-improve-codebase-architecture@srobroek-agentic` |
| Domain grilling | `matt-grill-with-docs@srobroek-agentic` |
| Project setup for these skills | `matt-setup-skills@srobroek-agentic` |
| Broader orientation | `matt-zoom-out@srobroek-agentic` |
| Compact response mode | `matt-caveman@srobroek-agentic` |
| Planning grill without docs | `matt-grill-me@srobroek-agentic` |
| Skill authoring | `matt-write-a-skill@srobroek-agentic` |

The marketplace exposes these as `matt-*` entries. Full-package dependency is
valid, but only recommend it when the user wants the whole upstream workflow
set:

```bash
apm install matt-skills@srobroek-agentic
```

Matt Pocock skills are the leading source for overlapping workflow skills such
as `diagnose`, `grill-me`, `grill-with-docs`, `triage`, `write-a-skill`, and
`zoom-out`. Do not recommend local replacements for those names unless a future
project intentionally maintains a fork.

## SpecKit Projects

Recommend the shared package only. It already includes SpecKit steering, agents,
and skills. Add Matt Pocock skills only if the user explicitly wants both
workflows and accepts overlap around planning, issues, TDD, and triage.

Ask before adding any of: `to-prd`, `to-issues`, `tdd`, `triage`, or
`setup-matt-pocock-skills`.

## UI-Heavy Projects

Recommend the shared package plus the Google Stitch bundle when the project will
use Stitch MCP or design-to-code workflows:

```bash
apm install stitch-skills@srobroek-agentic
```

Treat `stitch-skills` as a bundle that covers `stitch-design`, `stitch-loop`,
`design-md`, `enhance-prompt`, `react:components`, `remotion`, `shadcn-ui`, and
`taste-design`. Do not list those covered skills as separate choices after the
bundle is selected.

Also recommend `impeccable@srobroek-agentic` for frontend craft and
`interface-design@srobroek-agentic` for product-interface systems when relevant.
These are third-party upstream entries, not local copies.

For browser automation or UI verification, recommend the explicit MCP package:

```bash
apm install mcp-playwright@srobroek-agentic
```

Do not recommend extra design packages unless the user asks for a specific
external design workflow.

## Maintenance Or Tooling Projects

Recommend the shared package. For projects focused on dotfiles, MCP servers,
hooks, APM packages, or agent tooling, keep `project-setup`,
`agent-management`, `chezmoi-editor`, `find-tools`, `write-a-skill`, `catchup`,
and `handover` global rather than project-local.
