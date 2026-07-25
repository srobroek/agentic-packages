# Bundles

A **bundle** is a hand-authored APM package whose job is to install a coherent set of primitives. Each bundle is its own directory under [`packages/`](../packages/) with an `apm.yml` manifest that is a dependency aggregator: a `dependencies.apm:` list referencing member packages plus external third-party packages.

Install a bundle with `apm install <name>@srobroek-agentic`.

## Catalog

In the **Includes** column, each entry is a member package; an entry marked with a trailing `^` is an external third-party package (see [External sources](#external-sources)) rather than one of this marketplace's own packages.

<!-- BEGIN:bundles -->
| Bundle | What it gives you | Includes |
| --- | --- | --- |
| `agentic-maintenance` | Maintain your agentic assets | `audit-steering`, `write-agentic`, `agent-coder`, `agent-pr-reviewer` |
| `cmux` | cmux terminal control bundle | `cmux`^, `cmux-workspace`^, `cmux-customization`^, `cmux-settings`^, `cmux-diagnostics`^, `cmux-socket-policy`^, `cmux-ghostty`^, `cmux-keyboard-shortcuts`^, `cmux-shared-behavior`^ |
| `code-intelligence` | Codebase understanding toolkit | `web-fetch`, `agent-pr-reviewer`, `steering-project-structure` |
| `codex-hook-contract` | Current Codex CLI hook contract for supported events, matcher behavior, payloads, decisions, trust, and runtime limitations | self-contained |
| `core` | Baseline bundle for any repo | `project-lifecycle`, `code-intelligence`, `agentic-maintenance`, `resume-session`, `steering-delivery`, `beads`, `grilling`^, `grill-with-docs`^ |
| `data-ai` | Data and AI toolkit | `steering-data` |
| `dependency-quality` | Dependency hygiene bundle | `hooks-package-investigate`, `dep-audit` |
| `diagrams` | Diagram generation bundle for editable draw.io diagrams, visual Excalidraw diagrams, and D2 architecture or flow diagrams | `drawio-skill`^, `excalidraw-diagram-skill`^, `d2-diagram`^ |
| `frontend` | Frontend development and design toolkit | `playwright`, `steering-frontend`, `impeccable`^, `interface-design`^, `stitch-design`^ |
| `infrastructure` | Infrastructure and operations toolkit | `steering-infrastructure` |
| `language-go` | Go toolkit | `go-quality`, `lsp-go` |
| `language-python` | Python toolkit | `python-quality`, `lsp-python` |
| `language-rust` | Rust toolkit | `rust-quality`, `language-steering-rust`, `lsp-rust` |
| `language-shell` | Shell scripting toolkit with Shell LSP | `lsp-shell` |
| `language-terraform` | Terraform and HCL toolkit | `language-steering-terraform`, `lsp-terraform` |
| `language-typescript` | TypeScript and JavaScript toolkit | `typescript-quality`, `language-steering-typescript`, `lsp-typescript` |
| `lsp-go` | Go LSP server | external packages |
| `lsp-python` | Python LSP server | external packages |
| `lsp-rust` | Rust LSP server | external packages |
| `lsp-shell` | Shell LSP server | external packages |
| `lsp-terraform` | Terraform LSP server | external packages |
| `lsp-typescript` | TypeScript/JavaScript LSP server | external packages |
| `matt-skills` | Bundle of Matt Pocock's engineering and productivity skills | `grilling`^, `grill-with-docs`^, `improve-codebase-architecture`^, `setup-matt-pocock-skills`^, `tdd`^, `to-issues`^, `to-prd`^, `triage`^ |
| `planning-product` | Planning and product toolkit | `debate`, `eli5`, `web-fetch`, `to-prd`^, `to-issues`^, `tdd`^, `triage`^, `improve-codebase-architecture`^ |
| `presentation` | Presentation bundle for general decks, Marp slides, and PowerPoint template workflows | `ppt-creator`^, `marp-slide`^, `pptx-from-layouts`^ |
| `project-lifecycle` | Day-to-day project lifecycle workflows | `catchup`, `handover`, `steering-git-workflow`, `verify`, `agent-pr-reviewer` |
| `resume-cv` | CV / career-resume bundle | `resume-tailoring`^, `ResumeSkills`^ |
| `review` | Code review and verification toolkit | `verify`, `agent-pr-reviewer` |
| `speckit-beads` | Beads-native SpecKit workflow | `speckit`, `beads` |
| `toolchain-cache-policy` | Shares bounded package-manager and compiler caches across worktrees without redirecting mutable dependencies or branch output into machine-global directories | self-contained |
<!-- END:bundles -->

## How bundles work

**Member reference syntax.** Sibling packages in this monorepo are referenced as a **virtual subdirectory of the marketplace repo**, using a caret semver range (requires apm >= 0.18, fixed in upstream microsoft/apm#1633):

```yaml
dependencies:
  apm:
    - srobroek/agentic-packages/packages/code-review#^0.1.0   # member, caret range
    - srobroek/agentic-packages/packages/verify#^0.1.0
    - mattpocock/skills/skills/productivity/grilling#main      # external, by source
```

APM dependencies are repo-locators, not marketplace shortnames -- `code-review@srobroek-agentic` is **not** valid in `dependencies.apm` (that form only works on the `apm install` command line). The `owner/repo/path#ref` form resolves the same way for this repo's own dev checkout and for an external consumer installing from the marketplace.

**Caret ranges and the update workflow.** Member deps use `#^<version>` caret ranges that resolve to the latest matching `<pkg>-v<X.Y.*>` tag via the lockfile. Running `apm update` advances all members to their latest compatible release automatically. When a member bumps its minor or major version you still edit the bundle's range explicitly (making it a `feat`/`fix` commit release-please can track). External deps (mattpocock and others) stay pinned to `#main`.

**Floating `#main` for co-released first-party siblings.** Tightly coupled first-party siblings that are always released together with their bundle (for example the `language-steering-*` packages consumed by the `language-*` bundles) use a floating `#main` ref rather than a caret range. Because they live in this same repo and ship in lockstep, a caret pin adds churn (every sibling minor bump forces a bundle edit) without buying isolation -- there is no independent consumer who could be broken by tracking `main`. `#main` is therefore blessed for these co-released siblings in addition to external deps; reserve `#^<version>` caret ranges for first-party members that are versioned and consumed independently.

**Composition over duplication.** Skills and agents live as individual packages under `packages/<name>/`. A bundle does not copy their content -- it declares a caret-range dep on them. `core` now layers the three sub-bundles (`project-lifecycle`, `code-intelligence`, `agentic-maintenance`) rather than depending on leaf packages directly, so most member updates cascade through the sub-bundle without touching core at all.

Each package carries its own `apm.yml` and is versioned independently via release-please. The marketplace is hand-authored in the root [`apm.yml`](../apm.yml) `marketplace:` block and generated to `.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json` by `apm pack`. Codex plugin manifests do not define dependency composition, so install bundles through APM; native Codex installs expose only components owned directly by that package.

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
| [`manaflow-ai/cmux`](https://github.com/manaflow-ai/cmux) | 9 | `cmux`, `cmux-customization`, `cmux-diagnostics`, `cmux-ghostty`, `cmux-keyboard-shortcuts`, `cmux-settings`, `cmux-shared-behavior`, `cmux-socket-policy`, `cmux-workspace` |
| [`mattpocock/skills`](https://github.com/mattpocock/skills) | 8 | `grill-with-docs`, `grilling`, `improve-codebase-architecture`, `setup-matt-pocock-skills`, `tdd`, `to-issues`, `to-prd`, `triage` |
| [`neuro-synapse/network-topology-agent`](https://github.com/neuro-synapse/network-topology-agent) | 1 | `d2-diagram` |
| [`pbakaus/impeccable`](https://github.com/pbakaus/impeccable) | 1 | `impeccable` |
| [`softaworks/agent-toolkit`](https://github.com/softaworks/agent-toolkit) | 1 | `marp-slide` |
| [`tristan-mcinnis/pptx-from-layouts-skill`](https://github.com/tristan-mcinnis/pptx-from-layouts-skill) | 1 | `pptx-from-layouts` |
| [`varunr89/resume-tailoring-skill`](https://github.com/varunr89/resume-tailoring-skill) | 1 | `resume-tailoring` |
<!-- END:external-sources -->

---

See also: [skills](skills.md) · [agents](agents.md) · [steering](steering.md) · [hooks and MCP](hooks-and-mcp.md) · [external repos](external-repos.md) · [SpecKit](speckit.md)
