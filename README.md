# srobroek/agentic-packages

Shared agentic tooling for AI coding assistants -- installable through [APM](https://microsoft.github.io/apm/), the Agent Package Manager.

This repository is an **APM marketplace**: a curated catalog of agents, skills, hooks, steering instructions, MCP server definitions, and a SpecKit-driven orchestration system. Everything is authored once under `.apm/` and compiled to whatever runtime you use -- Claude Code, Codex, Copilot, Cursor, Gemini, OpenCode, or Windsurf.

- **38 bundles** -- opinionated groupings of skills, agents, and steering for a domain (frontend, security, a language toolchain, SpecKit, ...)
- **26 first-party skills** -- reusable workflows (catchup, code-review, research, verify, ...)
- **10 agents** -- sub-agents with model/tool/permission profiles (coder, pr-reviewer, the SpecKit agents, ...)
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

A **bundle** is an APM package whose job is to install a coherent set of primitives. Bundles are not hand-written -- they are generated from declarative `Bundle(...)` definitions in [`.apm/scripts/build-packages.py`](.apm/scripts/build-packages.py) and materialized under [`packages/`](packages/).

Each bundle definition declares:

- `skills` -- first-party skills from `.apm/skills/`
- `agents` -- agent definitions from `.apm/agents/`
- `instructions` / `contexts` -- steering docs
- `scripts` -- maintenance scripts copied alongside
- `dependencies` -- third-party packages (Matt Pocock skills, Hobson agents, ...)

Shared sets are defined once and reused: `CORE_SKILLS` (17 skills), `CORE_AGENTS` (4 agents), and `SPECKIT_AGENTS` (6 agents) are referenced by multiple bundles, so a change to the baseline propagates everywhere on the next build.

**Composition over duplication.** Bundles can pull in other bundles' content by sharing those constants, so `core` aggregates project-lifecycle, code-intelligence, and agentic-maintenance, and language bundles layer a single quality skill plus language steering on top.

To regenerate every bundle after editing a definition:

```bash
apm run build-packages       # materialize packages/
apm run build-marketplace    # regenerate marketplace.json
apm run build-indexes        # regenerate indexes/*.json
# or all of the above plus README tables:
apm run build-artifacts
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
| `agentic-maintenance` | Bundle: Agentic asset maintenance bundle with steering audit, optimization, prompt lookup, first-party skill writing, and Hobson plugin/documentation evaluation. Contains: skills optimize-steering, prompt-lookup, steering-audit, write-a-skill; agents coder, pr-reviewer; steering; packages documentation-standards, plugin-eval. |
| `code-intelligence` | Bundle: Codebase understanding bundle with graph/index/search skills, PR review, and Hobson documentation/architecture agents. Contains: skills codebase-index, codebase-memory, explore, prompt-lookup, research, web-fetch; agents pr-reviewer; steering; packages code-documentation, documentation-generation, c4-architecture. |
| `core` | Bundle: Deterministic shared project baseline with core agents, code intelligence, project lifecycle, agentic maintenance, first-party skill writing, and Matt grill/diagnose workflows. Contains: skills catchup, handover, code-review, codebase-index, codebase-memory, commit-push-merge, commit-push-pr, explore, optimize-steering, prompt-lookup, quick-commit, research, steering-audit, unstuck, verify, web-fetch, write-a-skill; agents adversarial-challenger, coder, external-repo-worker, pr-reviewer; steering; scripts prune-stale-local-packages, fix-context-links, patch-runtime-agents, audit-agentic-assets; packages diagnose, grill-me, grill-with-docs, context-management, agent-orchestration. |
| `data-ai` | Bundle: Data and AI bundle with Hobson LLM application, data engineering, MLOps, and database optimization workflows. Contains: steering; packages llm-application-dev, data-engineering, machine-learning-ops, database-design, database-migrations, database-cloud-optimization. |
| `debugging` | Bundle: Debugging escalation bundle with diagnose, unstuck, adversarial challenge, and Hobson debugging agents. Contains: skills unstuck; agents adversarial-challenger; packages diagnose, debugging-toolkit, error-debugging, error-diagnostics, distributed-debugging, incident-response. |
| `design` | _(meta-bundle)_ |
| `developer-tools` | Bundle: Hobson developer tooling bundle for everyday development, debugging, review, PR, and documentation generation workflows. Contains: packages developer-essentials, debugging-toolkit, comprehensive-review, git-pr-workflows, documentation-generation. |
| `diagrams` | Diagram generation bundle for editable draw.io diagrams, visual Excalidraw diagrams, and D2 architecture or flow diagrams. |
| `docs-architecture` | Bundle: Documentation and architecture bundle with Hobson documentation, HADS, OpenAPI, Mermaid, and C4 workflows. Contains: packages documentation-standards, code-documentation, documentation-generation, c4-architecture. |
| `finance` | _(meta-bundle)_ |
| `frontend` | Bundle: Frontend development and design bundle with Impeccable, Interface Design, Stitch skills, Playwright browser skill, and Hobson frontend/UI/accessibility agents. Contains: skills playwright; steering; packages impeccable, interface-design, stitch-design, frontend-mobile-development, ui-design, accessibility-compliance, brand-landingpage. |
| `game-development` | _(meta-bundle)_ |
| `governance` | Bundle: Governance bundle with Hobson MCP protection, signed audit trails, and review policy workflows. Contains: packages protect-mcp, signed-audit-trails, review-agent-governance, block-no-verify. |
| `hyperresearch` | Run the third-party HyperResearch deep research harness. Use when the user asks for deep research, adversarial source-backed research, long-form research reports, or HyperResearch specifically. |
| `infrastructure` | Bundle: Infrastructure bundle with Hobson cloud, Kubernetes, CI/CD, observability, and deployment workflows. Contains: steering; packages cloud-infrastructure, kubernetes-operations, cicd-automation, deployment-strategies, deployment-validation, observability-monitoring. |
| `language-arm-cortex` | Bundle: ARM Cortex-M firmware bundle with Hobson embedded specialists. Contains: packages arm-cortex-microcontrollers. |
| `language-dotnet` | Bundle: .NET development bundle with Hobson C# and ASP.NET specialists. Contains: packages dotnet-contribution. |
| `language-functional` | Bundle: Functional programming bundle with Hobson Elixir and Haskell specialists. Contains: packages functional-programming. |
| `language-go` | Bundle: Go quality bundle with language steering and Hobson systems specialists. Contains: skills go-quality; steering; packages systems-programming. |
| `language-julia` | Bundle: Julia development bundle with Hobson scientific computing specialists. Contains: packages julia-development. |
| `language-jvm` | Bundle: JVM language bundle with Hobson Java, Scala, and enterprise specialists. Contains: packages jvm-languages. |
| `language-python` | Bundle: Python quality bundle with language steering and Hobson specialists. Contains: skills python-quality; steering; packages python-development. |
| `language-rust` | Bundle: Rust quality bundle with language steering and Hobson systems specialists. Contains: skills rust-quality; steering; packages systems-programming. |
| `language-shell` | Bundle: Shell scripting bundle with Hobson Bash and POSIX specialists. Contains: packages shell-scripting. |
| `language-terraform` | Bundle: Terraform steering bundle with Hobson deployment and Terraform specialists. Contains: steering; packages deployment-strategies. |
| `language-typescript` | Bundle: TypeScript and JavaScript quality bundle with language steering and Hobson specialists. Contains: skills typescript-quality; steering; packages javascript-typescript. |
| `language-web-scripting` | Bundle: PHP and Ruby web scripting bundle with Hobson specialists. Contains: packages web-scripting. |
| `marketing` | _(meta-bundle)_ |
| `planning-product` | Bundle: Planning and product bundle with first-party debate/research plus Matt PRD, issue, TDD, triage, and architecture workflows. Contains: skills debate, eli5, research, web-fetch; packages to-prd, to-issues, tdd, triage, zoom-out, improve-codebase-architecture. |
| `presentation` | Presentation bundle for general decks, Marp slides, and PowerPoint template workflows. |
| `project-lifecycle` | Bundle: Project lifecycle bundle for catchup, handover, local commits, PRs, merges, and verification. Contains: skills catchup, handover, commit-push-merge, commit-push-pr, quick-commit, verify; agents pr-reviewer. |
| `project-management` | _(meta-bundle)_ |
| `quality` | Bundle: Cross-language quality bundle for reviews, verification, language checks, and Hobson test/review workflows. Contains: skills code-review, go-quality, python-quality, rust-quality, typescript-quality, verify; agents pr-reviewer; steering; packages comprehensive-review, performance-testing-review, unit-testing, tdd-workflows. |
| `resume` | Resume bundle for focused resume tailoring and broad career-support workflows. |
| `security` | Bundle: Security bundle with Hobson scanning, compliance, API security, frontend security, and reverse-engineering workflows. Contains: steering; packages security-scanning, security-compliance, backend-api-security, frontend-mobile-security, reverse-engineering. |
| `speckit` | Bundle: SpecKit workflow bundle with per-command DAG hook dispatcher, SpecKit agents, bugfix skill, and docs/spec steering. Contains: hook dispatcher + ~150 per-command node markdowns shipping to Claude (.claude/settings.json) and Codex (.codex/hooks.json); skill speckit-bugfix; agents speckit-implement-task, speckit-research, speckit-sync, speckit-sync-conflicts, speckit-verify, speckit-verify-tasks; steering. |
| `work-tools` | Personal work workflow bundle for Salesforce activity logging, Excel activity tracking, and read-only work context collection. |
| `worldbuilding` | _(meta-bundle)_ |
<!-- END:bundles -->

### MCP server packages

<!-- BEGIN:mcp -->
| MCP Package | Description |
| --- | --- |
| `mcp-codebase-memory` | MCP package: Codebase Memory MCP server package for graph-aware project orientation. Contains: MCP servers codebase-memory-mcp. |
| `mcp-context7` | MCP package: Context7 MCP server package for current library and framework documentation. Contains: MCP servers context7. |
| `mcp-package-version` | MCP package: Package Version MCP server package for dependency version discovery. Contains: MCP servers mcp-package-version. |
| `mcp-playwright` | MCP package: Playwright MCP server package for browser automation and UI verification. Contains: MCP servers playwright. |
| `mcp-repomix` | MCP package: Repomix MCP server package for bulk repository snapshots. Contains: MCP servers repomix. |
| `mcp-serena` | MCP package: Serena MCP server package for semantic code tools. The launcher selects the Codex or Claude Code context from the parent harness and can be overridden with SERENA_MCP_CONTEXT. Contains: MCP servers serena. |
<!-- END:mcp -->

### Agents

<!-- BEGIN:agents -->
| Agent | Description |
| --- | --- |
| `adversarial-challenger` | Read-only adversarial debugger for the unstuck workflow. Use after normal diagnosis stalls and the parent can provide observable facts only; investigates independently, challenges assumptions behind failed fixes, and returns evidence-backed alternative causes without editing files. |
| `coder` | Implementation subagent for bounded code changes, tests, refactors, |
| `external-repo-worker` | Works in an external repository outside the caller project. Use when the parent names a repo URL or org/name and needs isolated clone/reuse, repo-local convention discovery, bounded edits, local verification, or explicitly delegated publish/PR work without nesting another git repo inside the current project. |
| `pr-reviewer` | Reviews pull requests for code quality, security, and best practices |
| `speckit-implement-task` | Implements non-code or tightly scoped tasks from a SpecKit tasks.md, or scopes substantial code work for a parent-delegated coder. Use only inside a SpecKit implementation workflow when the parent provides task IDs, spec context, and worktree scope. |
| `speckit-research` | Researches current primary-source library or API documentation for a SpecKit decision and returns concise findings. Use only inside a SpecKit workflow when the parent provides a library, API, or implementation question tied to a spec or task. |
| `speckit-sync` | Detects drift between active SpecKit artifacts and implementation, including stale specs, missing code, and unspecced covered-scope behavior. Use for SpecKit sync/drift audits, not final FR/SC acceptance verification. |
| `speckit-sync-conflicts` | Detects contradictions between active SpecKit specs or between specs and shared contracts/interfaces. Use for inter-spec conflict audits when scopes overlap, supersession is unclear, or shared API/data assumptions may disagree. |
| `speckit-verify` | Validates implemented code against a target SpecKit spec's FR/SC requirements and acceptance intent. Use for final or checkpoint SpecKit adherence verification, not broad drift discovery or task checkbox audits. |
| `speckit-verify-tasks` | Detects phantom SpecKit completions by checking completed tasks or closed spec issues against real implementation evidence in fresh context. Use after task completion claims when confirmation bias must be avoided. |
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
| `optimize-steering` | Audit and optimize agent-facing markdown files (steering docs, skills, agent definitions) for token efficiency, structural compliance, and cross-model compatibility. Applies research-backed formatting conventions (R1-R7). Runs `steering-audit` first for drift/hook/lint detection. Use when asked to audit agent docs, optimize steering files, refactor SKILL.md, normalize agent instructions, reduce token waste, or fix agent compliance issues. To create a new skill from scratch, use `write-a-skill` instead. |
| `playwright` | Use when automating browser interactions through a Playwright MCP server. |
| `prompt-lookup` | Use when finding, comparing, or improving prompt templates and prompt-engineering patterns. |
| `python-quality` | Use to run Python format, lint, type-check, and test commands with the project toolchain. |
| `quick-commit` | Create a deliberate local git commit without pushing or opening a PR. Use when the user asks to commit local changes, make a checkpoint commit, or run a fast commit-only workflow. |
| `research` | Use when the user needs open-ended research requiring synthesis across multiple sources -- comparisons, technology evaluations, tradeoff analysis. NOT for single-repo "where is X" lookups (use explore), URL-specific fetches (use web-fetch), or speckit research workflows. |
| `rust-quality` | Use to run Rust format, lint, and test checks with the project toolchain. |
| `sniff` | Use for a stability, hardening, and cleanup audit across a codebase. |
| `speckit-bugfix` | Use when fixing bugs in a SpecKit repo. Scales from quick fixes to full bug workflows. |
| `steering-audit` | Use to audit agent rules, hooks, skills, and guardrails for drift and cleanup. |
| `typescript-quality` | Use to run TypeScript or JavaScript format, lint, type-check, and test commands. |
| `unstuck` | Escalate stalled debugging by challenging assumptions after the normal diagnosis loop has failed. Use when repeated fixes, same-file re-editing, flaky evidence, circular hypotheses, or going in circles suggest the agent is stuck; bundled diagnose owns first-pass debugging. |
| `verify` | Run and report a final local verification pass before handoff, commit, push, merge, or PR. Use when the user asks to verify, test everything, check readiness, or prove local changes are safe to hand off. |
| `web-fetch` | Retrieve current or URL-specific information from the web with source-aware tool routing. Use when the user asks to fetch, open, browse, cite, verify online, inspect a URL, or answer a question whose facts may have changed. |
| `write-a-skill` | Create or rewrite agent skills with precise triggers, progressive disclosure, references, scripts, and source-of-truth placement. Use when the user asks to create, write, repair, optimize, or package a skill for bootstrap/global use or an APM marketplace. |
<!-- END:skills -->

---

## Developing this repository

Shared assets are authored under [`.apm/`](.apm/). Installable bundles are generated into [`packages/`](packages/); **do not edit generated runtime directories or `packages/` by hand.**

After changing agents, skills, hooks, instructions, contexts, MCP definitions, or bundle definitions, regenerate artifacts and validate:

```bash
apm run build-artifacts                                   # packages, marketplace, indexes, README tables
apm compile --validate --local-only --target codex,claude # validate primitives without writing
```

The README inventory tables are regenerated as part of `build-artifacts`. CI runs `apm run check-readme-tables` to fail the build if the committed tables are stale.

License: MIT.
