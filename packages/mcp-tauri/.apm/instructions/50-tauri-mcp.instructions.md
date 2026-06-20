---
description: When and how to use the Tauri MCP server to drive, test, and debug a running Tauri v2 app.
applyTo: "**/*"
---

This repo uses the Tauri MCP server (P3GLEG `tauri-plugin-mcp`, over TCP
`127.0.0.1:9999`) to drive, test, and debug a **running** Tauri v2 app —
screenshots, DOM queries, click/type/scroll, navigation, JS execution, and
storage/window control. Before automating the UI or writing end-to-end tests,
read [Tauri MCP context](../context/tauri.tauri-mcp-index.context.md). The Rust
plugin is **dev-only** — keep it behind `#[cfg(debug_assertions)]` and out of
release builds.
