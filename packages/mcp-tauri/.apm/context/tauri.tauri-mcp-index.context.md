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

The MCP surface has **two dev-only halves**, both of which must be kept out of
release builds:

- The `tauri-plugin-mcp-bridge` crate — opens a local control WebSocket inside
  the app (a remote-control backdoor if shipped). Gate it behind
  `#[cfg(debug_assertions)]` or a dedicated dev feature flag.
- `withGlobalTauri` — exposes the full Tauri API on `window.__TAURI__` (needed by
  the bridge to drive the webview). Enable it only through a dev config overlay,
  never in the base `tauri.conf.json`. See
  [usage → dev-only config](tauri.tauri-mcp-usage.context.md#dev-only-config-withglobaltauri).

**Never** ship either in a production / release build; verify both are excluded
from release artifacts before publishing.
