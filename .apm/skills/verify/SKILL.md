---
name: verify
description: Use for a final local verification pass across the repo before handoff, commit, or PR.
---

# Verify

## Preferred Flow

1. Run `scripts/verify.sh`.
2. Report what ran, what was skipped, and what failed.
3. Distinguish environment gaps (missing tool, no config) from real code issues.
4. If the repo is polyglot, explain which checks were selected and why.

## Steering

- Prefer project-native commands (`package.json` scripts, `Makefile`, `justfile`) over guessed generic fallbacks.
- Do not claim coverage for checks that were skipped or unavailable.
- Keep the report concrete: command, exit code, failure summary.
- The agent MUST NOT silently swallow failures -- every non-zero exit gets reported.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/verify.sh` | Polyglot verify runner (detects languages, runs checks) |
