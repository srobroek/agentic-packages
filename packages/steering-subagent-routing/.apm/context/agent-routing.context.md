# Agent Routing

Model routing is applied by per-package `agent-models.yml` files, injected at build time via `inject-agent-models.py`.

## Criteria-based routing

Spawn an agent by name rather than choosing a tier by hand: every shipped agent
already carries a measured model+effort pin. Route by tier only when none fits.

| Task type | Claude tier | Claude effort | Codex fallback |
|-----------|-------------|----------------|----------------|
| review / verify / adversarial / design judgment | opus | high | gpt-5.6-sol high |
| scoped implementation, refactors, tests | opus | low--medium | gpt-5.6-luna xhigh |
| exploration, research, report writing | opus | low | gpt-5.6-luna high |
| mechanical readers: log/metric summarising, lint and doc gathering, diff smoke checks | sonnet | high | gpt-5.3-codex-spark low--medium |
| orchestration / planning | main session | inherit | parent session |
| explicit coding-agent override | -- | -- | gpt-5.6-luna high |

NOTE: `fable` is the frontier Claude model but is reserved for explicit user
opt-in only -- never auto-routed by steering or agents.

Do not route to `haiku`. Escalate on failed verification, not preemptively.

Do not encode MCP usage in model overrides. When delegating to coding or design
agents, pass task-specific instructions to use the project's available tools,
such as Context7 for library docs, semantic symbol tools for code exploration,
Playwright for browser verification, or Stitch for design work.

In beads repos (`bd where` succeeds), pass the bead id in the spawn prompt so
the worker claims it (`bd update <id> --claim`) -- an unpassed id leaves the
bead unclaimed and a parallel worker may take the same work.

## Repomix refresh

Repomix is a snapshot packer, on-demand, stored as ignored `repomix.xml`.

| Refresh after | Do NOT refresh on |
|---------------|-------------------|
| `git switch -c` / `checkout -b` / `worktree add` | every commit |
| `git merge` / `git pull` / `git rebase` | PR create/review |
| | remote-only `gh pr merge` |
