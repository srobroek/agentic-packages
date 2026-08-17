# Changelog

## [2.1.0](https://github.com/srobroek/agentic-packages/compare/mcp-tauri--v2.0.3...mcp-tauri--v2.1.0) (2026-08-17)


### Features

* **codex:** validate packages and standardize language tooling ([#856](https://github.com/srobroek/agentic-packages/issues/856)) ([42edbfb](https://github.com/srobroek/agentic-packages/commit/42edbfb3948c0103f3ce3ef5ba6819a08ae73566))

## [2.0.3](https://github.com/srobroek/agentic-packages/compare/mcp-tauri--v2.0.2...mcp-tauri--v2.0.3) (2026-07-30)


### Bug Fixes

* **code-intelligence:** stop shipping the unreachable subagent-context branch ([#834](https://github.com/srobroek/agentic-packages/issues/834)) ([6ca1ff5](https://github.com/srobroek/agentic-packages/commit/6ca1ff56e7e5dabbe7f15afb4631f3f4ca79e83b))

## [2.0.2](https://github.com/srobroek/agentic-packages/compare/mcp-tauri--v2.0.1...mcp-tauri--v2.0.2) (2026-07-25)


### Refactors

* cut duplicated rules from steering, agents and skills ([#728](https://github.com/srobroek/agentic-packages/issues/728)) ([8f892aa](https://github.com/srobroek/agentic-packages/commit/8f892aa01b3b0ffbb5888cca0dc4178d57ee967d))

## [2.0.1](https://github.com/srobroek/agentic-packages/compare/mcp-tauri--v2.0.0...mcp-tauri--v2.0.1) (2026-07-25)


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/mcp-tauri--v1.2.0...mcp-tauri--v2.0.0) (2026-07-21)


### ⚠ BREAKING CHANGES

* share MCP backends through 1MCP

### Features

* share MCP backends through 1MCP ([4896601](https://github.com/srobroek/agentic-packages/commit/4896601ca0326762493f340526a97a341b98e24a))

## [1.2.0](https://github.com/srobroek/agentic-packages/compare/mcp-tauri--v1.1.0...mcp-tauri--v1.2.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/mcp-tauri-v1.0.0...mcp-tauri--v1.1.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/mcp-tauri-v0.2.1...mcp-tauri-v1.0.0) (2026-06-20)


### ⚠ BREAKING CHANGES

* **mcp-tauri:** transport changes from WebSocket:9223 to TCP:9999 and the app must register the tauri-plugin-mcp Rust plugin (dev builds only).

### Features

* **mcp-tauri:** switch to P3GLEG tauri-plugin-mcp over TCP ([bc3f29e](https://github.com/srobroek/agentic-packages/commit/bc3f29e5972245f24b174383bcc67c8853d145ba))

## [0.2.1](https://github.com/srobroek/agentic-packages/compare/mcp-tauri-v0.2.0...mcp-tauri-v0.2.1) (2026-06-20)


### Documentation

* **mcp-tauri:** make withGlobalTauri dev-only in steering ([0f41b15](https://github.com/srobroek/agentic-packages/commit/0f41b155fe9ea60b03705b1b75a438b508f627f3))
* **mcp-tauri:** make withGlobalTauri dev-only in steering ([3ca0da2](https://github.com/srobroek/agentic-packages/commit/3ca0da21ca233761c0056a29f7fdda0b44db78e9))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/mcp-tauri-v0.1.0...mcp-tauri-v0.2.0) (2026-06-20)


### Features

* **mcp-tauri:** add standalone Tauri MCP server package ([6f3b7b8](https://github.com/srobroek/agentic-packages/commit/6f3b7b883fccad1847dbb4d1df0dc7376394538b))
* **mcp-tauri:** add standalone Tauri MCP server package ([94f0b61](https://github.com/srobroek/agentic-packages/commit/94f0b6150611fe8f8a6d7b4efb8fd760b79afb1a))

## Changelog
