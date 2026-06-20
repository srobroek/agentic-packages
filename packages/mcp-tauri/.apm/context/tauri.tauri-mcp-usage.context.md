# Tauri MCP Usage & Workflow

## Prerequisites & setup

- Node 20+, Rust/Cargo, and the Tauri CLI available.
- Add the `tauri-plugin-mcp-bridge` crate to the app — **dev builds only** (see
  the safety rule in [the index](tauri.tauri-mcp-index.context.md)); register it
  behind `#[cfg(debug_assertions)]` / a dev feature.
- Enable `withGlobalTauri` in `tauri.conf.json`.
- The app must be **running** for the MCP tools to connect; the bridge listens on
  WebSocket port 9223 and the MCP server connects to it.

## When to reach for which tools

- **UI automation / WebView** — take screenshots, capture a DOM snapshot, run
  JavaScript, use the visual element picker, perform clicks and gestures, and
  read console logs. Use these to drive the UI and assert on what is rendered.
- **IPC monitoring** — execute IPC commands directly, watch frontend↔backend
  traffic, and inspect events. Use these to debug command/event wiring.
- **Logging** — stream console / app logs while reproducing a bug.
- **Testing** — compose UI automation + IPC + logs to author and verify
  end-to-end flows.
- **Mobile** — list connected devices / simulators before a mobile run.

## Host / port override

The default connection target is `localhost:9223`. The connection can be
redirected when the app is not on the same loopback as the MCP server:

- Pass a `host` parameter to the `driver_session` tool (e.g. a device IP).
- Or set environment variables: `MCP_BRIDGE_HOST`, `TAURI_DEV_HOST`,
  `MCP_BRIDGE_PORT`.

The bridge binds `0.0.0.0` by default, so non-localhost clients (network mobile
devices, or a WSL-hosted agent reaching a Windows app) can connect. See
[WSL ↔ Windows connectivity](tauri.tauri-mcp-wsl.context.md) for the WSL case.

## Safety reminder

The `tauri-plugin-mcp-bridge` plugin must **never** ship in a production /
release build. Confirm it is excluded from release artifacts.
