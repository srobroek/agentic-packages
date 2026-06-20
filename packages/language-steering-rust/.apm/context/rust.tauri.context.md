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
