---
description: TypeScript monorepo pnpm workspace tsconfig layering eslint flat config formatter gate task runner ci quality
---

# TypeScript Build & Tooling

## pnpm Workspaces

| Pattern | Guidance |
|---------|----------|
| **Root layout** | Keep root private (no product code); add `packageManager` field pinning version; define `packages` glob for auto-discovery. |
| **Internal deps** | Use `workspace:*` protocol for cross-package imports; rely on symlink resolution, not publishing. |
| **Scripts** | Run cross-package via `pnpm -r --if-present <script>` — packages opt in by defining the script; avoids error when some members lack a target. |

## Type Checking & Bundling

- Type-checking (`tsc --noEmit`) runs independently of bundling (Vite, esbuild, etc.) via a dedicated `typecheck` script that surfaces type errors before build.
- tsconfig inheritance: child packages extend a base root config with package-local overrides (e.g. `lib` vs `module` targets).

## ESLint (Flat Config)

- Flat config (`eslint.config.mjs/ts`); specify `parserOptions.projectService` + `tsconfigRootDir` for type-aware rules.
- Exclude generated dirs (`dist`, `build`, `.next`, etc.) and lock files; document each suppress/override with an inline rationale comment.

## Formatting

- Enforce one formatter (e.g. Prettier, Biome, dprint) on `.ts`, `.tsx`, `.js`, `.jsx` in the lint gate, run in CI so local and remote results match — prevents style drift from becoming review noise.

## Task Runner & CI Aggregation

| Phase | Example targets | Notes |
|-------|-----------------|-------|
| **Cheap** | `format --check`, `lint` | Run first (no I/O, quick feedback). |
| **Medium** | `typecheck` | Type-aware rules; gates type safety before unit tests. |
| **Expensive** | `test:unit`, `test:integration` | Run only after formatting, linting, and type-checking pass. |
| **Aggregate** | `check` target chains all above | A repo-wide runner (e.g. `just check`, `mise run check`, `make check`) defines the sequence once; CI mirrors `check` exactly so local and remote failures align. |

## Code Intelligence Tools

- `knip` — find unused exports & dependencies (advisory; decide per project whether to gate).
- `madge` — detect circular dependencies (advisory review aid).
- `ast-grep` — structural pattern matching (advisory; use for bulk refactoring validation).

## See also

- [`typescript.tooling.context.md`](typescript.tooling.context.md) — tool versions, Prettier/Biome/dprint selection, ESLint plugin choices.
- [`typescript.libraries.context.md`](typescript.libraries.context.md) — dependency selection, peer-version alignment, framework conventions.
