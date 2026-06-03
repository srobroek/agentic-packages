---
name: typescript-quality
description: Use to run TypeScript or JavaScript format, lint, type-check, and test commands.
---

# TypeScript Quality

## Preferred Flow

1. Run `scripts/check.sh`.
2. If issues are mechanical (formatting, auto-fixable lint rules), run `scripts/fix.sh`.
3. Re-run `scripts/check.sh` to confirm fixes.
4. When the agent needs language-level design guidance or framework/library-specific docs, LOAD references/idioms.md.

## Tooling Preference

- Prefer project-native tooling if defined in `package.json` scripts
- Otherwise prefer:
  - `biome` for formatting and linting
  - `eslint` as fallback linter
  - `tsc --noEmit` for type checking

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/check.sh` | Run all checks (lint, typecheck, test) |
| `scripts/fix.sh` | Apply mechanical fixes (format, auto-fix lint) |

## References

When making API design decisions or choosing between framework/library alternatives, LOAD references/idioms.md.
