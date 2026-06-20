# Tauri MCP Usage & Workflow

## Prerequisites & setup

- Node 20+, Rust/Cargo, and the Tauri CLI available.
- Add the `tauri-plugin-mcp` crate (P3GLEG) to the app — **dev builds only** (see
  the safety rule in [the index](tauri.tauri-mcp-index.context.md)); register it
  behind `#[cfg(debug_assertions)]` / a dev feature.
- The app must be **running** for the MCP tools to connect; the plugin listens on
  TCP `127.0.0.1:9999` and the `tauri-plugin-mcp-server` MCP server connects to
  it.
- No `withGlobalTauri` and no config overlay are required — the plugin drives the
  webview from the Rust side.

## App-side registration (dev only)

Workspace `Cargo.toml`:

```toml
# Git-only (not published to crates.io). Pulls in tauri with the `unstable`
# feature, which Cargo unifies across the build.
tauri-plugin-mcp = { git = "https://github.com/P3GLEG/tauri-plugin-mcp" }
```

In `build_app()` / your `tauri::Builder` chain:

```rust
#[allow(unused_mut)]
let mut builder = tauri::Builder::default()
    /* …other plugins… */;

#[cfg(debug_assertions)]
{
    builder = builder.plugin(tauri_plugin_mcp::init_with_config(
        tauri_plugin_mcp::PluginConfig::new("my-app".to_string())
            .start_socket_server(true)
            .tcp_localhost(9999),
    ));
}
```

Add `"mcp:default"` to the app's capability permissions
(`src-tauri/capabilities/default.json`).

> TCP `127.0.0.1:9999` (not a Unix socket) is the recommended transport: it works
> for native Linux/macOS dev **and** the WSL-agent ↔ Windows-app case (see
> [WSL ↔ Windows connectivity](tauri.tauri-mcp-wsl.context.md)). Unix sockets do
> not cross the WSL/Windows boundary.

## MCP server connection (`.mcp.json`)

The `tauri-plugin-mcp-server` reads its target from environment variables:

```json
{
  "command": "npx",
  "args": ["-y", "tauri-plugin-mcp-server"],
  "env": {
    "TAURI_MCP_CONNECTION_TYPE": "tcp",
    "TAURI_MCP_TCP_HOST": "127.0.0.1",
    "TAURI_MCP_TCP_PORT": "9999"
  }
}
```

- `TAURI_MCP_CONNECTION_TYPE=tcp` selects TCP (default is IPC / Unix socket via
  `TAURI_MCP_IPC_PATH`).
- `TAURI_MCP_TCP_HOST` defaults to `127.0.0.1`, `TAURI_MCP_TCP_PORT` to `9999`.
- `TAURI_MCP_AUTH_TOKEN` — required only when the app binds a non-loopback
  address (see the WSL NAT fallback).

This package wires these env vars automatically when installed via APM.

## When to reach for which tools

- **See state** — `take_screenshot` for pixels; `query_page` (`app_info`, `map`,
  `html`, `state`, `find_element`) for structured DOM / app metadata.
- **Drive the UI** — `click`, `type_text`, `mouse_action`, `navigate`.
- **Script / assert** — `execute_js` to run arbitrary JS and read back results.
- **State & window** — `manage_storage` (localStorage / cookies), `manage_window`
  (focus / size / position / zoom / devtools).
- **Synchronise** — `wait_for` text / element visibility before the next step.
- **Testing** — compose screenshot + query_page + execute_js + wait_for to author
  and verify end-to-end flows.

## Safety reminder

The `tauri-plugin-mcp` plugin is **dev-only** and must **never** ship in a
release build. Gate it behind `#[cfg(debug_assertions)]` / a dev feature and
confirm it is excluded from release artifacts.
