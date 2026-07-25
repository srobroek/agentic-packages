# Tools And Scripts Context

Use this context for repo automation, scripts, maintained CLIs, generators, MCP
implementations, task runners, and orchestration files.

Use `scripts/` for thin repo automation. Scripts should be direct, inspectable,
and easy for agents to run.

Use `tools/` for maintained CLIs, generators, MCP server implementations, and
reusable developer tooling.

Task-runner defaults (`just`, `mise`, `moon`): see steering-toolchain-defaults.

Keep generated outputs and caches out of source unless the project explicitly
tracks them.
