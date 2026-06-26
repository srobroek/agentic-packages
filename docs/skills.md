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
| `code-review` | Review a diff, change set, or PR for bugs, regressions, security risks, and missing tests, reporting findings by severity. |
| `codebase-index` | Rebuild the codebase-memory graph index when it is missing or stale. Requires the codebase-memory-mcp binary; without it, fall back to grep/glob exploration. |
| `codebase-memory` | Structured graph queries against the indexed code graph: trace callers/callees, find references, map architecture. Requires the codebase-memory-mcp server; for lightweight orientation, use explore. |
| `commit-push-merge` | Commit local changes when needed, push, and merge a branch after inferring or confirming the target and merge method. |
| `commit-push-pr` | Commit local changes when needed, push, and open or update a pull request for review. |
| `debate` | Deep tradeoff analysis for architectural decisions, technology choices, and feature proposals. Tests an idea from both sides before recommending a path. |
| `dep-audit` | Scan the project's lockfiles and manifests for known-vulnerable dependencies using the ecosystem's native scanners (npm/pnpm audit, pip-audit, cargo audit, govulncheck, osv-scanner) and report CVEs grouped by severity. Never auto-fixes. |
| `eli5` | Explain a topic at five depth levels, from metaphor to frontier, for layered understanding of unfamiliar concepts. |
| `explore` | Lightweight read-only codebase orientation: file discovery, path tracing, and "where is X" lookups. For structured graph queries, use codebase-memory. |
| `find-tools` | Discover and vet reusable skills, agents, MCP servers, connectors, and APM packages. Use when the user asks to find a capability, compare tools, fill a marketplace gap, evaluate an external package, or decide whether to adopt, wrap, fork, reject, or build. |
| `go-quality` | Run Go format, lint, and test checks with the project toolchain. |
| `handover` | Save a self-contained recovery prompt to the shared handover store when pausing work, switching context, preserving unfinished state, or handing off to another session. |
| `headroom` | Run coding agents through Headroom to compress context and cut token usage (~60-95% fewer) and to read token-savings stats. |
| `optimize-steering` | Audit and optimize agent-facing markdown (steering docs, skills, agent definitions) for token efficiency and cross-model compliance (rules R1-R7). |
| `playwright` | Automate browser tasks through a Playwright MCP server: navigate, click, fill forms, and extract page data. |
| `project-hygiene` | Audit project-local APM agents, skills, hooks, MCP config, generated steering, and package fit. Use when asked for project hygiene, cleanup, installed agent or skill review, stale generated assets, duplicate tooling, or agentic package drift. |
| `project-setup` | Bootstrap a new repo or add a package with explicit setup choices, APM package selection, tooling, and verification. Use when creating a project, adding a monorepo package, choosing bundles/skills/agents/MCP packages, or running setup scripts. |
| `python-quality` | Run Python format, lint, type-check, and test commands with the project toolchain. |
| `quick-commit` | Create a deliberate local git commit without pushing or opening a PR, for checkpoints and fast commit-only workflows. |
| `research` | Multi-source research synthesis for comparisons, technology evaluations, and tradeoff analysis. Not for single lookups (explore) or URL fetches (web-fetch). |
| `resume-session` | Resume a previous agent session in the current repository from its transcript, reading only the latest context incrementally instead of reloading the full history. Discovers prior Claude Code and Codex sessions, summarizes the leftoff state, confirms ambiguities, then continues the work. |
| `rust-quality` | Run Rust format, lint, and test checks with the project toolchain. |
| `secrets-scan` | Pre-commit secret scanning. A skill plus a PreToolUse hook that runs gitleaks or trufflehog (whichever is on PATH) over staged changes and blocks the commit when a secret is found, with an actionable message and a documented bypass. Warns and allows when no scanner is installed, so missing tooling never blocks. Cross-tool (Claude + Codex). |
| `session-review` | Audit the ending session for corrections, lessons, unresolved TODOs, and follow-up work, then recommend handoffs to `handover`, `audit-steering`, `optimize-steering`, or `write-a-skill`. Use when the user says wrap up, review this session, what did we learn, or before a handover. |
| `sniff` | Audit a codebase for stability, hardening, and cleanup opportunities, finding latent issues across error handling, structure, concurrency, and input boundaries. |
| `typescript-quality` | Run TypeScript or JavaScript format, lint, type-check, and test commands with the project toolchain. |
| `unstuck` | Escalate stalled debugging by challenging assumptions after the normal diagnosis loop has failed and the agent is going in circles. Ships an outcome-gated stuck detector (re-edit churn, failure streaks, flip-flops) with an escalating nudge/directive/edit-gate ladder on both runtimes. |
| `verify` | Run and report a final local verification pass (tests, types, build, lint) before handoff, commit, push, merge, or PR. |
| `web-fetch` | Retrieve current or URL-specific information from the web with source-aware tool routing for fetching, browsing, citing, and verifying online. |
| `whats-new` | Research what changed in a tool, CLI, library, framework, package, or dependency — or a technology, cloud service, hosted API, platform, or model family (AWS Bedrock, Anthropic/Claude, OpenAI, GCP, Azure, …) — between what is in use and the latest: breaking changes, deprecations, new features, and fixes. Resolves versions, repos, changelogs, release notes, commit logs, and service announcement feeds/APIs via machine endpoints instead of reading rendered pages, then summarizes into a fixed template. |
| `write-a-skill` | Create or rewrite agent skills with precise triggers, progressive disclosure, references, scripts, and source-of-truth placement. |
<!-- END:skills -->

---

See also: [bundles](bundles.md) · [agents](agents.md) · [steering](steering.md) · [hooks and MCP](hooks-and-mcp.md) · [SpecKit](speckit.md)
