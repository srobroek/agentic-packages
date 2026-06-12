---
name: python-quality
description: Use to run Python format, lint, type-check, and test commands with the project toolchain.
---

# Python Quality

## Preferred Flow

1. Run `scripts/check.sh`.
2. If issues are mechanical (formatting, import sorting), run `scripts/fix.sh`.
3. Re-run `scripts/check.sh` to confirm fixes.
4. When the agent needs language-level design guidance or library-specific docs, LOAD references/idioms.md.

## Tooling Preference

Order the scripts implement:

1. `ruff check` + `ruff format --check` (always)
2. `pyright` only when installed (skipped otherwise)
3. `pytest` only when installed and `pyproject.toml` or `tests/` exists

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/check.sh` | Run all checks (ruff, pyright if installed, pytest if present) |
| `scripts/fix.sh` | Apply mechanical fixes only (ruff check --fix, ruff format) |

`fix.sh` is narrower than `check.sh`: it only applies auto-fixable lint rules
and formatting. Type errors and test failures need manual fixes. Re-run
`check.sh` after `fix.sh`.

## References

When making API design decisions or choosing between package alternatives, LOAD references/idioms.md.
