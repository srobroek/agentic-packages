# TypeScript and JavaScript Steering Index

Opinionated TypeScript and JavaScript defaults. Keep existing project choices
unless the task is explicitly about setup, migration, or standardization. Load
only the relevant topic:

- [Styling and theming](typescript.styling-theming.context.md) -- two-layer CSS
  tokens, data-theme theming, density axis, component naming
- [Testing](typescript.testing.context.md) -- layered pyramid, jsdom shims, IPC
  DI override, conformance test, Playwright split, CI drift gate
- [Build and tooling](typescript.build-tooling.context.md) -- pnpm workspace,
  tsconfig layering, flat ESLint, formatter gate, task runner mirrors CI

Structural architecture conventions (component layout, state/data, contract
boundary, type safety) live in the `language-typescript` package.
