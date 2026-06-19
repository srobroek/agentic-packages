# Bundles

A **bundle** is a hand-authored APM package whose job is to install a coherent set of primitives. Each bundle is its own directory under [`packages/`](../packages/) with an `apm.yml` manifest that is a dependency aggregator: a `dependencies.apm:` list referencing member packages plus external third-party packages.

Install a bundle with `apm install <name>@srobroek-agentic`.

## Catalog

In the **Includes** column, each entry is a member package; an entry marked with a trailing `^` is an external third-party package (see [External sources](#external-sources)) rather than one of this marketplace's own packages.

<!-- BEGIN:bundles -->
| Bundle | What it gives you | Includes |
| --- | --- | --- |
| `agentic-maintenance` | Maintain your agentic assets | `optimize-steering`, `prompt-lookup`, `audit-steering`, `write-a-skill`, `agent-coder`, `agent-pr-reviewer`, `documentation-standards`^, `plugin-eval`^ |
| `code-intelligence` | Codebase understanding toolkit | `codebase-index`, `codebase-memory`, `explore`, `prompt-lookup`, `research`, `web-fetch`, `agent-pr-reviewer`, `steering-project-structure`, `code-documentation`^, `documentation-generation`^, `c4-architecture`^ |
| `core` | Flat baseline bundle for any repo | `catchup`, `handover`, `commit-push-merge`, `commit-push-pr`, `quick-commit`, `verify`, `codebase-index`, `codebase-memory`, `explore`, `prompt-lookup`, `research`, `web-fetch`, `steering-project-structure`, `optimize-steering`, `audit-steering`, `write-a-skill`, `headroom`, `agent-coder`, `agent-pr-reviewer`, `diagnose`^, `grill-me`^, `grill-with-docs`^, `context-management`^, `agent-orchestration`^, `code-documentation`^, `documentation-generation`^, `c4-architecture`^, `documentation-standards`^, `plugin-eval`^ |
| `core-global` | Recommended global (user-scope) baseline | `catchup`, `codebase-memory`, `debate`, `eli5`, `handover`, `write-a-skill`, `headroom`, `chezmoi-editor`, `agent-coder`, `agent-pr-reviewer`, `agent-adversarial-challenger`, `agent-external-repo-worker`, `grill-me`^ |
| `data-ai` | Data and AI toolkit | `steering-data`, `llm-application-dev`^, `data-engineering`^, `machine-learning-ops`^, `database-design`^, `database-migrations`^, `database-cloud-optimization`^ |
| `debugging` | Local debugging escalation | `unstuck`, `agent-adversarial-challenger`, `diagnose`^ |
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
| `matt-skills` | Bundle of Matt Pocock's engineering and productivity skills | `caveman`^, `diagnose`^, `grill-me`^, `grill-with-docs`^, `improve-codebase-architecture`^, `setup-matt-pocock-skills`^, `tdd`^, `to-issues`^, `to-prd`^, `triage`^, `zoom-out`^ |
| `planning-product` | Planning and product toolkit | `debate`, `eli5`, `research`, `web-fetch`, `to-prd`^, `to-issues`^, `tdd`^, `triage`^, `zoom-out`^, `improve-codebase-architecture`^ |
| `presentation` | Presentation bundle for general decks, Marp slides, and PowerPoint template workflows | `ppt-creator`^, `marp-slide`^, `pptx-from-layouts`^ |
| `project-lifecycle` | Day-to-day project lifecycle workflows | `catchup`, `handover`, `commit-push-merge`, `commit-push-pr`, `quick-commit`, `verify`, `agent-pr-reviewer` |
| `resume` | Resume bundle for focused resume tailoring and broad career-support workflows | `resume-tailoring`^, `ResumeSkills`^ |
| `review` | Code review and verification toolkit | `code-review`, `verify`, `agent-pr-reviewer`, `comprehensive-review`^, `performance-testing-review`^, `unit-testing`^, `tdd-workflows`^ |
| `security` | Security toolkit | `security-scanning`^, `security-compliance`^, `backend-api-security`^, `frontend-mobile-security`^, `reverse-engineering`^ |
| `speckit` | SpecKit mechanism | self-contained |
| `speckit-dag-hooks` | Opt-in enforcement hooks for the SpecKit DAG | `speckit` |
<!-- END:bundles -->

## How bundles work

**Member reference syntax.** Sibling packages in this monorepo are referenced as a **virtual subdirectory of the marketplace repo**, version-pinned to the member's release tag:

```yaml
dependencies:
  apm:
    - srobroek/agentic-packages/packages/code-review#code-review-v0.1.0   # member, pinned
    - srobroek/agentic-packages/packages/verify#verify-v0.1.0
    - wshobson/agents/plugins/comprehensive-review#main                   # external, by source
```

APM dependencies are repo-locators, not marketplace shortnames -- `code-review@srobroek-agentic` is **not** valid in `dependencies.apm` (that form only works on the `apm install` command line). The `owner/repo/path#ref` form resolves the same way for this repo's own dev checkout and for an external consumer installing from the marketplace.

**Pinning and the bump workflow.** Member deps are pinned to a specific `#<member>-v<version>` tag (created by release-please on release). Pinning is deliberate: a bundle only moves to a newer member when you **edit its pin**, which is a `feat`/`fix` commit on the bundle that release-please then bumps. So updating a member is two explicit steps -- release the member, then re-pin (and thereby bump) each bundle that should adopt it. There is no automatic cascade. (Semver ranges would remove the manual step but do not yet work for monorepo subpath deps -- see [issue #239](https://github.com/srobroek/agentic-packages/issues/239) and upstream [microsoft/apm#1633](https://github.com/microsoft/apm/issues/1633).)

**Composition over duplication.** Skills and agents live as individual packages under `packages/<name>/`. A bundle does not copy their content -- it pins a dependency on them. `core` is flattened to depend on leaf skills/agents directly (no bundle-on-bundle edge), so a member bump needs at most a single re-pin layer.

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
| [`mattpocock/skills`](https://github.com/mattpocock/skills) | 11 | `caveman`, `diagnose`, `grill-me`, `grill-with-docs`, `improve-codebase-architecture`, `setup-matt-pocock-skills`, `tdd`, `to-issues`, `to-prd`, `triage`, `zoom-out` |
| [`neuro-synapse/network-topology-agent`](https://github.com/neuro-synapse/network-topology-agent) | 1 | `d2-diagram` |
| [`pbakaus/impeccable`](https://github.com/pbakaus/impeccable) | 1 | `impeccable` |
| [`softaworks/agent-toolkit`](https://github.com/softaworks/agent-toolkit) | 1 | `marp-slide` |
| [`tristan-mcinnis/pptx-from-layouts-skill`](https://github.com/tristan-mcinnis/pptx-from-layouts-skill) | 1 | `pptx-from-layouts` |
| [`varunr89/resume-tailoring-skill`](https://github.com/varunr89/resume-tailoring-skill) | 1 | `resume-tailoring` |
| [`wshobson/agents`](https://github.com/wshobson/agents) | 53 | `accessibility-compliance`, `agent-orchestration`, `arm-cortex-microcontrollers`, `backend-api-security`, `block-no-verify`, `brand-landingpage`, `c4-architecture`, `cicd-automation`, `cloud-infrastructure`, `code-documentation`, `comprehensive-review`, `context-management`, `data-engineering`, `database-cloud-optimization`, `database-design`, `database-migrations`, `debugging-toolkit`, `deployment-strategies`, `deployment-validation`, `developer-essentials`, `distributed-debugging`, `documentation-generation`, `documentation-standards`, `dotnet-contribution`, `error-debugging`, `error-diagnostics`, `frontend-mobile-development`, `frontend-mobile-security`, `functional-programming`, `git-pr-workflows`, `incident-response`, `javascript-typescript`, `julia-development`, `jvm-languages`, `kubernetes-operations`, `llm-application-dev`, `machine-learning-ops`, `observability-monitoring`, `performance-testing-review`, `plugin-eval`, `protect-mcp`, `python-development`, `reverse-engineering`, `review-agent-governance`, `security-compliance`, `security-scanning`, `shell-scripting`, `signed-audit-trails`, `systems-programming`, `tdd-workflows`, `ui-design`, `unit-testing`, `web-scripting` |
<!-- END:external-sources -->

---

See also: [skills](skills.md) · [agents](agents.md) · [steering](steering.md) · [hooks and MCP](hooks-and-mcp.md) · [SpecKit](speckit.md)
