# Rust Tooling Defaults

- Format: `rustfmt`; lint: `clippy` (`-D warnings` in CI).
- Tests: `cargo nextest run` (per-test isolation, parallel); also run `cargo test --doc`.
- Coverage: `cargo llvm-cov nextest --lcov`.
- Install dev/CI tools: `taiki-e/install-action`; fall back to `cargo binstall`.
  Avoid `cargo install` in CI.
- Dependency gate: `cargo deny check` (advisories, bans, licenses, sources).
