---
name: rust-quality
description: Use to run Rust format, lint, and test checks with the project toolchain.
---

# Rust Quality

## Preferred Flow

1. Run `scripts/check.sh`.
2. If issues are mechanical (formatting, simple clippy lints), run `scripts/fix.sh`.
3. Re-run `scripts/check.sh` to confirm fixes.
4. Read `references/idioms.md` when the agent needs API-design or library-specific guidance.

## Tooling Preference

- `cargo fmt --check`
- `cargo clippy -- -D warnings`
- `cargo test`

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/check.sh` | Run all checks (fmt, clippy, test) |
| `scripts/fix.sh` | Apply mechanical fixes (fmt, clippy --fix) |

## References

Read `references/idioms.md` when making API design decisions or choosing between crate alternatives.
