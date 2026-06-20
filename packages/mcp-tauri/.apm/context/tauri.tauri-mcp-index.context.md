# Tauri MCP Context

Use the Tauri MCP server (`tauri` MCP) to build, test, debug, and drive a running
Tauri v2 desktop or mobile app. It connects to the app over a WebSocket bridge
and exposes ~21 tools across these areas:

- **UI automation / WebView** — screenshots, DOM snapshots, JavaScript execution,
  a visual element picker, clicks and gestures, and console-log access.
- **IPC monitoring** — execute IPC commands and watch / inspect frontend↔backend
  traffic and events.
- **Logging** — stream console and app logs while reproducing an issue.
- **Testing** — combine UI automation + IPC + logs to write and verify e2e flows.
- **Mobile** — list devices / simulators before mobile runs.

Read only the relevant detail:

- [Tauri MCP usage & workflow](tauri.tauri-mcp-usage.context.md)
- [WSL ↔ Windows connectivity](tauri.tauri-mcp-wsl.context.md)

## Safety: dev builds only

The bridge that these tools talk to is the `tauri-plugin-mcp-bridge` crate. It
opens a local control WebSocket inside the app, so it is a **development-only**
dependency:

- Gate it behind `#[cfg(debug_assertions)]` or a dedicated dev feature flag.
- **Never** ship it in a production / release build — a shipped bridge is a
  remote-control backdoor into the app.
- Verify it is excluded from release artifacts before publishing.
