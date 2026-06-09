# Agents

Sub-agents the main thread can delegate to, each with its own model, tool access, and permission profile. Install an agent package to make it available to your runtime's delegation/`Task` tooling.

Each agent ships an `x-agentic` block mapping its model/effort/sandbox/approval to both Claude and Codex; the `patch-agentic-tools` finalizer applies those native fields after install (see the [README developing section](../README.md#developing-this-repository)).

The four standalone agents below are also bundled into domain bundles (e.g. `agent-pr-reviewer` is in `review`, `code-intelligence`, and `project-lifecycle`). The six SpecKit sub-agents ship inside the `speckit` package -- see [SpecKit](speckit.md).

<!-- BEGIN:agents -->
| Agent | Description |
| --- | --- |
| `agent-adversarial-challenger` | Read-only adversarial challenger: independently stress-tests any claim, plan, design, hypothesis, decision, or conclusion -- technical or not -- by attacking its assumptions and returning evidence-backed counter-arguments and alternatives, without changing anything. The critic half of a generate/critique loop; debugging escalation, debate devil's-advocate, research and decision review are all applications. |
| `agent-coder` | Implementation subagent for bounded code changes, tests, and refactors within a defined scope. |
| `agent-external-repo-worker` | Subagent that works inside an external repository outside the caller project. Handles isolated clone or reuse, convention discovery, bounded edits, local verification, and delegated publish or PR work. |
| `agent-pr-reviewer` | Subagent that reviews pull requests for code quality, security, and best practices. |
<!-- END:agents -->

---

See also: [bundles](bundles.md) · [skills](skills.md) · [steering](steering.md) · [hooks and MCP](hooks-and-mcp.md) · [SpecKit](speckit.md)
