# Changelog

## 0.1.0

### Features

- **secrets-scan:** New hybrid package (skill + pre-commit hook) closing the gap
  where commit steering says to check for secrets but ships no tool. `scan.sh`
  auto-detects a scanner on PATH (gitleaks preferred, then trufflehog), scans the
  staged diff (`--staged`, default) or the working tree (`--working`), redacts
  matches, and exits with a stable contract: 0 clean, 1 finding, 2 no scanner.
- **secrets-scan:** PreToolUse hook (Claude + Codex) on `git commit` runs the
  scanner over the staged diff and blocks the commit (exit 2) with an actionable
  message and a documented bypass when a secret is found. When no scanner is
  installed it WARNs and allows the commit -- missing tooling never blocks work.
  Honors a `SECRETS_SCAN_SKIP=1` bypass (env var or inline command prefix). Uses
  the type-checked string-form `tool_input` idiom and the proven `git commit`
  anchor (also matches `git -C <path> commit`). Portable to bash 3.2 + BSD grep.
