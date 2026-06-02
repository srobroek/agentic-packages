# Tools And Scripts Context

Use this context for repo automation, scripts, maintained CLIs, generators, MCP
implementations, task runners, and orchestration files.

Use `scripts/` for thin repo automation. Scripts should be direct, inspectable,
and easy for agents to run.

Use `tools/` for maintained CLIs, generators, MCP server implementations, and
reusable developer tooling.

Project orchestration is composable:

- `just` for task aliases and repeatable workflows.
- `mise` for language and tool versions.
- `moon` for larger monorepo task orchestration.

Keep generated outputs and caches out of source unless the project explicitly
tracks them.
