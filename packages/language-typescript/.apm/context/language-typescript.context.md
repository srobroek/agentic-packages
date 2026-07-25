---
description: typescript react frontend architecture index — route to component layout, state/data, contract boundary, type safety
---

# TypeScript Architecture Index

Non-obvious structural constraints for TypeScript and React frontends. Keep
existing project choices unless the task is about setup, refactor, or
standardization. Load only the relevant topic:

| Task / keyword | Doc |
|---|---|
| page layout primitive, scroll containment, slot props, barrels | [Component & layout](ts.architecture.component-layout.context.md) |
| server vs client state, query facade, error normalization, IPC seam | [State & data](ts.architecture.state-data.context.md) |
| generated bindings, dispatch seam, envelope unwrap, conformance test | [Contract boundary](ts.architecture.contract-boundary.context.md) |
| generated-union maps, `satisfies` allow-lists, boundary validation | [Type safety & validation](ts.architecture.type-safety-validation.context.md) |

The server side of the contract boundary — command registration, binding export,
and the CI codegen drift gate — lives in the `language-rust` contract boundary
doc.

Opinionated picks (styling/theming, testing, build/tooling) live in the
`language-steering-typescript` package.
