# Serena MCP client compatibility

`mcp-serena` starts one project-scoped Serena server over stdio. The launcher
walks the process ancestry so shell wrappers do not change the selected
`--context`; set `SERENA_MCP_CONTEXT` when a harness needs an explicit value.

Claude Code can start Serena from an agent-local MCP declaration. Codex's
current CLI documentation accepts `mcp_servers` in custom agent files, but
Codex 0.145.0 does not actually start an agent-local server in this setup.
Until that client behavior is fixed upstream, Codex agents should use the
shared semantic MCP route when it is configured, while Claude agents can use
this package directly.

The launcher always uses `--project-from-cwd`, so the process must start in the
checkout or worktree whose symbols it is expected to inspect. Sharing one
long-lived Serena process across worktrees remains a separate, future launcher
capability; do not assume it from this package version.
