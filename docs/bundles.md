# Bundles

A **bundle** is a hand-authored APM package whose job is to install a coherent set of primitives. Each bundle is its own directory under [`packages/`](../packages/) with an `apm.yml` manifest that is a dependency aggregator: a `dependencies.apm:` list referencing member packages plus external third-party packages.

Install a bundle with `apm install <name>@srobroek-agentic`.

## Catalog

In the **Includes** column, each entry is a member package; an entry marked with a trailing `^` is an external third-party package (see [External sources](#external-sources)) rather than one of this marketplace's own packages.

<!-- BEGIN:bundles -->
| Bundle | What it gives you | Includes |
| --- | --- | --- |
| `agentic-maintenance` | Maintain your agentic assets | `optimize-steering`, `audit-steering`, `write-a-skill`, `agent-coder`, `agent-pr-reviewer`, `documentation-standards`^, `plugin-eval`^ |
| `code-intelligence` | Codebase understanding toolkit | `codebase-index`, `codebase-memory`, `mcp-codebase-memory`, `explore`, `research`, `web-fetch`, `agent-pr-reviewer`, `steering-project-structure`, `code-documentation`^, `documentation-generation`^, `c4-architecture`^ |
| `codex-hook-contract` | Reference doc for the Codex CLI hook contract as used by this monorepo's guard hooks | self-contained |
| `core` | Baseline bundle for any repo | `project-lifecycle`, `code-intelligence`, `agentic-maintenance`, `resume-session`, `grill-me`^, `grill-with-docs`^, `context-management`^, `agent-orchestration`^ |
| `core-global` | Recommended global (user-scope) baseline | `catchup`, `codebase-memory`, `debate`, `eli5`, `handover`, `write-a-skill`, `whats-new`, `chezmoi-editor`, `agent-coder`, `agent-pr-reviewer`, `agent-adversarial-challenger`, `agent-external-repo-worker`, `grill-me`^ |
| `data-ai` | Data and AI toolkit | `steering-data`, `llm-application-dev`^, `data-engineering`^, `machine-learning-ops`^, `database-design`^, `database-migrations`^, `database-cloud-optimization`^ |
| `debugging` | Local debugging escalation | `unstuck`, `agent-adversarial-challenger` |
| `dependency-quality` | Dependency hygiene bundle | `hooks-package-file-guard`, `hooks-package-investigate`, `hooks-pkg-version-warn`, `dep-audit`, `mcp-package-version` |
| `developer-tools` | Everyday developer tooling | `developer-essentials`^, `debugging-toolkit`^, `comprehensive-review`^, `git-pr-workflows`^, `documentation-generation`^ |
| `diagrams` | Diagram generation bundle for editable draw.io diagrams, visual Excalidraw diagrams, and D2 architecture or flow diagrams | `drawio-skill`^, `excalidraw-diagram-skill`^, `d2-diagram`^ |
| `docs-architecture` | Documentation and architecture | `documentation-standards`^, `code-documentation`^, `documentation-generation`^, `c4-architecture`^ |
| `frontend` | Frontend development and design toolkit | `playwright`, `steering-frontend`, `impeccable`^, `interface-design`^, `stitch-design`^, `frontend-mobile-development`^, `ui-design`^, `accessibility-compliance`^, `brand-landingpage`^ |
| `governance` | Agent governance | `protect-mcp`^, `signed-audit-trails`^, `review-agent-governance`^, `block-no-verify`^ |
| `incident-response` | Incident response and production debugging | `error-debugging`^, `distributed-debugging`^, `incident-response`^, `error-diagnostics`^, `debugging-toolkit`^ |
| `infrastructure` | Infrastructure and operations toolkit | `steering-infrastructure`, `cloud-infrastructure`^, `kubernetes-operations`^, `cicd-automation`^, `deployment-strategies`^, `deployment-validation`^, `observability-monitoring`^ |
| `language-arm-cortex` | ARM Cortex-M firmware toolkit | `arm-cortex-microcontrollers`^ |
| `language-dotnet` | .NET development toolkit | `dotnet-contribution`^ |
| `language-functional` | Functional programming toolkit | `functional-programming`^ |
| `language-go` | Go toolkit | `go-quality`, `language-steering-go`, `systems-programming`^ |
| `language-julia` | Julia development toolkit | `julia-development`^ |
| `language-jvm` | JVM language toolkit | `jvm-languages`^ |
| `language-python` | Python toolkit | `python-quality`, `language-steering-python`, `python-development`^ |
| `language-rust` | Rust toolkit | `rust-quality`, `language-steering-rust`, `systems-programming`^ |
| `language-shell` | Shell scripting toolkit | `shell-scripting`^ |
| `language-terraform` | Terraform and HCL toolkit | `language-steering-terraform`, `deployment-strategies`^ |
| `language-typescript` | TypeScript and JavaScript toolkit | `typescript-quality`, `language-steering-typescript`, `javascript-typescript`^ |
| `language-web-scripting` | PHP and Ruby web scripting toolkit | `web-scripting`^ |
| `matt-skills` | Bundle of Matt Pocock's engineering and productivity skills | `grill-me`^, `grill-with-docs`^, `improve-codebase-architecture`^, `setup-matt-pocock-skills`^, `tdd`^, `to-issues`^, `to-prd`^, `triage`^ |
| `planning-product` | Planning and product toolkit | `debate`, `eli5`, `research`, `web-fetch`, `to-prd`^, `to-issues`^, `tdd`^, `triage`^, `improve-codebase-architecture`^ |
| `presentation` | Presentation bundle for general decks, Marp slides, and PowerPoint template workflows | `ppt-creator`^, `marp-slide`^, `pptx-from-layouts`^ |
| `project-lifecycle` | Day-to-day project lifecycle workflows | `catchup`, `handover`, `commit-push-merge`, `commit-push-pr`, `quick-commit`, `verify`, `agent-pr-reviewer` |
| `resume-cv` | CV / career-resume bundle | `resume-tailoring`^, `ResumeSkills`^ |
| `review` | Code review and verification toolkit | `code-review`, `verify`, `agent-pr-reviewer`, `comprehensive-review`^, `performance-testing-review`^, `unit-testing`^, `tdd-workflows`^ |
| `security` | Security toolkit | `security-scanning`^, `security-compliance`^, `backend-api-security`^, `frontend-mobile-security`^, `reverse-engineering`^ |
| `speckit` | SpecKit mechanism | `mcp-speckit-memory` |
| `speckit-dag-hooks` | Opt-in enforcement hooks for the SpecKit DAG | `speckit` |
<!-- END:bundles -->

## How bundles work

**Member reference syntax.** Sibling packages in this monorepo are referenced as a **virtual subdirectory of the marketplace repo**, using a caret semver range (requires apm >= 0.18, fixed in upstream microsoft/apm#1633):

```yaml
dependencies:
  apm:
    - srobroek/agentic-packages/packages/code-review#^0.1.0   # member, caret range
    - srobroek/agentic-packages/packages/verify#^0.1.0
    - wshobson/agents/plugins/comprehensive-review#main        # external, by source
```

APM dependencies are repo-locators, not marketplace shortnames -- `code-review@srobroek-agentic` is **not** valid in `dependencies.apm` (that form only works on the `apm install` command line). The `owner/repo/path#ref` form resolves the same way for this repo's own dev checkout and for an external consumer installing from the marketplace.

**Caret ranges and the update workflow.** Member deps use `#^<version>` caret ranges that resolve to the latest matching `<pkg>-v<X.Y.*>` tag via the lockfile. Running `apm update` advances all members to their latest compatible release automatically. When a member bumps its minor or major version you still edit the bundle's range explicitly (making it a `feat`/`fix` commit release-please can track). External deps (wshobson, mattpocock) stay pinned to `#main`.

**Floating `#main` for co-released first-party siblings.** Tightly coupled first-party siblings that are always released together with their bundle (for example the `language-steering-*` packages consumed by the `language-*` bundles) use a floating `#main` ref rather than a caret range. Because they live in this same repo and ship in lockstep, a caret pin adds churn (every sibling minor bump forces a bundle edit) without buying isolation -- there is no independent consumer who could be broken by tracking `main`. `#main` is therefore blessed for these co-released siblings in addition to external deps; reserve `#^<version>` caret ranges for first-party members that are versioned and consumed independently.

**Composition over duplication.** Skills and agents live as individual packages under `packages/<name>/`. A bundle does not copy their content -- it declares a caret-range dep on them. `core` now layers the three sub-bundles (`project-lifecycle`, `code-intelligence`, `agentic-maintenance`) rather than depending on leaf packages directly, so most member updates cascade through the sub-bundle without touching core at all.

Each package carries its own `apm.yml` and is versioned independently via release-please. The marketplace is hand-authored in the root [`apm.yml`](../apm.yml) `marketplace:` block and generated to `.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json` by `apm pack`.

## External sources

Bundles also pull in third-party skills and agents (marked `^` in the **Includes** column above). Their descriptions are owned and maintained upstream -- this table records only which repo each comes from. See the source repo for what each does.

<!-- BEGIN:external-sources -->
| Source repo | Count | Members pulled |
| --- | --- | --- |
| [`Agents365-ai/drawio-skill`](https://github.com/Agents365-ai/drawio-skill) | 1 | `drawio-skill` |
| [`Dammyjay93/interface-design`](https://github.com/Dammyjay93/interface-design) | 1 | `interface-design` |
| [`Paramchoudhary/ResumeSkills`](https://github.com/Paramchoudhary/ResumeSkills) | 1 | `ResumeSkills` |
| [`coleam00/excalidraw-diagram-skill`](https://github.com/coleam00/excalidraw-diagram-skill) | 1 | `excalidraw-diagram-skill` |
| [`daymade/claude-code-skills`](https://github.com/daymade/claude-code-skills) | 1 | `ppt-creator` |
| [`google-labs-code/stitch-skills`](https://github.com/google-labs-code/stitch-skills) | 1 | `stitch-design` |
| [`mattpocock/skills`](https://github.com/mattpocock/skills) | 8 | `grill-me`, `grill-with-docs`, `improve-codebase-architecture`, `setup-matt-pocock-skills`, `tdd`, `to-issues`, `to-prd`, `triage` |
| [`neuro-synapse/network-topology-agent`](https://github.com/neuro-synapse/network-topology-agent) | 1 | `d2-diagram` |
| [`pbakaus/impeccable`](https://github.com/pbakaus/impeccable) | 1 | `impeccable` |
| [`softaworks/agent-toolkit`](https://github.com/softaworks/agent-toolkit) | 1 | `marp-slide` |
| [`tristan-mcinnis/pptx-from-layouts-skill`](https://github.com/tristan-mcinnis/pptx-from-layouts-skill) | 1 | `pptx-from-layouts` |
| [`varunr89/resume-tailoring-skill`](https://github.com/varunr89/resume-tailoring-skill) | 1 | `resume-tailoring` |
| [`wshobson/agents`](https://github.com/wshobson/agents) | 53 | `accessibility-compliance`, `agent-orchestration`, `arm-cortex-microcontrollers`, `backend-api-security`, `block-no-verify`, `brand-landingpage`, `c4-architecture`, `cicd-automation`, `cloud-infrastructure`, `code-documentation`, `comprehensive-review`, `context-management`, `data-engineering`, `database-cloud-optimization`, `database-design`, `database-migrations`, `debugging-toolkit`, `deployment-strategies`, `deployment-validation`, `developer-essentials`, `distributed-debugging`, `documentation-generation`, `documentation-standards`, `dotnet-contribution`, `error-debugging`, `error-diagnostics`, `frontend-mobile-development`, `frontend-mobile-security`, `functional-programming`, `git-pr-workflows`, `incident-response`, `javascript-typescript`, `julia-development`, `jvm-languages`, `kubernetes-operations`, `llm-application-dev`, `machine-learning-ops`, `observability-monitoring`, `performance-testing-review`, `plugin-eval`, `protect-mcp`, `python-development`, `reverse-engineering`, `review-agent-governance`, `security-compliance`, `security-scanning`, `shell-scripting`, `signed-audit-trails`, `systems-programming`, `tdd-workflows`, `ui-design`, `unit-testing`, `web-scripting` |
<!-- END:external-sources -->

---

See also: [skills](skills.md) · [agents](agents.md) · [steering](steering.md) · [hooks and MCP](hooks-and-mcp.md) · [SpecKit](speckit.md)
