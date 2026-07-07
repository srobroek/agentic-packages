# Agent Routing

Model routing is applied by the patch-agents finalizer; overrides live in `.apm/runtime-agent-overrides.yml`.

## Criteria-based routing

| Task type | Claude tier | Codex fallback |
|-----------|-------------|----------------|
| review / verify / adversarial / design judgment | opus (fable when available) | gpt-5.5 high |
| scoped implementation, refactors, tests | sonnet | gpt-5.4 medium |
| mechanical/bounded transforms, lookups | haiku | gpt-5.4-mini low |
| orchestration / planning | main session | parent session |
| explicit coding-agent override | — | gpt-5.3-codex-spark high |

Pick the cheapest tier the task tolerates; escalate on failed verification, not preemptively.

Do not encode MCP usage in model overrides. When delegating to coding or design
agents, pass task-specific instructions to use the project's available tools, such
as Context7 for library docs, codebase-memory-mcp for graph-aware exploration,
Playwright for browser verification, or Stitch for design work.

## Repomix refresh

Repomix is a snapshot packer, on-demand, stored as ignored `repomix.xml`.

| Refresh after | Do NOT refresh on |
|---------------|-------------------|
| `git switch -c` / `checkout -b` / `worktree add` | every commit |
| `git merge` / `git pull` / `git rebase` | PR create/review |
| | remote-only `gh pr merge` |
