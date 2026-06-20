# Tauri (v2) App Defaults

Load only when the task involves a Tauri desktop app — bundles, releases,
auto-update, or signing. Generic Rust tooling/CI still applies: see
[Tooling](rust.tooling.context.md) and [CI](rust.ci.context.md).

## Release pipeline

- Build + release with `tauri-apps/tauri-action@v0` in a 3-OS matrix (ubuntu,
  windows, macos). It runs `tauri build`, produces the OS-native installers
  (NSIS/MSI/DMG/AppImage/deb), and — with signing keys set — generates the
  updater `latest.json` + per-artifact minisign `.sig`.
- Orchestrate versions/changelog with `release-please` (Conventional Commits →
  release PR → tag). Do NOT use GoReleaser or cargo-dist: they ship plain
  binaries and produce neither Tauri bundles nor the updater manifest.
- Draft-then-publish: tauri-action uploads to a DRAFT release; flip to published
  only after every OS build succeeds, so the updater never points at a partial
  set.
- Release workflow: omit `cancel-in-progress` (never abort a mid-upload release).

## Updater

- Use `tauri-plugin-updater`. Put the public key in `tauri.conf.json`; sign with
  `TAURI_SIGNING_PRIVATE_KEY` (+ `_PASSWORD`). Serve a static `latest.json` on
  the GitHub Release; use a dynamic endpoint only for channels / staged rollout.

## Code signing

- Windows: prefer SignPath Foundation (free, OSS) or Azure Trusted Signing
  (verify the US/Canada + 3-year-history eligibility first); EV cert last resort.
- macOS: Developer ID Application + `notarytool`, authenticated with an App Store
  Connect API key (`APPLE_API_KEY` / `_ISSUER` / `_KEY_PATH`) rather than an
  Apple ID password.

## E2E testing (real-UI)

- Driver: drive the real app through `tauri-driver` (W3C WebDriver proxy on
  `:4444`). It is NOT managed by the client — spawn it (and a frontend server for
  the dev/preview URL) yourself, then tear them down. Linux needs
  `webkit2gtk-driver` (WebKitWebDriver) run under `xvfb`; Windows uses a
  version-matched `msedgedriver`. The webview cannot run in WSL — verify in CI
  (Linux/xvfb) or on a real desktop; macOS UI driving is best-effort.
- Install `tauri-driver` via `taiki-e/install-action` (`tool: tauri-driver@<ver>`),
  NOT a hand-rolled `cargo binstall`/`cargo install`. With a warm
  `Swatinem/rust-cache`, bare `cargo binstall` reads stale `.crates2.json`, skips
  the download, and leaves the binary off PATH → `spawn tauri-driver ENOENT`. The
  action owns placement/PATH/its own version-keyed cache (it may use binstall as
  transport internally — that's fine; just don't hand-roll it).
- Client: prefer Rust **thirtyfour** over native JS WebdriverIO so E2E lives in
  the cargo workspace and shares contract types. Session capabilities MUST contain
  ONLY `tauri:options.application` and NO `browserName` (else WebKitWebDriver
  rejects the session). thirtyfour's `Capabilities::new()` is an empty map passed
  verbatim — correct. AVOID **fantoccini**: it unconditionally injects
  `goog:chromeOptions.w3c` + `pageLoadStrategy`, adding extension caps the native
  driver may reject. thirtyfour has no async Drop (call `driver.quit().await`) and
  no auto-wait / `expect`-style matchers — use `driver.query(..)` + `wait_until`
  and plain `assert!`. Tauri's docs only show JS wdio + Selenium; a Rust client is
  off-doc but works (tauri-driver is generic W3C).
- Assertions / round-trips (FR-008-style): `withGlobalTauri` is off by default, so
  `window.__TAURI__` is absent in the webview. Expose a build-flag-gated invoke
  bridge (e.g. `VITE_E2E` → `window.__APP_E2E__.invoke`, tree-shaken from prod) and
  read it from a test via `execute_async`, or assert through the UI. Read back via
  query commands (`*_list`, audit log) — do NOT add a direct SQLite reader.
- Runner: **cargo-nextest**. Put E2E in a dedicated crate (`crates/e2e-tests`) with
  a `[profile.e2e]`. Serialize it (shared `:4444`/`:5173`) with a test-group
  `max-threads = 1`; add `retries` (exponential backoff) for webview flake; raise
  `slow-timeout`; emit JUnit for CI. Keep E2E OUT of the default run
  (`-E 'not package(e2e-tests)'`), run it with
  `--profile e2e -E 'package(e2e-tests)'`. Start driver+frontend OUTSIDE nextest (a
  `just e2e` recipe / explicit CI steps: start → run → kill). nextest setup-scripts
  are experimental and have NO teardown hook, and a foreground driver hangs the
  run — so don't rely on them for the driver lifecycle.

```toml
# .config/nextest.toml
[test-groups]
serial-e2e = { max-threads = 1 }
[profile.e2e]
slow-timeout = { period = "60s", terminate-after = 3 }
retries = { backoff = "exponential", count = 3, delay = "5s", max-delay = "30s", jitter = true }
fail-fast = false
[profile.e2e.junit]
path = "junit.xml"
[[profile.e2e.overrides]]
filter = "package(e2e-tests)"
test-group = "serial-e2e"
```

- Agent-interactive MCP (a complement to, NOT a replacement for, scripted CI E2E):
  use **`P3GLEG/tauri-plugin-mcp`** — a debug-only Rust plugin
  (`#[cfg(debug_assertions)]`) embedded in the app plus a standalone MCP server,
  so agents can drive and inspect the REAL running app. Transport: agent↔server
  over stdio (MCP); server↔plugin over an IPC socket (default
  `/tmp/tauri-mcp.sock`) or TCP (auth token required for non-loopback). Tools:
  `execute_js`, `query_page` (map/html/state/find_element/app_info), `click`,
  `type_text`, `mouse_action`, `navigate`, `take_screenshot`, `manage_storage`,
  `manage_window`, `wait_for`. macOS gets native `NSEvent` injection;
  Windows/Linux use a JS input fallback (~80% coverage). It does NOT use
  tauri-driver and is independent of the WebDriver suite. Use it for interactive
  investigation/debugging; use thirtyfour+nextest for deterministic regression
  gates. thirtyfour/fantoccini are libraries, not MCP servers; Playwright MCP
  cannot drive the Tauri native webview or tauri-driver's W3C endpoint.
