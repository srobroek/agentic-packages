# Changelog

## 0.1.0

### Features

- **hooks-attribution-guard:** PreToolUse hook (Claude + Codex) that blocks
  `git commit` invocations carrying AI authorship attribution and exits 2 with
  an actionable message. Detects Co-Authored-By trailers naming
  Claude/Anthropic/`noreply@anthropic`, "Generated with/by Claude/AI" phrases,
  "AI-assisted"/"AI-generated" authorship qualifiers, and Claude Code trailer
  URLs. Patterns are scoped to attribution constructs so prose that merely
  mentions AI/Claude (e.g. "fix AI model loading bug") is allowed. Uses the
  type-checked string-form `tool_input` idiom and the proven `git commit`
  anchor (also matches `git -C <path> commit`). Portable to bash 3.2 + BSD grep.
