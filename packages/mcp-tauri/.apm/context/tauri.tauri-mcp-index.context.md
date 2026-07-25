# Tauri MCP Context

Use the Tauri MCP server (`tauri` MCP) to build, test, debug, and drive a running
Tauri v2 desktop or mobile app. It connects to the app over a WebSocket bridge.

Read only the relevant detail:

- [Tauri MCP usage & workflow](tauri.tauri-mcp-usage.context.md)
- [WSL ↔ Windows connectivity](tauri.tauri-mcp-wsl.context.md)

## Safety: dev builds only

The MCP surface has two halves, and shipping either in a release build hands
remote control of the app to anything that can reach it:

- The `tauri-plugin-mcp-bridge` crate opens a local control WebSocket inside the
  app. Gate it behind `#[cfg(debug_assertions)]` or a dedicated dev feature flag.
- `withGlobalTauri` exposes the full Tauri API on `window.__TAURI__` (needed by
  the bridge to drive the webview). Enable it only through a dev config overlay,
  never in the base `tauri.conf.json`. See
  [usage → dev-only config](tauri.tauri-mcp-usage.context.md#dev-only-config-withglobaltauri).
