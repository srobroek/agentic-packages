---
description: typescript strict tsconfig generated union message map exhaustive assertNever boundary zod typed catalog
---

# TypeScript Type Safety & Validation

## Strict tsconfig baseline

| Option | Value | Why |
|---|---|---|
| `strict` | `true` | Enables the full strict suite |
| `isolatedModules` | `true` | Safe for bundlers; catches re-export-only files |
| `noUncheckedIndexedAccess` | `true` | Index access returns `T \| undefined` |
| `resolveJsonModule` | `true` | Enables typed JSON imports |

- Share one `tsconfig.base.json` at the workspace root; each package extends it and overrides only environment specifics (`lib`, `target`, `module`).

## Generated union as the gating type

- Derive a string-literal union from the authoritative source (error codes, command names, route keys, message ids).
- Map off it via `Record<Union, () => string>` (exhaustive — a new variant is a compile error until added) or `Partial<Record<…>>` (override a subset).
- Runtime allow-lists stay in sync via `as const satisfies readonly Union[]`.

## Runtime boundary validation

- Apply a schema validator (e.g. zod, valibot, arktype) **only** at trust boundaries: external HTTP/IPC responses typed `unknown`, query-param / form input parsing, config files read from disk.
- Pass typed internal values through without re-parsing.

## Exhaustive switch helper

```ts
function assertNever(x: never): never {
  throw new Error(`Unhandled variant: ${String(x)}`);
}
// switch default: assertNever(action.type) → new variant is a compile error
```

## Typed message catalogs

- Key error messages, UI copy, and notifications off the generated union.
- Missing or mistyped keys fail at **build time**, not at runtime.
- A runtime i18n library (e.g. Paraglide, i18next, react-intl) is an optional complement — not a prerequisite for type safety.
