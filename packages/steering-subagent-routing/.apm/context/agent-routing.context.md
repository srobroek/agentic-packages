# Agent Routing

Agent definitions are authored once as `.apm/agents/*.agent.md`.

Each agent carries namespaced `x-agentic` frontmatter. The APM install step
creates runtime-native agent files; the `apm run patch-agents` finalizer then
normalizes runtime-specific metadata that APM cannot represent directly.

Codex patch fields:

- `model`
- `model_reasoning_effort`
- `sandbox_mode`

Claude patch fields:

- `model`
- `effort`
- `permissions`, when explicitly provided

Default routing:

- Claude `opus` fallback: `gpt-5.5`, high effort.
- Claude `sonnet` fallback: `gpt-5.4`, medium effort.
- Claude `haiku` fallback: `gpt-5.4-mini`, low effort.
- Explicit coding-agent overrides: `gpt-5.3-codex-spark`, high effort.
- Main planning/orchestration remains the parent GPT-5.5 high/xhigh session.

External runtime overrides live in `.apm/runtime-agent-overrides.yml`. They are
applied before Claude model fallback, so an explicit Spark mapping is not later
remapped by an upstream `opus` or `sonnet` frontmatter value.

Do not encode MCP usage in model overrides. When delegating to coding or design
agents, the main session should pass task-specific instructions to use the
project's available tools, such as Context7 for library docs,
codebase-memory-mcp for graph-aware exploration, Playwright for browser
verification, or Stitch for design work.

Repomix is a snapshot packer, not an incremental code index. Use it on demand
when a task needs compact broad repository context. Store generated packs in
the ignored repo-root file `repomix.xml` so agents can find them without
treating them as source. Do not check them in; project setup should ignore
`repomix.xml`, `repomix.md`, `repomix.json`, and `repomix.txt`.
Refresh the cache after branch/worktree creation and local integration events
such as `git switch -c`, `git checkout -b`, `git worktree add`, `git merge`,
`git pull`, or `git rebase`. Do not treat every commit as a Repomix refresh
point. Do not refresh Repomix on PR creation, PR review, or remote-only
`gh pr merge`; the pack should reflect the local worktree after the relevant
branch or merged base branch has actually been pulled or checked out.

Agents and orchestrators must clean up their worktrees and compilation
artifacts once their work is done. Dead worktrees accumulate build output (a
Rust `target/` dir alone can reach tens of GB) until the disk fills; a shared
build directory would only mask this while serializing parallel builds. The
removal is gated on the worktree being confirmed clean: `git -C <worktree>
status --porcelain` prints nothing and the branch is merged or harvested —
never discard uncommitted work to force a removal. Once confirmed clean,
delete build dirs (`rm -rf <worktree>/target`, plus `node_modules/` and
similar) and run `git worktree remove <worktree>` and `git worktree prune`;
orchestrators sweep this way after every fan-in and periodically via
`git worktree list`.
