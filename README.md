# srobroek/agentic-packages

Shared agentic tooling for AI coding assistants -- installable through [APM](https://microsoft.github.io/apm/), the Agent Package Manager.

This repository is an **APM marketplace**: a curated catalog of agents, skills, hooks, steering instructions, MCP server definitions, and a SpecKit-driven orchestration system. Everything is authored once under `.apm/` and compiled to whatever runtime you use -- Claude Code, Codex, Copilot, Cursor, Gemini, OpenCode, or Windsurf.

- **33 bundles** -- opinionated dependency-aggregator packages grouping skills, agents, and steering for a domain (frontend, security, a language toolchain, SpecKit, ...)
- **25 skills** -- reusable workflows, each its own package (catchup, code-review, research, verify, ...)
- **4 agents** -- sub-agents with model/tool/permission profiles (coder, pr-reviewer, adversarial-challenger, external-repo-worker)
- **16 steering packages** -- opt-in opinionated conventions (per domain and per language)
- **6 MCP server packages** -- pre-wired Model Context Protocol servers (context7, playwright, repomix, ...)

---

## Table of contents

- [Quick start](#quick-start)
- [Installing APM](#installing-apm)
- [Adding the marketplace](#adding-the-marketplace)
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
apm install core@srobroek-agentic --target claude,codex,agent-skills

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

Pick deployment targets explicitly with `--target` (otherwise APM auto-detects from `.claude/`, `.codex/`, etc.):

```bash
apm install core@srobroek-agentic --target claude,codex,agent-skills
```

After installing, run the **setup order** so steering lands in the right place and runtime agents are patched:

```bash
apm install --target claude,codex,agent-skills
apm compile --target codex,claude --no-constitution
apm run fix-context-links
apm run patch-agentic-tools
apm run audit-agentic-tools
```

A ready-made `apm.yml` for consuming projects lives in [`templates/project-apm.yml`](templates/project-apm.yml) -- it wires these steps as `apm run setup-agentic-tools`.

> **Why the extra steps?** `apm install` deploys primitives (skills, agents, hooks, MCP); `apm compile` turns instructions into the root context files each runtime reads. `fix-context-links` repairs the relative `.context.md` links in the generated `AGENTS.md`/`CLAUDE.md` to point at the installed package location under `apm_modules/`. `patch-agentic-tools` restores Codex/Claude-specific model, reasoning-effort, sandbox, and permission fields that APM's generic conversion doesn't preserve.

---

## How bundles work

A **bundle** is a hand-authored APM package whose job is to install a coherent set of primitives. Each bundle is its own directory under [`packages/`](packages/) with an `apm.yml` manifest. The manifest is a dependency aggregator: a `dependencies.apm:` list that references the member packages (skills, agents, steering) by their marketplace shortname, plus any external third-party packages (Matt Pocock skills, Hobson agents, ...).

A bundle `apm.yml` typically lists:

- member skill/agent/steering packages by marketplace shortname (for example `code-review@srobroek-agentic`)
- external dependencies (third-party APM packages) by their source
- the bundle's own `name`, `version`, and `description`

**Composition over duplication.** Skills and agents live as individual packages under `packages/<name>/`. A bundle does not copy their content -- it depends on them, so a change to a member package propagates to every bundle that references it. Bundles can also depend on other bundles, so `core` aggregates project-lifecycle, code-intelligence, and agentic-maintenance, and language bundles layer a single quality skill plus language steering on top.

Each package (skill, agent, and bundle) carries its own `apm.yml` and is versioned independently via release-please. The marketplace itself is hand-authored in the root [`apm.yml`](apm.yml) `marketplace:` block using local-path sources, and generated to `.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json` by `apm pack`.

To regenerate artifacts after editing a manifest:

```bash
apm pack                # regenerate the marketplace JSON only
apm run build-artifacts # release-please config + indexes/*.json + README tables + apm pack
```

---

## Compiling for different targets

`apm compile` reads your instructions (local `.apm/` + installed `apm_modules/`) and writes the root context file each runtime loads at startup. One source, many targets:

```bash
apm compile --target codex            # AGENTS.md only
apm compile --target claude           # CLAUDE.md only
apm compile --target codex,claude     # both (default for this project)
apm compile --all                     # every canonical target
apm run compile-claude                # convenience script for CLAUDE.md only
```

`compilation.strategy: distributed` (set in `apm.yml`) places scoped instructions next to the code they apply to via `applyTo:` globs; `single-file` collapses everything into one root file.

`--no-constitution` excludes any SpecKit `memory/constitution.md` block -- both the `<!-- SPEC-KIT CONSTITUTION -->` markers and the constitution body -- from a clean compile. (An existing block already on disk is preserved, not regenerated.)

---

## SpecKit orchestration

The `speckit` bundle installs a complete spec-driven development workflow: six SpecKit sub-agents, a `speckit-bugfix` skill, steering instructions, and a **hook-enforced orchestration DAG**. It turns ad-hoc "vibe coding" into a gated pipeline:

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

The `speckit` bundle in this repo supplies the orchestration layer (agents, DAG, hooks). The `/speckit.*` slash commands themselves come from the upstream [`github/spec-kit`](https://github.com/github/spec-kit) `specify` CLI plus a set of community extensions. The fastest path is the global **`project-setup`** skill, which wires both together.

**Recommended -- via `project-setup`:**

```text
Use project-setup with SpecKit enabled
```

The skill runs an interactive interview, installs `core@srobroek-agentic` plus the `speckit` bundle, then bootstraps SpecKit by:

1. `specify init --here --integration codex --script sh` -- scaffolds `.specify/` (constitution, feature dirs, workflow state).
2. Adding the community extension catalog: `https://raw.githubusercontent.com/github/spec-kit/main/extensions/catalog.community.json`
3. Installing and enabling the **required extension set** (26): `archive`, `brownfield`, `bugfix`, `checkpoint`, `cleanup`, `conduct`, `critique`, `diagram`, `doctor`, `fix-findings`, `fleet`, `github-issues`, `iterate`, `onboard`, `optimize`, `qa`, `reconcile`, `refine`, `retro`, `review`, `security-review`, `status`, `tinyspec`, `verify`, `verify-tasks`, `worktree`.
4. Installing the workflow definitions: `speckit`, `speckit-quality`, `speckit-full`.

**Manual setup** -- if you're not using `project-setup`:

```bash
# 1. Install the specify CLI (see github/spec-kit for current install)
uv tool install specify-cli

# 2. Scaffold .specify/ in your project
specify init --here --integration codex --script sh

# 3. Register the community extension catalog
specify extension catalog add --name community --install-allowed \
  https://raw.githubusercontent.com/github/spec-kit/main/extensions/catalog.community.json

# 4. Add the required extensions (repeat per id from the list above)
specify extension add critique && specify extension enable critique
# ... archive, bugfix, security-review, verify, verify-tasks, worktree, etc.

# 5. Install this repo's speckit orchestration bundle
apm install speckit@srobroek-agentic --target claude,codex,agent-skills
apm compile --target codex,claude --no-constitution
```

The orchestration hooks key off `.specify/feature.json` (or the git branch) to resolve the active feature, so a scaffolded `.specify/` directory is a prerequisite for the DAG's precondition checks to work.

---

## The how and why of SpecKit orchestration

**Why.** LLM coding agents skip steps. Left to their own judgment they call a security review "overkill," mark tasks complete that were never implemented, and let specs drift from code. The orchestration system removes that discretion: every step is mandatory by default, the ordering is fixed, and a hook layer can hard-block out-of-order or precondition-violating moves before the model acts.

**How -- three layers.**

1. **Declarative workflow** -- [`packages/speckit/.apm/instructions/50-speckit-workflow.instructions.md`](packages/speckit/.apm/instructions/50-speckit-workflow.instructions.md) defines the full Phase 1 (spec, human-gated) -> Phase 2 (implementation) -> Phase 3 (post-implementation QA) DAG and the standing rules: *all steps mandatory, always invoke via the Skill tool, always get approval between phases.*

2. **The DAG node store** -- [`packages/speckit/.apm/skills/speckit-dag/`](packages/speckit/.apm/skills/speckit-dag/) holds a `nodes/<step>.pre.md` and `nodes/<step>.post.md` pair for each step. `pre.md` declares legitimate predecessors and **preconditions**; `post.md` declares the default next step and **postconditions**. This is the graph -- edges live in these files, not in code.

3. **The hook dispatcher** -- [`dispatcher.sh`](packages/speckit/.apm/skills/speckit-dag/scripts/dispatcher.sh) runs on every `/speckit.*` invocation, wired through [`speckit-claude-hooks.json`](packages/speckit/.apm/hooks/speckit-claude-hooks.json) and [`speckit-codex-hooks.json`](packages/speckit/.apm/hooks/speckit-codex-hooks.json):
   - **Pre phase** evaluates hard-block directives in the node file and **denies** the call if violated:
     - `HARD-MISSING: specs/<feat>/spec.md` -- blocks if a required artifact is absent (e.g. `plan` before `spec`)
     - `HARD-EXISTS: <path>` -- blocks if an artifact that shouldn't exist yet does (routes to a refine path)
     - `HARD-DEPRECATED:` -- blocks unconditionally
   - It resolves the `<feat>` placeholder from `$SPECIFY_FEATURE_DIRECTORY`, then `.specify/feature.json`, then the git branch -- so preconditions are feature-aware.
   - Otherwise it injects the node body as `additionalContext` (soft steering -- "you came from X, go to Y next").

**Hook events.** Claude wires `UserPromptExpansion`, `PreToolUse:Skill`, `PostToolUse:Skill`; Codex wires `UserPromptSubmit`, `PreToolUse`, `PostToolUse`. Pre fires before the skill runs (can deny); post fires after (only steers).

**Mandatory-step enforcement.** Node `.pre.md` files phrase skips as *"only if the user explicitly skips X"* rather than *"acceptable if X skipped"* -- combined with the standing rule that steps are mandatory, the agent suggests the next step every time and only omits one on explicit user request. The May-2026 DAG reorder moved `critique` and `security-review` to run in parallel right after `tasks`, and made the post-implementation QA steps (verify, verify-tasks, code-review, security-review) mandatory rather than optional.

**The payoff.** Security review and phantom-completion detection can't be silently dropped; specs can't be hand-edited around the Skill tool; and the same gated flow compiles to both Claude and Codex from one definition.

---

## Inventory

The tables below are generated from [`indexes/*.json`](indexes/) by [`build-readme-tables.py`](.apm/scripts/build-readme-tables.py) and kept current by CI -- do not edit them by hand.

### Bundles

<!-- BEGIN:bundles -->
| Bundle | Description |
| --- | --- |
| `agentic-maintenance` | Maintain your agentic assets: audit and optimize steering, look up prompts, write new skills, with the coder and PR reviewer agents. Includes Hobson documentation-standards and plugin-eval for evaluating external packages. |
| `code-intelligence` | Codebase understanding toolkit: graph/index/search skills (codebase-index, codebase-memory, explore, prompt-lookup), research and web-fetch, the PR reviewer agent, project-structure steering, and Hobson documentation/architecture plugins. |
| `core` | Meta-bundle for the shared project baseline. Aggregates the project-lifecycle, code-intelligence, and agentic-maintenance bundles, plus grill/diagnose workflows and context/orchestration plugins. Install this to get a sensible default toolkit for any repo. |
| `data-ai` | Data and AI toolkit: data steering plus Hobson LLM application, data engineering, MLOps, database design, migrations, and cloud optimization plugins. |
| `debugging` | Local debugging escalation: the unstuck skill and the adversarial-challenger agent for when you are blocked, plus Matt's diagnose workflow. For production/distributed incident debugging, see the incident-response bundle. |
| `developer-tools` | Bundle: Hobson developer tooling bundle for everyday development, debugging, review, PR, and documentation generation workflows. Contains: packages developer-essentials, debugging-toolkit, comprehensive-review, git-pr-workflows, documentation-generation. |
| `diagrams` | Diagram generation bundle for editable draw.io diagrams, visual Excalidraw diagrams, and D2 architecture or flow diagrams. |
| `docs-architecture` | Bundle: Documentation and architecture bundle with Hobson documentation, HADS, OpenAPI, Mermaid, and C4 workflows. Contains: packages documentation-standards, code-documentation, documentation-generation, c4-architecture. |
| `frontend` | Frontend development and design toolkit: the Playwright browser skill, frontend steering, and external design/build skills (Impeccable, Interface Design, Stitch) plus Hobson frontend, UI, accessibility, and landing-page plugins. |
| `governance` | Bundle: Governance bundle with Hobson MCP protection, signed audit trails, and review policy workflows. Contains: packages protect-mcp, signed-audit-trails, review-agent-governance, block-no-verify. |
| `incident-response` | Incident response and production debugging: Hobson error-debugging, distributed-debugging, incident-response, error-diagnostics, and debugging-toolkit plugins for diagnosing failures in running systems. |
| `infrastructure` | Infrastructure and operations toolkit: infrastructure steering plus Hobson cloud, Kubernetes, CI/CD, deployment, deployment-validation, and observability plugins. |
| `language-arm-cortex` | ARM Cortex-M firmware toolkit: Hobson's embedded arm-cortex-microcontrollers specialists. |
| `language-dotnet` | .NET development toolkit: Hobson's C# and ASP.NET dotnet-contribution specialists. |
| `language-functional` | Functional programming toolkit: Hobson's Elixir and Haskell functional-programming specialists. |
| `language-go` | Go toolkit: the go-quality skill, opinionated Go steering, and Hobson's systems-programming specialists. |
| `language-julia` | Julia development toolkit: Hobson's scientific-computing julia-development specialists. |
| `language-jvm` | JVM language toolkit: Hobson's Java, Scala, and enterprise jvm-languages specialists. |
| `language-python` | Python toolkit: the python-quality skill, opinionated Python steering, and Hobson's python-development specialists. |
| `language-rust` | Rust toolkit: the rust-quality skill, opinionated Rust steering, and Hobson's systems-programming specialists. |
| `language-shell` | Shell scripting toolkit: Hobson's Bash and POSIX shell-scripting specialists. |
| `language-terraform` | Terraform and HCL toolkit: opinionated Terraform steering plus Hobson's deployment-strategies specialists. No dedicated quality skill yet. |
| `language-typescript` | TypeScript and JavaScript toolkit: the typescript-quality skill, opinionated TS/JS steering, and Hobson's javascript-typescript specialists. |
| `language-web-scripting` | PHP and Ruby web scripting toolkit: Hobson's web-scripting specialists. |
| `matt-skills` | Bundle of Matt Pocock's engineering and productivity skills: diagnose, grill-me, grill-with-docs, tdd, to-prd, to-issues, triage, zoom-out, improve-codebase-architecture, caveman, and setup. |
| `planning-product` | Planning and product toolkit: the debate, eli5, research, and web-fetch skills plus Matt's PRD, issue-writing, TDD, triage, zoom-out, and architecture-improvement workflows. |
| `presentation` | Presentation bundle for general decks, Marp slides, and PowerPoint template workflows. |
| `project-lifecycle` | Day-to-day project lifecycle workflows: resume work after interruption (catchup), write handovers, run verification, and commit/push via local merge, PR, or quick commit. Bundles the matching skills and the PR reviewer agent. |
| `resume` | Resume bundle for focused resume tailoring and broad career-support workflows. |
| `review` | Code review and verification toolkit: the code-review and verify skills, the PR reviewer agent, and Hobson comprehensive-review, performance-testing-review, unit-testing, and tdd-workflows plugins. Language-specific quality checks live in the language-<lang> bundles. |
| `security` | Security toolkit: Hobson security-scanning, security-compliance, backend-api-security, frontend-mobile-security, and reverse-engineering plugins for vulnerability analysis, compliance, and hardening. |
| `speckit` | SpecKit mechanism: the six SpecKit agents and the bugfix and setup skills. Opt into the opinionated layers separately: steering-speckit (the mandatory-gated workflow) and speckit-dag-hooks (the DAG dispatcher + enforcement hooks). |
| `speckit-dag-hooks` | Opt-in enforcement hooks for the SpecKit DAG: hard-block out-of-order or precondition-violating /speckit.* commands via the speckit-dag dispatcher. Opinionated mandatory-gating -- requires the speckit package (which ships the dispatcher) to be installed. |
<!-- END:bundles -->

### MCP server packages

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

<!-- BEGIN:agents -->
| Agent | Description |
| --- | --- |
| `agent-adversarial-challenger` | Read-only adversarial debugger for the unstuck workflow. Investigates independently, challenges assumptions behind failed fixes, and returns evidence-backed alternative causes without editing files. |
| `agent-coder` | Implementation subagent for bounded code changes, tests, and refactors within a defined scope. |
| `agent-external-repo-worker` | Subagent that works inside an external repository outside the caller project. Handles isolated clone or reuse, convention discovery, bounded edits, local verification, and delegated publish or PR work. |
| `agent-pr-reviewer` | Subagent that reviews pull requests for code quality, security, and best practices. |
<!-- END:agents -->

### Skills

<!-- BEGIN:skills -->
| Skill | Description |
| --- | --- |
| `catchup` | Resume interrupted project work by locating and following the best handover before doing fresh discovery. Use when starting in an existing repo/worktree, after context loss or /clear, when the user says catchup/continue/resume/handover, or when asked what changed or what is next. |
| `code-review` | Use for review requests. Prioritizes bugs, regressions, risks, and missing tests. |
| `codebase-index` | Use when the codebase graph is missing or stale. Rebuild the codebase-memory index first. |
| `codebase-memory` | Use for graph-aware codebase exploration, tracing, and reference lookup. |
| `commit-push-merge` | Publish and merge a branch by committing local changes when needed, pushing, and merging after inferring or confirming the target and method. Use when the user asks to commit, push, and merge or to direct-merge a branch. |
| `commit-push-pr` | Publish a branch by committing local changes when needed, pushing, and opening or updating a pull request. Use when the user explicitly asks to commit and push with a PR, open a PR, or publish the current branch for review. |
| `debate` | Use for deep tradeoff analysis on architectural decisions, technology choices, and feature proposals. Tests an idea from both sides before recommending a path. Agents may suggest this when the user faces a non-trivial decision. |
| `eli5` | Explains a topic at multiple depth levels. Use when a topic needs layered explanation, when the user is confused about a concept, or when the user says "explain X." Agents may suggest this when the user seems unfamiliar with a topic or asks "what is" / "how does" questions. |
| `explore` | Use for read-only codebase orientation, file discovery, and path tracing. |
| `go-quality` | Use to run Go format, lint, and test checks with the project toolchain. |
| `handover` | Save a self-contained recovery prompt for a later agent session in the shared handover store. Use when ending or pausing work, switching context, preserving unfinished implementation state, or when the user asks for a handover. |
| `hyperresearch` | Run the third-party HyperResearch deep research harness. Use when the user asks for deep research, adversarial source-backed research, long-form research reports, or HyperResearch specifically. |
| `optimize-steering` | Audit and optimize agent-facing markdown files (steering docs, skills, agent definitions) for token efficiency, structural compliance, and cross-model compatibility. Applies research-backed formatting conventions (R1-R7). Runs `steering-audit` first for drift/hook/lint detection. Use when asked to audit agent docs, optimize steering files, refactor SKILL.md, normalize agent instructions, reduce token waste, or fix agent compliance issues. To create a new skill from scratch, use `write-a-skill` instead. |
| `playwright` | Use when automating browser interactions through a Playwright MCP server. |
| `prompt-lookup` | Use when finding, comparing, or improving prompt templates and prompt-engineering patterns. |
| `python-quality` | Use to run Python format, lint, type-check, and test commands with the project toolchain. |
| `quick-commit` | Create a deliberate local git commit without pushing or opening a PR. Use when the user asks to commit local changes, make a checkpoint commit, or run a fast commit-only workflow. |
| `research` | Use when the user needs open-ended research requiring synthesis across multiple sources -- comparisons, technology evaluations, tradeoff analysis. NOT for single-repo "where is X" lookups (use explore), URL-specific fetches (use web-fetch), or speckit research workflows. |
| `rust-quality` | Use to run Rust format, lint, and test checks with the project toolchain. |
| `sniff` | Use for a stability, hardening, and cleanup audit across a codebase. |
| `typescript-quality` | Use to run TypeScript or JavaScript format, lint, type-check, and test commands. |
| `unstuck` | Escalate stalled debugging by challenging assumptions after the normal diagnosis loop has failed. Use when repeated fixes, same-file re-editing, flaky evidence, circular hypotheses, or going in circles suggest the agent is stuck; bundled diagnose owns first-pass debugging. |
| `verify` | Run and report a final local verification pass before handoff, commit, push, merge, or PR. Use when the user asks to verify, test everything, check readiness, or prove local changes are safe to hand off. |
| `web-fetch` | Retrieve current or URL-specific information from the web with source-aware tool routing. Use when the user asks to fetch, open, browse, cite, verify online, inspect a URL, or answer a question whose facts may have changed. |
| `write-a-skill` | Create or rewrite agent skills with precise triggers, progressive disclosure, references, scripts, and source-of-truth placement. Use when the user asks to create, write, repair, optimize, or package a skill for an APM package or marketplace. |
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
| `steering-audit` | Use to audit agent rules, hooks, skills, and guardrails for drift and cleanup. |
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

---

## Developing this repository

Every installable asset -- each skill, agent, MCP package, and bundle -- is a hand-authored package directory under [`packages/`](packages/) with its own `apm.yml`. Edit packages directly; **do not edit generated runtime directories (`.claude/`, `.codex/`, `.agents/`, compiled `AGENTS.md`/`CLAUDE.md`) by hand.**

Each package (skill, agent, bundle, MCP) has its own `apm.yml` and is versioned independently via release-please. The marketplace is hand-authored in the root `apm.yml` `marketplace:` block and generated to JSON via `apm pack`. After changing a package manifest or the marketplace block, regenerate artifacts and validate:

```bash
apm run build-artifacts                                   # release-please config, indexes, README tables, apm pack
apm compile --validate --local-only --target codex,claude # validate primitives without writing
```

The README inventory tables are regenerated as part of `build-artifacts`. CI runs `apm run check-readme-tables` to fail the build if the committed tables are stale.

License: MIT.
