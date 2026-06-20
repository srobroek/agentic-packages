# Tauri MCP Context

Use the Tauri MCP server (`tauri` MCP) to drive, test, and debug a **running**
Tauri v2 desktop app. It is backed by the
[P3GLEG `tauri-plugin-mcp`](https://github.com/P3GLEG/tauri-plugin-mcp): a small
Rust plugin compiled into the app (dev builds only) opens a raw TCP socket that
the `tauri-plugin-mcp-server` MCP server connects to. The server exposes 10
tools:

- **Screenshots** — `take_screenshot` (viewport capture with thumbnail).
- **DOM / page** — `query_page` (modes: `app_info`, `map`, `html`, `state`,
  `find_element`).
- **Input automation** — `click`, `type_text` (incl. bulk form fill),
  `mouse_action` (hover / scroll / drag), `navigate` (goto / back / forward /
  reload).
- **Scripting** — `execute_js` (arbitrary JS in the webview).
- **State** — `manage_storage` (localStorage / cookies), `manage_window`
  (focus / size / position / zoom / devtools).
- **Synchronisation** — `wait_for` (text / element visibility).

Compose these (screenshot + query_page + execute_js + wait_for) to author and
verify end-to-end UI flows.

Read only the relevant detail:

- [Tauri MCP usage & workflow](tauri.tauri-mcp-usage.context.md)
- [WSL ↔ Windows connectivity](tauri.tauri-mcp-wsl.context.md)

## Safety: dev builds only

The Rust plugin opens a local control socket that can drive the app (a
remote-control backdoor if shipped). Register it **only** in dev builds, gated
behind `#[cfg(debug_assertions)]` (or a dedicated dev feature). `debug_assertions`
is off in release builds, so a `tauri build` excludes the surface automatically —
but verify the plugin is absent from release artifacts before publishing.

Unlike a `window.__TAURI__` (`withGlobalTauri`) bridge, this plugin drives the
webview from the Rust side, so it does **not** require `withGlobalTauri` and adds
no extra webview attack surface in dev.
