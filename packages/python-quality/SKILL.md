---
name: python-quality
description: Use to run Python format, lint, type-check, and test commands with the project toolchain.
---

# Python Quality

## Preferred Flow

1. Run `scripts/check.sh`.
2. If issues are mechanical (formatting, import sorting), run `scripts/fix.sh`.
3. Re-run `scripts/check.sh` to confirm fixes.
4. Read `references/idioms.md` when the agent needs language-level design guidance or library-specific docs.

## Tooling Preference

- Prefer `ruff` for linting and formatting
- Prefer `pyright` for type checking when available
- Prefer `pytest` for tests when present

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/check.sh` | Run all checks (ruff, pyright, pytest) |
| `scripts/fix.sh` | Apply mechanical fixes (ruff format, ruff --fix) |

## References

Read `references/idioms.md` when making API design decisions or choosing between package alternatives.
