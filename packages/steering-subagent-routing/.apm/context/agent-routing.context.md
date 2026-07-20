# Agent Routing

Model routing is applied by the patch-agents finalizer; overrides live in `.apm/runtime-agent-overrides.yml`.

## Criteria-based routing

| Task type | Claude tier | Claude effort | Codex fallback |
|-----------|-------------|----------------|----------------|
| review / verify / adversarial / design judgment | opus (fable when available) | high | gpt-5.5 high |
| scoped implementation, refactors, tests | sonnet | medium | gpt-5.4 medium |
| mechanical/bounded transforms, lookups | haiku | low | gpt-5.4-mini low |
| orchestration / planning | main session | inherit | parent session |
| explicit coding-agent override | — | — | gpt-5.4 high |

Pick the cheapest tier the task tolerates; escalate on failed verification, not preemptively.

NOT haiku for implementation tasks that are complex, ambiguous, or loosely
scoped — measured (84-run matrix, 2026-07): haiku follows instruction-shaped
bait 2/2 where opus/sonnet resist, violates output contracts 11-13/14, and
wrote the runaway fake-clock tests. Well-scoped simple mechanical patches
(single-file rename, bounded transform, lookup, format fix) stay haiku-eligible.

Do not encode MCP usage in model overrides. When delegating to coding or design
agents, pass task-specific instructions to use the project's available tools, such
as Context7 for library docs, codebase-memory-mcp for graph-aware exploration,
Playwright for browser verification, or Stitch for design work.

In beads repos (`bd where` succeeds), pass the bead id in the spawn prompt so
the worker claims it (`bd update <id> --claim`) — an unpassed id leaves the
bead unclaimed and a parallel worker may take the same work.

## Repomix refresh

Repomix is a snapshot packer, on-demand, stored as ignored `repomix.xml`.

| Refresh after | Do NOT refresh on |
|---------------|-------------------|
| `git switch -c` / `checkout -b` / `worktree add` | every commit |
| `git merge` / `git pull` / `git rebase` | PR create/review |
| | remote-only `gh pr merge` |
