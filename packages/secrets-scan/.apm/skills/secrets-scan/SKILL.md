---
name: secrets-scan
description: Scan staged changes or the working tree for committed secrets (API keys, tokens, credentials) using gitleaks or trufflehog. Use when the user asks to scan for secrets, check for leaked credentials before committing, audit the diff for keys, or verify nothing sensitive is being committed.
---

# Secrets Scan

Run a secret scanner over the staged diff (default) or the working tree and
report any findings. Backs the pre-commit hook that gates `git commit`.

## Preferred Flow

1. Run `scripts/scan.sh` to scan the staged diff. Use `scripts/scan.sh --working`
   to scan the working tree instead.
2. Report what scanner ran, the mode, and every finding (file + redacted match).
3. If a finding is real, tell the user to remove the secret from the staged
   files and rotate the credential -- a leaked key must be assumed compromised.
4. If it is a false positive, point to the scanner's inline allow mechanism.

## Scanner Selection

The script auto-detects a scanner on PATH, preferring `gitleaks`, then
`trufflehog`. If neither is installed it warns and exits with a tooling-gap
code -- it never reports a clean scan it did not actually run.

| Scanner | Staged scan | Working-tree scan |
|---------|-------------|-------------------|
| gitleaks | `gitleaks protect --staged --redact` | `gitleaks detect --no-git --redact` |
| trufflehog | `trufflehog filesystem --fail` over staged files | `trufflehog filesystem --fail .` |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Clean: a scanner ran and found nothing |
| 1 | A scanner ran and flagged a potential secret |
| 2 | No scanner installed (gitleaks/trufflehog both absent) |

## Pre-Commit Hook

This package also installs a PreToolUse hook on `git commit`. On a finding it
blocks the commit (exit 2) with an actionable message. When no scanner is
installed it WARNs and allows the commit -- missing tooling never blocks work.

## Bypass

For a deliberate, audited exception, prefix the commit with the documented
escape hatch (you accept the risk):

```sh
SECRETS_SCAN_SKIP=1 git commit -m "..."
```

## Rules

- Never claim a clean scan when no scanner ran. Surface the tooling gap instead.
- Treat any flagged credential as compromised: remove it AND rotate it.
- Do not weaken the scanner config to silence a real finding -- only use inline
  allows for genuine false positives.
