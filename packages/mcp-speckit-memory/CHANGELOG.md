# Changelog

## 0.1.0

### Features

- **mcp-speckit-memory:** MCP server package for the Spec Kit Memory Hub
  (`memory-md`) extension. Registers a stdio MCP server (`speckit-memory-hub`)
  exposing the durable project-memory tools (`speckit_memory_search`,
  `speckit_memory_synthesize`, `speckit_memory_refresh_cache`,
  `speckit_memory_share_lesson`, `speckit_memory_sync_shared`,
  `speckit_memory_init_project`, ...). The launcher walks up from the launch
  cwd to find the project-local `.specify/extensions/memory-md`, builds the
  server in-place (`npm install && npm run build`) if `dist/` is missing, then
  execs `node dist/bin/speckit-memory.js mcp-start`. The in-place build is
  required because upstream ships TypeScript source with no built `dist/` (and
  no `node_modules`), and the `speckit-memory` binary is not published to npm,
  so the documented `npx -y speckit-memory mcp-start` cannot work.
  `setup-speckit.sh` builds the server eagerly so the first MCP launch does not
  pay a cold `better-sqlite3` native compile during the stdio handshake; the
  launcher build is the fallback.
