---
description: typescript react frontend architecture index — route to component layout, state/data, contract boundary, type safety
---

# TypeScript Architecture Index

Structural conventions for TypeScript and React frontends. Keep existing project
choices unless the task is about setup, refactor, or standardization. Load only
the relevant topic:

| Task / keyword | Doc |
|---|---|
| component hierarchy, page layout, feature folder, slot props, container/presentational | [Component & layout](ts.architecture.component-layout.context.md) |
| server vs client state, query keys, cache invalidation, error normalization, IPC seam | [State & data](ts.architecture.state-data.context.md) |
| generated bindings, dispatch seam, envelope unwrap, runtime drift validation, conformance test | [Contract boundary](ts.architecture.contract-boundary.context.md) |
| strict tsconfig, generated-union maps, assertNever, boundary zod, typed message catalog | [Type safety & validation](ts.architecture.type-safety-validation.context.md) |

These have server-side counterparts — see the `language-rust` contract boundary
doc (generated-surface authority, validate-at-boundary, mock != real-stack).

Opinionated picks (styling/theming, testing, build/tooling) live in the
`language-steering-typescript` package.
