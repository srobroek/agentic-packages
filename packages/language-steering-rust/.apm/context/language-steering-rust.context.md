# Rust Steering Index

Opinionated Rust defaults. Keep existing project choices unless the task is
explicitly about setup, migration, or standardization. Load only the relevant
topic:

- [CI](rust.ci.context.md) — cache keys, gate structure, supply chain
- [Persistence](rust.persistence.context.md) — DB-as-record, repository boundary,
  CAS-in-transaction, numbered migrations
- [Workspace](rust.workspace.context.md) — workspace lints, feature-gated dev
  surface, dev-dependency isolation, layered tests
- [Errors](rust.errors.context.md) — error-code registry, edge mapping, rich
  error envelope, append-only audit
- [Tauri apps](rust.tauri.context.md) — load ONLY for Tauri desktop work
  (bundles, releases, updater, signing)

Structural architecture conventions (crate boundaries, domain modeling, contract
boundary, safe mutation) live in the `language-rust` package.
