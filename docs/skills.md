# Skills

Reusable workflows, each its own package, deployed to `.agents/skills/` (cross-client). A skill is loaded on demand when its trigger matches; install only the workflows you want.

Install a single skill with `apm install <name>@srobroek-agentic`, or get a curated set via a [bundle](bundles.md).

<!-- BEGIN:skills -->
| Skill | Description |
| --- | --- |
| `agent-management` | Manage APM-backed project agents, skills, hooks, steering, bundles, and package dependencies. Use when a repo already has or is about to get apm.yml and the task is to add, update, remove, install, compile, patch, or audit agentic assets. |
| `audit-steering` | Audit agent rules, hooks, skills, and guardrails for drift, duplication, stale files, and token waste. |
| `brownfield-project` | Retrofit an existing repository into APM-managed agentic tooling without broad scaffolding. Use when onboarding, ingesting, or repairing a brownfield repo, especially when the agent must first discover project purpose, requirements, and workflow needs interactively. |
| `catchup` | Resume interrupted project work by locating and following the best handover before doing fresh discovery, after context loss, /clear, or a continue/resume request. |
| `chezmoi-editor` | Edit chezmoi-managed dotfiles from their authoritative source files. Use when changing dotfiles, global agent/tool config, templates, private files, symlinked config, or any live target that may be managed by chezmoi. |
| `codebase-memory` | Structured graph queries against the indexed code graph: trace callers/callees, find references, map architecture. Requires the codebase-memory-mcp server; for lightweight orientation, use explore. |
| `debate` | Deep tradeoff analysis for architectural decisions, technology choices, and feature proposals. Tests an idea from both sides before recommending a path. |
| `dep-audit` | Scan the project's lockfiles and manifests for known-vulnerable dependencies using the ecosystem's native scanners (npm/pnpm audit, pip-audit, cargo audit, govulncheck, osv-scanner) and report CVEs grouped by severity. Never auto-fixes. |
| `dep-update` | Research each dependency's current latest version against installed lockfile pins, classify patch/minor/major bumps by safety, surface CVEs via native scanners, and produce a severity-grouped cited upgrade plan. Applies only patch and minor bumps interactively — one at a time behind a per-bump confirm; major bumps are advisory-only and never applied. Reads .project-setup/ answers.toml opportunistically; never writes it. |
| `eli5` | Explain a topic at five depth levels, from metaphor to frontier, for layered understanding of unfamiliar concepts. |
| `find-tools` | Discover and vet reusable skills, agents, MCP servers, connectors, and APM packages. Use when the user asks to find a capability, compare tools, fill a marketplace gap, evaluate an external package, or decide whether to adopt, wrap, fork, reject, or build. |
| `go-quality` | Run Go format, lint, and test checks with the project toolchain. |
| `goal-writer` | Turn a vague goal prompt into a structured, actionable goal -- with outcomes, concrete results, measurable KPIs, validation, and verifiable exit conditions -- saved as a context doc, then emit a self-sufficient /goal block that references the doc and tests done-ness via AND-joined exit conditions. |
| `handover` | Save a self-contained recovery prompt to the shared handover store when pausing work, switching context, preserving unfinished state, or handing off to another session. |
| `headroom` | Run coding agents through Headroom to compress context and cut token usage (~60-95% fewer) and to read token-savings stats. |
| `optimize-steering` | Audit and optimize agent-facing markdown (steering docs, skills, agent definitions) for token efficiency and cross-model compliance (rules R1-R7). |
| `orchestrate` | Orchestrate a fleet of subagents across complex, parallel, or long-running work while controlling cost by routing each role to the cheapest capable model. Ships the orchestration playbook plus bundled agents (workflow-coder, workflow-reviewer, workflow-advisor, integration-gatekeeper, ledger-scribe), a SubagentStart comms-protocol hook, and deterministic scripts (task DAG, forensic ledger, agent discovery, conflict probe). |
| `playwright` | Automate browser tasks through a Playwright MCP server: navigate, click, fill forms, and extract page data. |
| `project-hygiene` | Audit project-local APM agents, skills, hooks, MCP config, generated steering, and package fit. Use when asked for project hygiene, cleanup, installed agent or skill review, stale generated assets, duplicate tooling, or agentic package drift. |
| `python-quality` | Run Python format, lint, type-check, and test commands with the project toolchain. |
| `release-please` | Drive releases with googleapis/release-please. Use for any release, tagging, changelog, or version-bump work, and whenever the repo has a release-please-config.json / .release-please-manifest.json or a release-please workflow -- then following release-please is mandatory. Also use to set up release-please in a repo. Covers setup, the git/commit process, publishing, monorepo/manifest config, and diagnosing and recovering stuck or botched releases. Ships a warn-only cross-tool advisory hook; it never blocks. |
| `resume-session` | Resume a previous agent session in the current repository from its transcript, reading only the latest context incrementally instead of reloading the full history. Discovers prior Claude Code and Codex sessions, summarizes the leftoff state, confirms ambiguities, then continues the work. |
| `rust-quality` | Run Rust format, lint, and test checks with the project toolchain. |
| `secrets-scan` | Pre-commit secret scanning. A skill plus a PreToolUse hook that runs gitleaks or trufflehog (whichever is on PATH) over staged changes and blocks the commit when a secret is found, with an actionable message and a documented bypass. Warns and allows when no scanner is installed, so missing tooling never blocks. Cross-tool (Claude + Codex). |
| `session-review` | Audit the ending session for corrections, lessons, unresolved TODOs, and follow-up work, then recommend handoffs to `handover`, `audit-steering`, `optimize-steering`, or `write-a-skill`. Use when the user says wrap up, review this session, what did we learn, or before a handover. |
| `sniff` | Refactoring auditor. Detects code smells, tech debt, and non-idiomatic code across 21 languages and formats, maps each finding to refactoring.guru smells, patterns, and techniques, stress-tests every recommendation with a built-in adversarial pragmatism critic, and produces a prioritized refactoring plan (impact, value, cost, severity, backwards-compatibility). Drives each language toolchain's own linters and analyzers (opportunistic, never required) with a guided first-run installer. Advisory by default; applies low-risk refactors only on explicit approval behind a verification re-run. Standalone: no APM dependencies. |
| `speckit` | SpecKit mechanism: the six SpecKit agents and the bugfix and setup skills. Opt into the opinionated layers separately: steering-speckit (the mandatory-gated workflow) and speckit-dag-hooks (the DAG dispatcher + enforcement hooks). |
| `typescript-quality` | Run TypeScript or JavaScript format, lint, type-check, and test commands with the project toolchain. |
| `verify` | Run and report a final local verification pass (tests, types, build, lint) before handoff, commit, push, merge, or PR. |
| `web-fetch` | Retrieve current or URL-specific information from the web with source-aware tool routing for fetching, browsing, citing, and verifying online. |
| `whats-new` | Research what changed in a tool, CLI, library, framework, package, or dependency — or a technology, cloud service, hosted API, platform, or model family (AWS Bedrock, Anthropic/Claude, OpenAI, GCP, Azure, …) — between what is in use and the latest: breaking changes, deprecations, new features, and fixes. Resolves versions, repos, changelogs, release notes, commit logs, and service announcement feeds/APIs via machine endpoints instead of reading rendered pages, then summarizes into a fixed template. |
| `write-a-skill` | Create or rewrite agent skills with precise triggers, progressive disclosure, references, scripts, and source-of-truth placement. |
<!-- END:skills -->

---

See also: [bundles](bundles.md) · [agents](agents.md) · [steering](steering.md) · [hooks and MCP](hooks-and-mcp.md) · [external repos](external-repos.md) · [SpecKit](speckit.md)
