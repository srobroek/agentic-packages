# Tauri MCP Usage & Workflow

## Prerequisites & setup

- Node 20+, Rust/Cargo, and the Tauri CLI available.
- Add the `tauri-plugin-mcp-bridge` crate and enable `withGlobalTauri` — dev
  builds only; see the safety rule in
  [the index](tauri.tauri-mcp-index.context.md).
- The app must be **running** for the MCP tools to connect; the bridge listens on
  WebSocket port 9223 and the MCP server connects to it.

## Dev-only config: `withGlobalTauri`

`withGlobalTauri` injects the `window.__TAURI__` global into the webview,
exposing the full Tauri API (`invoke`, `event`, …) on `window` without importing
`@tauri-apps/api`. The MCP bridge **needs** it — it drives the webview by
executing JS against `window.__TAURI__`. Frontends that reach the backend through
generated bindings (e.g. tauri-specta) never use the global at runtime, so
production does not need it.

Tauri v2 does not auto-merge debug/release config, but supports an explicit
overlay via `--config`. Keep the global out of release:
1. Leave the base `tauri.conf.json` with `withGlobalTauri` off (the default).
2. Add a dev overlay, e.g. `src-tauri/tauri.dev.conf.json`:
   ```json
   { "app": { "withGlobalTauri": true } }
   ```
3. Run dev with the overlay: `tauri dev --config src-tauri/tauri.dev.conf.json`
   (wire it into your dev recipe / script). A plain `tauri build` omits the
   overlay, so release builds stay clean.

## Host / port override

The default connection target is `localhost:9223`. The connection can be
redirected when the app is not on the same loopback as the MCP server:

- Pass a `host` parameter to the `driver_session` tool (e.g. a device IP).
- Or set environment variables: `MCP_BRIDGE_HOST`, `TAURI_DEV_HOST`,
  `MCP_BRIDGE_PORT`.

The bridge binds `0.0.0.0` by default, so non-localhost clients (network mobile
devices, or a WSL-hosted agent reaching a Windows app) can connect. See
[WSL ↔ Windows connectivity](tauri.tauri-mcp-wsl.context.md) for the WSL case.
