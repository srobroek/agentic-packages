# Hooks and MCP packages

## Hook packages

Opt-in lifecycle hooks. Most hooks ship inside their owning package (code-intelligence, agent-coder, unstuck, the MCP packages, speckit); the two below are standalone cross-cutting policy packages.

A package ships hooks as `.apm/hooks/<pkg>-{claude,codex}-hooks.json` plus a `scripts/` directory, with commands referencing `${PLUGIN_ROOT}/scripts/<name>.sh`. On install, APM deploys the scripts under `.claude/hooks/<pkg>/` and `.codex/hooks/<pkg>/`, rewrites `${PLUGIN_ROOT}`, and merges the config into `settings.json` / `hooks.json`. Codex only supports `UserPromptSubmit`, `PreToolUse`, `PermissionRequest`, `PostToolUse`, and `Stop`; lifecycle events like `SessionStart` and `SubagentStart` are Claude-only, so those hooks ship in the claude variant only.

<!-- BEGIN:hooks -->
| Hook Package | Description |
| --- | --- |
| `hooks-git-workflow` | Opt-in git workflow hooks: gate commits on passing tests, track edit-vs-test state, and warn about uncommitted work at session end. Cross-tool (Claude + Codex). |
| `hooks-quality` | Opt-in code-quality hooks: advisory linting/formatting feedback after edits and a quality check before commits. Cross-tool (Claude + Codex). |
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
