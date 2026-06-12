# Skills

Reusable workflows, each its own package, deployed to `.agents/skills/` (cross-client). A skill is loaded on demand when its trigger matches; install only the workflows you want.

Install a single skill with `apm install <name>@srobroek-agentic`, or get a curated set via a [bundle](bundles.md).

<!-- BEGIN:skills -->
| Skill | Description |
| --- | --- |
| `audit-steering` | Audit agent rules, hooks, skills, and guardrails for drift and cleanup. |
| `catchup` | Resume interrupted project work by locating and following the best handover before doing fresh discovery, after context loss, /clear, or a continue/resume request. |
| `chezmoi-editor` | Edit chezmoi-managed dotfiles from their authoritative source files. Use when changing dotfiles, global agent/tool config, templates, private files, symlinked config, or any live target that may be managed by chezmoi. |
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
| `optimize-steering` | Audit and optimize agent-facing markdown (steering docs, skills, agent definitions) for token efficiency and cross-model compliance (rules R1-R7). |
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

---

See also: [bundles](bundles.md) · [agents](agents.md) · [steering](steering.md) · [hooks and MCP](hooks-and-mcp.md) · [SpecKit](speckit.md)
