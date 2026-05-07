---
description: Quality analysis CLI tools for dead code, dependencies, and metrics
applyTo: "**/*"
---

## Dead Code & Dependency Analysis

- **knip** (JS/TS): `npx knip` — finds unused exports, files, dependencies, types.
  Run before major refactors to identify safe deletion candidates.

- **madge** (JS/TS): `npx madge --circular src/` — detects circular dependencies.
  Use when import cycles cause runtime issues or make code hard to reason about.

## Code Statistics

- **scc**: `scc .` — fast line counts, complexity estimates by language.
  Use when asked about codebase size, language distribution, or complexity metrics.

## Structural Patterns

- **ast-grep** (`sg`): structural code search via AST patterns.
  `sg -p 'console.log($$$)' --lang typescript` — find all console.log calls.
  Use for finding anti-patterns, deprecated API usage, or refactor candidates.
