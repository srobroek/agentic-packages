# Hooks and MCP packages

## Hook packages

Opt-in lifecycle hooks. Most hooks ship inside their owning package (code-intelligence, agent-coder, unstuck, the MCP packages, speckit); the two below are standalone cross-cutting policy packages.

A package ships hooks as `.apm/hooks/<pkg>-{claude,codex}-hooks.json` plus a `scripts/` directory, with commands referencing `${PLUGIN_ROOT}/scripts/<name>.sh`. On install, APM deploys the scripts under `.claude/hooks/<pkg>/` and `.codex/hooks/<pkg>/`, rewrites `${PLUGIN_ROOT}`, and merges the config into `settings.json` / `hooks.json`. Codex only supports `UserPromptSubmit`, `PreToolUse`, `PermissionRequest`, `PostToolUse`, and `Stop`; lifecycle events like `SessionStart` and `SubagentStart` are Claude-only, so those hooks ship in the claude variant only.

<!-- BEGIN:hooks -->
| Hook Package | Description |
| --- | --- |
| `hooks-bash-safety` | Bash safety guards: block privilege escalation, curl\|sh pipes, and obviously destructive filesystem ops; soft-confirm rm -rf on non-system paths and hard- block it on system-critical paths. Cross-tool (Claude + Codex). |
| `hooks-branch-check` | Branch awareness hook: on prompt submit, warn when work starts on a protected branch (main/master/develop) and surface relevant feature branches/worktrees. Advisory context only, never blocks. Cross-tool (Claude + Codex). |
| `hooks-git-safety` | Git safety guards: block destructive git operations (reset --hard, force push, branch/stash/tag deletion, worktree remove) and throttle large gh CLI batches toward a rate-limit-aware helper. Cross-tool (Claude + Codex). |
| `hooks-git-workflow` | Opt-in git workflow hooks: gate commits on passing tests, track edit-vs-test state, and warn about uncommitted work at session end. Cross-tool (Claude + Codex). |
| `hooks-no-ff` | Opinionated git policy hook: require --no-ff on git merge so feature-branch history is preserved. Blocks fast-forward merges. Cross-tool (Claude + Codex). |
| `hooks-quality` | Opt-in code-quality hooks: advisory linting/formatting feedback after edits and a quality check before commits. Cross-tool (Claude + Codex). |
| `hooks-squash-merge` | Opinionated git policy hook: require an explicit merge strategy on gh pr merge (--squash for feature PRs, --merge for release PRs). Blocks strategy-less PR merges. Cross-tool (Claude + Codex). |
| `hooks-tool-prefs` | Opinionated advisory hook: suggest preferred tools over deprecated ones (rg over grep, fd over find, pnpm over npm, uv over pip, mise over nvm/pyenv, just over make). Advisory only, never blocks. Cross-tool (Claude + Codex). |
| `hooks-worktree` | Worktree lifecycle hooks: create worktrees outside the repo tree (in /tmp) to prevent nesting, and clean up the worktree directory and branch on removal. Claude WorktreeCreate/WorktreeRemove events. |
<!-- END:hooks -->

## MCP server packages

Pre-wired Model Context Protocol servers. Installing one adds the server's tools to your runtime's MCP config -- no manual server setup.

<!-- BEGIN:mcp -->
| MCP Package | Description |
| --- | --- |
| `mcp-codebase-memory` | MCP server package for the Codebase Memory MCP, providing graph-aware project orientation (symbol search, call paths, code snippets). |
| `mcp-context7` | MCP server package for Context7, providing current library and framework documentation lookups. |
| `mcp-package-version` | MCP server package for Package Version, providing dependency version discovery before adding or upgrading packages. |
| `mcp-playwright` | MCP server package for Playwright, providing browser automation and in-browser UI verification. |
| `mcp-repomix` | MCP server package for Repomix, providing bulk repository snapshots for analysis and review. |
| `mcp-serena` | MCP server package for Serena semantic code tools. The launcher selects the Codex or Claude Code context from the parent harness and can be overridden with SERENA_MCP_CONTEXT. |
<!-- END:mcp -->

---

See also: [bundles](bundles.md) · [skills](skills.md) · [agents](agents.md) · [steering](steering.md) · [SpecKit](speckit.md)
