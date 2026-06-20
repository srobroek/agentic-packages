# Rust CI Defaults (GitHub Actions)

## Caching & speed

- Cache with `Swatinem/rust-cache@v2`: per-OS `shared-key`, `cache-on-failure`.
- Set `CARGO_INCREMENTAL: 0` — smaller, reusable cache and a prerequisite for
  any compiler-cache layer.
- Use toolchain ≥1.90 (rust-lld is the default Linux linker — free link
  speedup). Set `linker = "rust-lld.exe"` for Windows in `.cargo/config.toml`
  (per-target — NOT via `RUSTFLAGS`, which invalidates the rust-cache key).
- Add `mold` (Linux) or `sccache` ONLY when measurements show compile/link
  still dominates. With `sccache`, use an S3/GCS backend — the GitHub Actions
  cache backend fights `rust-cache` for the 10 GB repo cache and both evict
  each other (verify with `sccache --show-stats`).

## Structure

- Filter paths with `dorny/paths-filter` feeding job `if:` conditions. Never put
  `paths:` on a job that is a required check — skipped required checks deadlock.
- Make ONE `ci-gate` job the sole required status: `if: always()`, needs all
  jobs, evaluate with `re-actors/alls-green` + `allowed-skips` (a naive gate
  treats skipped jobs as success).
- `fail-fast: false` on the OS matrix; `cancel-in-progress: true` on CI only
  (omit on release workflows mid-upload).

## Supply chain

- SHA-pin third-party actions (e.g. `pinact`); let the dependency updater bump
  the pins. Tag refs are mutable.
- Attest released binaries with `actions/attest-build-provenance` (free for
  public repos; needs `id-token: write`, `attestations: write`).
