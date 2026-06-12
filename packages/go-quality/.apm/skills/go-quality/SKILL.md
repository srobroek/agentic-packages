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

Order the scripts implement:

1. `gofmt` for formatting (always)
2. `golangci-lint run` only when installed (skipped otherwise)
3. `go test ./...`

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/check.sh` | Run all checks (gofmt -l, golangci-lint if installed, go test) |
| `scripts/fix.sh` | Apply formatting only (gofmt -w) |

`fix.sh` is narrower than `check.sh`: it only formats. Lint findings and test
failures need manual fixes. Re-run `check.sh` after `fix.sh`.

## References

When making API design decisions or choosing between package alternatives, LOAD references/idioms.md.
