---
name: go-quality
description: Use to run Go format, lint, and test checks with the project toolchain.
---

# Go Quality

## Preferred Flow

1. Run `scripts/check.sh`.
2. If issues are formatting-only, run `scripts/fix.sh`.
3. Re-run `scripts/check.sh` to confirm fixes.
4. When the agent needs language-level design guidance or package-specific docs, LOAD references/idioms.md.

## Tooling Preference

- `gofmt` / `goimports` for formatting
- `golangci-lint` when available
- `go test ./...`

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/check.sh` | Run all checks (fmt, lint, test) |
| `scripts/fix.sh` | Apply formatting fixes (gofmt -w, goimports -w) |

## References

When making API design decisions or choosing between package alternatives, LOAD references/idioms.md.
