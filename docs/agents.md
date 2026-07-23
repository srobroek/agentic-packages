# Agents

Subagents the main thread can delegate to. Install the package that owns the
agent definition.

Workflow-specific task agents stay in their hybrid workflow packages. APM
deploys the same `.apm/agents/*.agent.md` source as native Markdown for Claude
and TOML for Codex. Generic raw and semantic Codex profiles each have their own
`agent-*` package; there is no mega-package containing every Codex role.

Every agent-bearing package owns `.apm/agent-models.yml`. APM 0.26 drops model
metadata when it transforms an agent to Codex TOML. The package lifecycle
handles that limitation:

- The post-deploy injector restores `model` and `model_reasoning_effort`.
- The consumer owns the lifecycle trigger because APM does not discover
  lifecycle blocks from dependencies.
- The strict check requires every portable source and deployed Codex profile
  to resolve to a complete mapping.
- Wrapper packages map the external agents they install. A consumer that
  installs an external agent directly supplies `.apm/agent-models.yml`.

Use the parent workflow package or explicitly install a standalone profile.
APM 0.26 honors package/dependency targets, although an explicit direct install
with the opposite `--target` can force a target-specific package through that
runtime's transformer.

<!-- BEGIN:agents -->
| Agent | Description |
| --- | --- |
| `agent-adversarial-challenger` | Read-only adversarial challenger: independently stress-tests any claim, plan, design, hypothesis, decision, or conclusion -- technical or not -- by attacking its assumptions and returning evidence-backed counter-arguments and alternatives, without changing anything. The critic half of a generate/critique loop; debugging escalation, debate devil's-advocate, research and decision review are all applications. |
| `agent-coder` | Implementation subagents for bounded code changes, tests, and refactors within a defined scope. Ships `coder` (edits the caller's tree directly; the parent commits) and `parallel-coder` (runs in an isolated worktree, self-commits, and hands back a reviewable branch — for parallel or staged work). Delegation is guided by steering and explicit orchestration rather than per-edit hooks. |
| `agent-coder-high` | Escalated coding agent for complex bounded implementation and debugging. |
| `agent-explorer` | Read-only exploration agent for bounded code and configuration discovery. |
| `agent-external-repo-worker` | Subagent that works inside an external repository outside the caller project. Handles isolated clone or reuse, convention discovery, bounded edits, local verification, and delegated publish or PR work. |
| `agent-operator` | Mechanical operator agent for tiny commands, formatting, and inventory steps. |
| `agent-pr-reviewer` | Subagent that reviews pull requests for code quality, security, and best practices. |
| `agent-quality-guards` | Read-only quality-guard subagents for bounded triage: docs-guard checks scoped documentation and documentation lint findings, lint-guard validates and normalizes lint reports, data-metrics-summarizer compacts large logs and metrics, maintenance-metrics-reader snapshots repository maintenance health (stale branches, worktrees, lock states), and reviewer-mechanics smoke-checks scoped diffs for mechanical issues. All five reply with bounded, capped verdict lines and never edit files. |
| `agent-reasoner` | Read-only reasoning agent for exceptional architecture, policy, and adversarial questions. |
| `agent-reviewer-high` | Adversarial read-only reviewer for security-sensitive and broad-impact changes. |
| `agent-reviewer-low` | Mechanical read-only reviewer for tiny changes with explicit criteria. |
| `agent-worker` | Bounded implementation worker for changes without a more specific coding role. |
<!-- END:agents -->

---

See also: [bundles](bundles.md) · [skills](skills.md) · [steering](steering.md) · [hooks and MCP](hooks-and-mcp.md) · [external repos](external-repos.md) · [SpecKit](speckit.md)
