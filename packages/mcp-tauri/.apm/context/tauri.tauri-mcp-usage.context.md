# Tauri MCP Usage & Workflow

## Prerequisites & setup

- Node 20+, Rust/Cargo, and the Tauri CLI available.
- Add the `tauri-plugin-mcp-bridge` crate to the app — **dev builds only** (see
  the safety rule in [the index](tauri.tauri-mcp-index.context.md)); register it
  behind `#[cfg(debug_assertions)]` / a dev feature.
- Enable `withGlobalTauri` — **dev builds only**, via a config overlay (see
  [Dev-only config](#dev-only-config-withglobaltauri) below). Do **not** set it
  in the base `tauri.conf.json`, which applies to release builds too.
- The app must be **running** for the MCP tools to connect; the bridge listens on
  WebSocket port 9223 and the MCP server connects to it.

## Dev-only config: `withGlobalTauri`

`withGlobalTauri` injects the `window.__TAURI__` global into the webview,
exposing the full Tauri API (`invoke`, `event`, …) on `window` without importing
`@tauri-apps/api`. The MCP bridge **needs** it — it drives the webview by
executing JS against `window.__TAURI__`.

It is a **dev-only** surface, exactly like the bridge plugin:
- Frontends that reach the backend through generated bindings (e.g. tauri-specta,
  importing `@tauri-apps/api/*`) do not use the global at runtime, so production
  does not need it.
- Enabling it globally widens the attack surface — the whole Tauri API becomes
  reachable from any script in the webview, which is especially dangerous under a
  permissive (`"csp": null`) policy.

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

Both halves of the MCP surface are **dev-only** and must **never** ship in a
production / release build:
- the `tauri-plugin-mcp-bridge` plugin — gate behind `#[cfg(debug_assertions)]` /
  a dev feature, and
- `withGlobalTauri` — enable only via the dev config overlay, never in the base
  `tauri.conf.json`.

Confirm both are excluded from release artifacts.
