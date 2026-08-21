# mcp-serena

`mcp-serena` registers Serena as a direct MCP server for Codex and Claude Code.
It shares the Serena and language-server backend between agents that use the
same Git checkout. Linked worktrees receive separate, resource-limited
backends.

Install the APM package `mcp-serena@srobroek-agentic`. Serena must be available
as `serena` on `PATH`. The launcher uses an installed `mcp-proxy` command or
falls back to `uvx` with `mcp-proxy` 0.12.0.

## Runtime behavior

The launcher resolves the current checkout with Git and starts Serena's
Streamable HTTP transport on the loopback interface. Each MCP client receives
a lightweight stdio bridge to that backend.

- The primary checkout has one backend for all attached clients.
- Each linked worktree has its own backend and Serena project state.
- Concurrent clients use a file lock so only one backend starts per checkout.
- Client leases keep an in-use backend alive and discard stale client state.
- An idle supervisor stops primary backends after 30 minutes and worktree
  backends after 2 minutes.
- The default `shared-cli` context exposes semantic navigation, diagnostics,
  refactoring, editing, and memory tools. It excludes basic file, text-search,
  shell, and dashboard tools supplied by the MCP client.

Worktree backends run at nice level 10, inherit at most 1,024 open file
descriptors, and are stopped when their process group's resident memory exceeds
1,024 MiB. Linux also applies the memory limit with `RLIMIT_AS`. The pool allows
20 active worktree backends per repository and 16,384 MiB of aggregate
worktree RSS across the user's Serena pool. Instance or memory pressure removes
idle backends before a new backend is rejected. An attached backend is not
stopped to satisfy the aggregate budget.

Runtime state and logs live under
`$XDG_CACHE_HOME/serena/pools` or `~/.cache/serena/pools`. Set
`SERENA_POOL_HOME` to use another directory.

## Configuration

| Variable | Default | Effect |
| --- | --- | --- |
| `SERENA_MCP_CONTEXT` | packaged `shared-cli` context | Selects another Serena context. A different context uses a separate checkout pool. |
| `SERENA_PROJECT_CWD` | process working directory | Overrides the directory used to resolve the Git checkout. |
| `SERENA_POOL_HOME` | platform cache directory | Stores locks, leases, backend metadata, and logs. |
| `SERENA_POOL_STARTUP_SECONDS` | `45` | Limits backend startup time. |
| `SERENA_PRIMARY_IDLE_SECONDS` | `1800` | Stops an unused primary-checkout backend after this interval. |
| `SERENA_WORKTREE_IDLE_SECONDS` | `120` | Stops an unused linked-worktree backend after this interval. |
| `SERENA_WORKTREE_MAX_INSTANCES` | `20` | Limits active worktree backends per repository. |
| `SERENA_WORKTREE_MEMORY_MB` | `1024` | Stops a worktree backend when aggregate process-group RSS exceeds this value. |
| `SERENA_WORKTREE_TOTAL_MEMORY_MB` | `16384` | Limits aggregate RSS across all pooled worktree backends by evicting unleased backends and rejecting new launches under active-session pressure. |
| `SERENA_WORKTREE_OPEN_FILES` | `1024` | Sets the maximum inherited file-descriptor limit without raising a lower host limit. |
| `SERENA_WORKTREE_NICE` | `10` | Lowers worktree backend CPU scheduling priority. |
| `SERENA_WORKTREE_PROCESSES` | `0` | Applies `RLIMIT_NPROC` when nonzero. This limit is per user on macOS and Linux. |
| `SERENA_WORKTREE_CPU_SECONDS` | `0` | Applies a cumulative `RLIMIT_CPU` budget when nonzero. |
| `SERENA_BIN` | `serena` from `PATH` | Overrides the Serena executable. |
| `SERENA_MCP_PROXY_COMMAND` | installed `mcp-proxy` or pinned `uvx` fallback | Overrides the stdio-to-HTTP bridge command. |
