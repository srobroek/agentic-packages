# Rust Tooling Defaults

- Format with `rustfmt`; lint with `clippy` (`-D warnings` in CI).
- Run tests with `cargo nextest run` — per-test process isolation, global
  parallel scheduling, and `--retries` for flakes. Nextest does NOT run
  doctests, so also run `cargo test --doc`.
- Measure coverage with `cargo llvm-cov nextest` (LLVM source-based; runs the
  nextest suite in one pass). Emit `--lcov` for upload.
- Install dev/CI tools with `taiki-e/install-action` (curated, checksummed);
  fall back to `cargo binstall`. Avoid `cargo install` in CI (source builds).
- Gate dependencies with `cargo deny check` (advisories, bans, licenses,
  sources) — supersedes `cargo audit` and adds license + duplicate control.
