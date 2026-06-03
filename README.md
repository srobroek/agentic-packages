# srobroek/agentic-packages

Shared agentic tooling for AI coding assistants -- installable through [APM](https://microsoft.github.io/apm/), the Agent Package Manager.

This repository is an **APM marketplace**: a curated catalog of agents, skills, hooks, steering instructions, MCP server definitions, and a SpecKit-driven orchestration system. Everything is authored once under `.apm/` and compiled to whatever runtime you use -- Claude Code, Codex, Copilot, Cursor, Gemini, OpenCode, or Windsurf.

- **33 bundles** -- opinionated dependency-aggregator packages grouping skills, agents, and steering for a domain (frontend, security, a language toolchain, SpecKit, ...)
- **26 skills** -- reusable workflows, each its own package (catchup, code-review, research, verify, ...)
- **4 agents** -- sub-agents with model/tool/permission profiles (coder, pr-reviewer, adversarial-challenger, external-repo-worker)
- **15 steering packages** -- opt-in opinionated conventions (per domain and per language)
- **6 MCP server packages** -- pre-wired Model Context Protocol servers (context7, playwright, repomix, ...)
- **2 hook packages** -- opt-in lifecycle hooks (git-workflow, quality), cross-tool for Claude and Codex

Many packages also ship **hooks** directly: code-intelligence (indexing/discovery), agent-coder (delegation reminder), unstuck (stuck detection), the MCP packages (version/snapshot refresh), and speckit (workflow guards). Hooks deploy per package and target whichever runtime supports the event.

---

## Table of contents

- [Quick start](#quick-start)
- [Installing APM](#installing-apm)
- [Adding the marketplace](#adding-the-marketplace)
- [Consuming as a native plugin marketplace (no APM CLI)](#consuming-as-a-native-plugin-marketplace-no-apm-cli)
- [Installing a bundle, package, or tool](#installing-a-bundle-package-or-tool)
- [How bundles work](#how-bundles-work)
- [Compiling for different targets](#compiling-for-different-targets)
- [SpecKit orchestration](#speckit-orchestration)
  - [Setting up a SpecKit project](#setting-up-a-speckit-project)
- [The how and why of SpecKit orchestration](#the-how-and-why-of-speckit-orchestration)
- [Inventory](#inventory)
- [Developing this repository](#developing-this-repository)

---

## Quick start

```bash
# 1. Install the APM CLI (see next section for alternatives)
uv tool install apm-cli

# 2. Register this marketplace
apm marketplace add srobroek/agentic-packages --name srobroek-agentic

# 3. Browse what's available
apm marketplace browse srobroek-agentic

# 4. Install the baseline bundle into your project
apm install core@srobroek-agentic --target claude,codex

# 5. Compile steering into your runtime's native context files
apm compile --target codex,claude --no-constitution
```

`core` is the deterministic baseline -- core agents, code-intelligence skills, project-lifecycle skills, agentic-maintenance skills, and the Matt Pocock diagnose/grill workflows. Add domain bundles (`frontend`, `security`, `language-python`, ...) on top as needed.

---

## Installing APM

APM is a Python CLI. Any of these work:

```bash
uv tool install apm-cli                   # isolated, recommended
mise use -g "pipx:apm-cli"                # if you use mise
```

No-install one-shot (handy in CI or before committing to an install):

```bash
uv tool run --from apm-cli apm --version
```

Verify:

```bash
apm --version    # Agent Package Manager (APM) CLI version 0.16.0+
```

This repository targets **APM 0.16.0 or newer**.

---

## Adding the marketplace

A marketplace is a catalog APM can resolve packages from. Register this one once per machine:

```bash
apm marketplace add srobroek/agentic-packages --name srobroek-agentic
apm marketplace browse srobroek-agentic
```

You can then install any catalog entry with the `name@marketplace` form (see below).

**Direct from GitHub** -- if you'd rather skip the marketplace and pin the repo directly, add it to your project `apm.yml`:

```yaml
dependencies:
  apm:
    - srobroek/agentic-packages            # whole repo
    - srobroek/agentic-packages#v1.2.0     # pinned to a tag
```

---

## Consuming as a native plugin marketplace (no APM CLI)

`apm pack` generates native plugin-marketplace manifests committed at the repo root, so this catalog also works as a **first-class plugin marketplace** for Claude Code and Codex without installing the APM CLI:

- `.claude-plugin/marketplace.json` -- Claude Code plugin marketplace (86 plugins)
- `.agents/plugins/marketplace.json` -- Codex / cross-client plugin marketplace (86 plugins)

Plugin `source` values are repo-relative (`./packages/<name>`). Claude resolves relative sources **only when the marketplace is added via Git** (the case here), so this works out of the box.

### Claude Code

Interactively:

```text
/plugin marketplace add srobroek/agentic-packages
/plugin install core@srobroek-agentic
```

`/plugin marketplace add` accepts the `owner/repo` GitHub shorthand (append `@<ref>` to pin a branch or tag); `/plugin install <name>@srobroek-agentic` installs any catalog entry. Run `/plugin` for the interactive Discover menu.

Non-interactively, in project `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "srobroek-agentic": {
      "source": { "source": "github", "repo": "srobroek/agentic-packages" }
    }
  },
  "enabledPlugins": [
    { "marketplace": "srobroek-agentic", "plugin": "core" }
  ]
}
```

### Codex

Codex reads the same catalog from `.agents/plugins/marketplace.json` (entries carry a `category` and an `installation`/`authentication` policy). Add the marketplace by repo and enable the plugins you want through Codex's plugin configuration; the entries resolve to the same `./packages/<name>` sources.

> The APM CLI flow (above) and the native plugin flow (here) install the same packages from the same catalog -- pick whichever fits your setup. The APM flow additionally runs `apm compile` + `patch-agentic-tools`; native plugins are consumed directly by the runtime.

---

## Installing a bundle, package, or tool

All three are installed the same way -- by name from the marketplace, or by subdir from the repo.

```bash
# A bundle (group of skills/agents/steering)
apm install frontend@srobroek-agentic

# A single skill
apm install code-review@srobroek-agentic

# A single agent
apm install agent-pr-reviewer@srobroek-agentic

# An MCP server package
apm install mcp-context7@srobroek-agentic
```

`--target` is **optional** -- plain `apm install` and `apm compile` auto-detect which runtimes to deploy for from what's already in your project (`.claude/`, `.codex/`, etc.). Only pass `--target` when you want to force a specific set, e.g. on a fresh project that doesn't have those dirs yet:

```bash
apm install core@srobroek-agentic --target claude,codex
```

After installing, compile steering into your runtime's context files:

```bash
apm install --target claude,codex
apm compile --target codex,claude --no-constitution
```

Then, **as an optional post-deploy step**, patch agent metadata that APM's generic conversion drops:

```bash
apm run patch-agentic-tools   # apply tuned model / effort / sandbox / approval to deployed agents
apm run audit-agentic-tools   # report runtime parity + agent metadata completeness
```

A ready-made `apm.yml` for consuming projects lives in [`templates/project-apm.yml`](templates/project-apm.yml) -- it wires all four steps as `apm run setup-agentic-tools`.

> **Why patch?** `apm install` deploys primitives (skills, agents, hooks, MCP) and `apm compile` turns instructions into the root context files each runtime reads -- agents are **fully functional after these two steps**. APM preserves a Claude agent's top-level `model:`, but its generic conversion does not map the cross-tool `x-agentic` block: a Codex agent falls back to Codex defaults (no tuned model / reasoning-effort / sandbox / approval), and a Claude agent's `effort` / `permissions.mode` are not applied. `patch-agentic-tools` restores those fields on the already-deployed `.claude/agents/*.md` and `.codex/agents/*.toml`. Skip it if the runtime defaults are fine; run it to get the tuned profiles.
>
> Target one runtime by narrowing `--target` (for example `apm compile --target claude --no-constitution` for Claude-only); `--target codex,claude` compiles both in a single pass, and `patch-agentic-tools` patches whichever runtime dirs are present.

---

## How bundles work

A **bundle** is a hand-authored APM package whose job is to install a coherent set of primitives. Each bundle is its own directory under [`packages/`](packages/) with an `apm.yml` manifest. The manifest is a dependency aggregator: a `dependencies.apm:` list referencing member packages plus any external third-party packages (Matt Pocock skills, Hobson agents, ...).

**Member reference syntax.** Sibling packages in this monorepo are referenced as a **virtual subdirectory of the marketplace repo**, version-pinned to the member's release tag:

```yaml
dependencies:
  apm:
    - srobroek/agentic-packages/packages/code-review#code-review-v0.1.0   # member, pinned
    - srobroek/agentic-packages/packages/verify#verify-v0.1.0
    - wshobson/agents/plugins/comprehensive-review#main                   # external, by source
```

APM dependencies are repo-locators, not marketplace shortnames -- `code-review@srobroek-agentic` is **not** valid in `dependencies.apm` (that form only works on the `apm install` command line). The `owner/repo/path#ref` form resolves the same way for this repo's own dev checkout and for an external consumer installing from the marketplace.

**Pinning and the bump workflow.** Member deps are pinned to a specific `#<member>-v<version>` tag (created by release-please on release). Pinning is deliberate: a bundle only moves to a newer member when you **edit its pin**, which is a `feat`/`fix` commit on the bundle that release-please then bumps. So updating a member is two explicit steps -- release the member, then re-pin (and thereby bump) each bundle that should adopt it. There is no automatic cascade.

**Composition over duplication.** Skills and agents live as individual packages under `packages/<name>/`. A bundle does not copy their content -- it pins a dependency on them. Bundles can also depend on other bundles, so `core` aggregates project-lifecycle, code-intelligence, and agentic-maintenance, and language bundles layer a single quality skill plus language steering on top.

**Hooks ship with their owning package.** A package can carry `.apm/hooks/<pkg>-{claude,codex}-hooks.json` plus a `scripts/` directory; hook commands reference their scripts via `${PLUGIN_ROOT}/scripts/<name>.sh`. On install, APM deploys the scripts under `.claude/hooks/<pkg>/` and `.codex/hooks/<pkg>/`, rewrites `${PLUGIN_ROOT}`, and merges the hook config into `settings.json` / `hooks.json`. Codex only supports `UserPromptSubmit`, `PreToolUse`, `PermissionRequest`, `PostToolUse`, and `Stop`; lifecycle events like `SessionStart` and `SubagentStart` are Claude-only, so those hooks ship in the claude variant only.

Each package carries its own `apm.yml` and is versioned independently via release-please. The marketplace itself is hand-authored in the root [`apm.yml`](apm.yml) `marketplace:` block using local-path sources, and generated to `.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json` by `apm pack`.

To regenerate artifacts after editing a manifest:

```bash
apm pack                # regenerate the marketplace manifests only
apm run build-artifacts # release-please config + README tables + apm pack
```

---

## Compiling for different targets

`apm compile` reads your instructions (local `.apm/` + installed `apm_modules/`) and writes the root context file each runtime loads at startup. One source, many targets:

```bash
apm compile --target codex            # AGENTS.md only
apm compile --target claude           # CLAUDE.md only
apm compile --target codex,claude     # both (default for this project)
apm compile --all                     # every canonical target
```

`compilation.strategy: distributed` (set in `apm.yml`) places scoped instructions next to the code they apply to via `applyTo:` globs; `single-file` collapses everything into one root file.

`--no-constitution` excludes any SpecKit `memory/constitution.md` block -- both the `<!-- SPEC-KIT CONSTITUTION -->` markers and the constitution body -- from a clean compile. (An existing block already on disk is preserved, not regenerated.)

---

## SpecKit orchestration

SpecKit is delivered as three opt-in packages (see [Setting up a SpecKit project](#setting-up-a-speckit-project)): `speckit` (six sub-agents + bugfix/setup skills + the DAG node store + workflow guard hooks), `steering-speckit` (the gated workflow steering), and `speckit-dag-hooks` (the **hook-enforced orchestration DAG** dispatcher). Together they turn ad-hoc "vibe coding" into a gated pipeline:

```
specify -> clarify -> checklist -> plan -> tasks -> critique + security-review
        -> analyze -> issues -> checkpoint
        -> assign -> validate -> execute (checkpoint per task)
        -> verify-tasks + verify -> code-review + security-review
        -> cleanup -> sync + conflicts -> retro -> docs -> final checkpoint
```

The six agents are read-only analysts except where noted:

| Agent | Role |
| --- | --- |
| `speckit-research` | Pulls current library/API docs (Context7, official sources) tied to a spec decision; returns cited findings. |
| `speckit-implement-task` | Executes scoped tasks from `tasks.md`, or delegates substantial code work to a coder. |
| `speckit-verify` | Checks implementation against the spec's functional requirements and success criteria. |
| `speckit-verify-tasks` | Detects *phantom completions* -- tasks marked done with no real implementation evidence. |
| `speckit-sync` | Detects drift between specs and implementation. |
| `speckit-sync-conflicts` | Detects contradictions between specs or against shared contracts. |

### Setting up a SpecKit project

Three layers, installed separately so you can opt into exactly what you want:

- **`speckit`** -- the mechanism: six SpecKit sub-agents, the `speckit-bugfix` skill, the `speckit-setup` bootstrap skill, and the `speckit-dag` node store. Also ships the SpecKit workflow guard hooks (issue/PR conventions, commit checks, stop gate).
- **`steering-speckit`** -- the opinionated mandatory-gated Phase 1/2/3 workflow steering. Opt in to adopt the process.
- **`speckit-dag-hooks`** -- the enforcement layer: the Python DAG dispatcher + `nodes.json` + hooks that hard-block out-of-order `/speckit.*` calls. Depends on `speckit`.

The `/speckit.*` slash commands themselves come from the upstream [`github/spec-kit`](https://github.com/github/spec-kit) `specify` CLI plus community extensions.

**Recommended -- via the `speckit-setup` skill** (shipped in the `speckit` package):

```bash
apm install speckit@srobroek-agentic --target claude,codex
```

Then invoke the skill (it is self-describing -- ask the agent to "set up SpecKit"). It bootstraps SpecKit end-to-end:

1. `specify init --here --integration codex --script sh` -- scaffolds `.specify/` (constitution, feature dirs, workflow state).
2. Registers the community extension catalog: `https://raw.githubusercontent.com/github/spec-kit/main/extensions/catalog.community.json`
3. Installs and enables the required extension set and the workflow definitions (`speckit`, `speckit-quality`, `speckit-full`).

**Manual setup** -- if you prefer to drive `specify` yourself:

```bash
# 1. Install the specify CLI (see github/spec-kit for current install)
uv tool install specify-cli

# 2. Scaffold .specify/ in your project
specify init --here --integration codex --script sh

# 3. Register the community extension catalog
specify extension catalog add --name community --install-allowed \
  https://raw.githubusercontent.com/github/spec-kit/main/extensions/catalog.community.json

# 4. Install this repo's speckit layers
apm install speckit@srobroek-agentic --target claude,codex
apm install steering-speckit@srobroek-agentic        # opt-in: the gated workflow
apm install speckit-dag-hooks@srobroek-agentic       # opt-in: hard-block enforcement
apm compile --target codex,claude --no-constitution
```

The enforcement hooks key off `.specify/feature.json` (or the git branch) to resolve the active feature, so a scaffolded `.specify/` directory is a prerequisite for the DAG's precondition checks to work.

---

## The how and why of SpecKit orchestration

**Why.** LLM coding agents skip steps. Left to their own judgment they call a security review "overkill," mark tasks complete that were never implemented, and let specs drift from code. The orchestration system removes that discretion: every step is mandatory by default, the ordering is fixed, and a hook layer can hard-block out-of-order or precondition-violating moves before the model acts.

**How -- three layers.**

1. **Declarative workflow** -- [`packages/steering-speckit/.apm/instructions/50-speckit-workflow.instructions.md`](packages/steering-speckit/.apm/instructions/50-speckit-workflow.instructions.md) defines the full Phase 1 (spec, human-gated) -> Phase 2 (implementation) -> Phase 3 (post-implementation QA) DAG and the standing rules: *all steps mandatory, always invoke via the Skill tool, always get approval between phases.*

2. **The DAG node store** -- [`packages/speckit/.apm/skills/speckit-dag/nodes/`](packages/speckit/.apm/skills/speckit-dag/nodes/) holds a `<step>.pre.md` and `<step>.post.md` pair for each step. `pre.md` declares legitimate predecessors and **preconditions**; `post.md` declares the default next step and **postconditions**. This is the graph -- edges live in these files, not in code. The same edges are compiled into [`packages/speckit-dag-hooks/scripts/nodes.json`](packages/speckit-dag-hooks/scripts/nodes.json), which the dispatcher reads at runtime.

3. **The hook dispatcher** -- [`packages/speckit-dag-hooks/scripts/dispatcher.py`](packages/speckit-dag-hooks/scripts/dispatcher.py) (a self-contained Python script, no build step) runs on every `/speckit.*` invocation, wired through [`speckit-claude-hooks.json`](packages/speckit-dag-hooks/.apm/hooks/speckit-claude-hooks.json) and [`speckit-codex-hooks.json`](packages/speckit-dag-hooks/.apm/hooks/speckit-codex-hooks.json):
   - **Pre phase** evaluates hard-block directives from `nodes.json` and **denies** the call if violated:
     - `HARD-MISSING: specs/<feat>/spec.md` -- blocks if a required artifact is absent (e.g. `plan` before `spec`)
     - `HARD-EXISTS: <path>` -- blocks if an artifact that shouldn't exist yet does (routes to a refine path)
     - `HARD-DEPRECATED:` -- blocks unconditionally
   - It resolves the `<feat>` placeholder from `$SPECIFY_FEATURE_DIRECTORY`, then `.specify/feature.json`, then the git branch -- so preconditions are feature-aware.
   - Otherwise it injects the node body as `additionalContext` (soft steering -- "you came from X, go to Y next").

**Hook events.** Claude wires `UserPromptExpansion`, `PreToolUse`, `PostToolUse`; Codex wires `UserPromptSubmit`, `PreToolUse`, `PostToolUse`. Pre fires before the skill runs (can deny); post fires after (only steers).

**Mandatory-step enforcement.** Node `.pre.md` files phrase skips as *"only if the user explicitly skips X"* rather than *"acceptable if X skipped"* -- combined with the standing rule that steps are mandatory, the agent suggests the next step every time and only omits one on explicit user request. The May-2026 DAG reorder moved `critique` and `security-review` to run in parallel right after `tasks`, and made the post-implementation QA steps (verify, verify-tasks, code-review, security-review) mandatory rather than optional.

**The payoff.** Security review and phantom-completion detection can't be silently dropped; specs can't be hand-edited around the Skill tool; and the same gated flow compiles to both Claude and Codex from one definition.

---

## Inventory

The tables below are generated from [`indexes/*.json`](indexes/) by [`build-readme-tables.py`](.apm/scripts/build-readme-tables.py) and kept current by CI -- do not edit them by hand.

### Bundles

In the **Includes** column, each entry is a member package; an entry marked with a trailing `^` is an external third-party package (Matt Pocock, Hobson, and others) rather than one of this marketplace's own packages.

<!-- BEGIN:bundles -->
| Bundle | What it gives you | Includes |
| --- | --- | --- |
| `agentic-maintenance` | Maintain your agentic assets | `optimize-steering`, `prompt-lookup`, `audit-steering`, `write-a-skill`, `agent-coder`, `agent-pr-reviewer`, `documentation-standards`^, `plugin-eval`^ |
| `code-intelligence` | Codebase understanding toolkit | `codebase-index`, `codebase-memory`, `explore`, `prompt-lookup`, `research`, `web-fetch`, `agent-pr-reviewer`, `steering-project-structure`, `code-documentation`^, `documentation-generation`^, `c4-architecture`^ |
| `core` | Flat baseline bundle for any repo | `catchup`, `handover`, `commit-push-merge`, `commit-push-pr`, `quick-commit`, `verify`, `codebase-index`, `codebase-memory`, `explore`, `prompt-lookup`, `research`, `web-fetch`, `steering-project-structure`, `optimize-steering`, `audit-steering`, `write-a-skill`, `agent-coder`, `agent-pr-reviewer`, `diagnose`^, `grill-me`^, `grill-with-docs`^, `context-management`^, `agent-orchestration`^, `code-documentation`^, `documentation-generation`^, `c4-architecture`^, `documentation-standards`^, `plugin-eval`^ |
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

### MCP server packages

Pre-wired Model Context Protocol servers. Installing one adds the server's tools to your runtime's MCP config -- no manual server setup.

<!-- BEGIN:mcp -->
| MCP Package | Description |
| --- | --- |
| `mcp-codebase-memory` | MCP server package for the Codebase Memory MCP, providing graph-aware project orientation (symbol search, call paths, code snippets). |
| `mcp-context7` | MCP server package for Context7, providing current library and framework documentation lookups. |
| `mcp-package-version` | MCP server package for Package Version, providing dependency version discovery before adding or upgrading packages. |
| `mcp-playwright` | MCP server package for Playwright, providing browser automation and in-browser UI verification. |
| `mcp-repomix` | MCP server package for Repomix, providing bulk repository snapshots for analysis and review. |
| `mcp-serena` | MCP server package for Serena semantic code tools. The launcher selects the Codex or Claude Code context from the parent harness and can be overridden with SERENA_MCP_CONTEXT. |
<!-- END:mcp -->

### Agents

Sub-agents the main thread can delegate to, each with its own model, tool access, and permission profile. Install an agent package to make it available to your runtime's delegation/`Task` tooling.

<!-- BEGIN:agents -->
| Agent | Description |
| --- | --- |
| `agent-adversarial-challenger` | Read-only adversarial challenger: independently stress-tests a plan, hypothesis, design, or fix by attacking its assumptions and returning evidence-backed counter-arguments and alternatives, without editing files. The critic half of a generate/critique loop; the unstuck debugging escalation is one application. |
| `agent-coder` | Implementation subagent for bounded code changes, tests, and refactors within a defined scope. |
| `agent-external-repo-worker` | Subagent that works inside an external repository outside the caller project. Handles isolated clone or reuse, convention discovery, bounded edits, local verification, and delegated publish or PR work. |
| `agent-pr-reviewer` | Subagent that reviews pull requests for code quality, security, and best practices. |
<!-- END:agents -->

### Skills

Reusable workflows, each its own package, deployed to `.agents/skills/` (cross-client). A skill is loaded on demand when its trigger matches; install only the workflows you want.

<!-- BEGIN:skills -->
| Skill | Description |
| --- | --- |
| `audit-steering` | Audit agent rules, hooks, skills, and guardrails for drift and cleanup. |
| `catchup` | Resume interrupted project work by locating and following the best handover before doing fresh discovery, after context loss, /clear, or a continue/resume request. |
| `code-review` | Review a diff or change set, prioritizing bugs, regressions, risks, and missing tests. |
| `codebase-index` | Rebuild the codebase-memory graph index when it is missing or stale. |
| `codebase-memory` | Graph-aware codebase exploration, tracing, and reference lookup using the codebase-memory index. |
| `commit-push-merge` | Commit local changes when needed, push, and merge a branch after inferring or confirming the target and merge method. |
| `commit-push-pr` | Commit local changes when needed, push, and open or update a pull request for review. |
| `debate` | Deep tradeoff analysis for architectural decisions, technology choices, and feature proposals. Tests an idea from both sides before recommending a path. |
| `eli5` | Explain a topic at multiple depth levels, from simple to detailed, for layered understanding. |
| `explore` | Read-only codebase orientation, file discovery, and path tracing. |
| `go-quality` | Run Go format, lint, and test checks with the project toolchain. |
| `handover` | Save a self-contained recovery prompt to the shared handover store when ending or pausing work, switching context, or preserving unfinished state. |
| `hyperresearch` | Thin APM wrapper that routes to the upstream third-party HyperResearch deep research harness for long-form, source-backed research reports. |
| `optimize-steering` | Audit and optimize agent-facing markdown (steering docs, skills, agent definitions) for token efficiency, structural compliance, and cross-model compatibility. |
| `playwright` | Automate browser interactions through a Playwright MCP server. |
| `prompt-lookup` | Find, compare, and improve prompt templates and prompt-engineering patterns. |
| `python-quality` | Run Python format, lint, type-check, and test commands with the project toolchain. |
| `quick-commit` | Create a deliberate local git commit without pushing or opening a PR, for checkpoints and fast commit-only workflows. |
| `research` | Open-ended research that synthesizes across multiple sources for comparisons, technology evaluations, and tradeoff analysis. |
| `rust-quality` | Run Rust format, lint, and test checks with the project toolchain. |
| `sniff` | Stability, hardening, and cleanup audit across a codebase. |
| `typescript-quality` | Run TypeScript or JavaScript format, lint, type-check, and test commands with the project toolchain. |
| `unstuck` | Escalate stalled debugging by challenging assumptions after the normal diagnosis loop has failed and the agent is going in circles. |
| `verify` | Run and report a final local verification pass (tests, types, build, lint) before handoff, commit, push, merge, or PR. |
| `web-fetch` | Retrieve current or URL-specific information from the web with source-aware tool routing for fetching, browsing, citing, and verifying online. |
| `write-a-skill` | Create or rewrite agent skills with precise triggers, progressive disclosure, references, scripts, and source-of-truth placement. |
<!-- END:skills -->

### Steering packages

Opt-in opinionated steering (instructions + context). Install only the conventions you want.

<!-- BEGIN:steering -->
| Steering Package | Description |
| --- | --- |
| `language-steering-go` | Opt-in opinionated Go defaults: prefer the standard library, urfave/cli for CLIs, koanf for layered config. Install to adopt these picks; the language-go package carries the non-opinionated structural conventions. |
| `language-steering-python` | Opt-in opinionated Python defaults: tooling (uv, Ruff, pytest, pyright) and libraries (FastAPI, Pydantic, Litestar). Install to adopt these picks; the language-python package carries the non-opinionated structural conventions. |
| `language-steering-rust` | Opt-in opinionated Rust defaults: cargo/clippy/rustfmt, thiserror for libraries, anyhow for binaries, clap for CLIs. Install to adopt these picks; the language-rust package carries the non-opinionated structural conventions. |
| `language-steering-terraform` | Opt-in opinionated Terraform and HCL defaults: module preference order, remote state with locking, version pinning, and plan/validate discipline. Install to adopt these picks; the language-terraform package carries the non-opinionated structural conventions. |
| `language-steering-typescript` | Opt-in opinionated TypeScript and JavaScript defaults: tooling (Bun, pnpm, Vitest) and contracts (Zod, OpenAPI). Install to adopt these picks; the language-typescript package carries the non-opinionated structural conventions. |
| `steering-backend` | Opinionated backend conventions: service/function/worker runtime shape, API and cross-boundary contract rules, and background-job (queue, event, scheduled) patterns. Opt-in steering. |
| `steering-data` | Opinionated data conventions: data ownership, database assets, migrations, pipelines, and notebook practices. Opt-in steering. |
| `steering-docs-specs` | Opinionated documentation and spec conventions: durable docs structure, markdown practices, project-doc placement, and the SpecKit spec-workflow conventions. Opt-in steering. |
| `steering-frontend` | Opinionated frontend conventions: framework choice by surface (React/Vue/Next/Astro), UI library picks, app vs server state, and browser verification expectations. Opt-in steering -- install to adopt these frontend defaults. |
| `steering-infrastructure` | Opinionated infrastructure conventions: platform code, IaC, deployment config, CI/CD, environments, and observability. Opt-in steering. |
| `steering-project-structure` | Opt-in steering: capability-first repository structure and ownership conventions -- repo layout, ownership boundaries, shared libraries, contracts, and where docs/specs/tools live. |
| `steering-speckit` | Opinionated SpecKit workflow steering: the mandatory-gated Phase 1/2/3 DAG, human-gating rules, and command reference. Opt-in -- install alongside the speckit package to adopt this specific spec-driven process. |
| `steering-subagent-routing` | Opt-in steering: model routing and verification policy for delegated subagents -- when to delegate, model/effort choice, parallel work, and who owns verification. |
| `steering-toolchain-defaults` | Opt-in steering: opinionated default stack choices for frontend, infrastructure, and quality/observability. Install to adopt these defaults when setting up or standardizing a project. |
| `steering-tools-scripts` | Opinionated conventions for repo tooling and automation: where scripts, generators, maintained CLIs, and task runners live and how they are structured. Opt-in steering. |
<!-- END:steering -->

### Hook packages

Opt-in lifecycle hooks. Most hooks ship inside their owning package (code-intelligence, agent-coder, unstuck, the MCP packages, speckit); these two are standalone cross-cutting policy packages.

<!-- BEGIN:hooks -->
| Hook Package | Description |
| --- | --- |
| `hooks-git-workflow` | Opt-in git workflow hooks: gate commits on passing tests, track edit-vs-test state, and warn about uncommitted work at session end. Cross-tool (Claude + Codex). |
| `hooks-quality` | Opt-in code-quality hooks: advisory linting/formatting feedback after edits and a quality check before commits. Cross-tool (Claude + Codex). |
<!-- END:hooks -->

---

## Developing this repository

Every installable asset -- each skill, agent, MCP package, bundle, steering package, and hook package -- is a hand-authored package directory under [`packages/`](packages/) with its own `apm.yml`. Edit packages directly; **do not edit generated runtime directories (`.claude/`, `.codex/`, `.agents/`, compiled `AGENTS.md`/`CLAUDE.md`) by hand.** Author agent sources in `packages/agent-*/<name>.agent.md` (and `packages/speckit/.apm/agents/`), skills in `packages/<name>/.apm/skills/` or a root `SKILL.md`, and hooks in `packages/<pkg>/.apm/hooks/` + `packages/<pkg>/scripts/`.

Each package has its own `apm.yml` and is versioned independently via release-please. The marketplace is hand-authored in the root `apm.yml` `marketplace:` block and generated to JSON via `apm pack`. After changing a package manifest or the marketplace block, regenerate artifacts and validate:

```bash
apm run build-artifacts                                   # release-please config, indexes, README tables, apm pack
apm compile --validate --local-only --target codex,claude # validate primitives without writing
```

The README inventory tables are regenerated as part of `build-artifacts`. CI runs `apm run check-readme-tables` and `apm run check-release-please` to fail the build if the committed tables or release-please config are stale.

**Consuming this repo's own tooling.** A project that depends on this marketplace wires the install flow as `apm run setup-agentic-tools` (see [`templates/project-apm.yml`](templates/project-apm.yml)): `apm install` -> `apm compile` -> `patch-agentic-tools` -> `audit-agentic-tools`. The two finalizers are this repo's `.apm/scripts/`:

- `patch-runtime-agents.py` -- maps each agent's cross-tool `x-agentic` block to native Codex `.toml` and Claude `.md` fields that APM's generic conversion drops (model, reasoning-effort, sandbox, approval/permission). Required because agents are functional but un-tuned without it.
- `audit-agentic-assets.py` -- reports agent/skill runtime parity (source vs `.claude`/`.codex`) and flags agents missing `x-agentic` fields. Complements `apm audit` (which only scans hidden Unicode and lockfile drift).

License: Apache-2.0 (see [`LICENSE`](LICENSE)). Bundles that only aggregate third-party MIT-licensed packages retain their upstream MIT license, declared per package in `apm.yml`.
