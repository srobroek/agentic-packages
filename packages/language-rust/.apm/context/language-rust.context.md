---
description: rust architecture conventions index — route to crate boundaries, domain modeling, contract boundary, safe mutation
---

# Rust Architecture Index

Non-obvious structural constraints for organizing a Rust project. Keep existing
project choices unless the task is about setup, refactor, or standardization.
Load only the relevant topic:

| Task / keyword | Doc |
|---|---|
| crate split, monorepo layout, `lib.rs` facade | [Crate boundaries](rust.architecture.crate-boundaries.context.md) |
| error scope, deterministic identity, newtype wire format | [Domain modeling](rust.architecture.domain-modeling.context.md) |
| generated bindings, codegen drift gate, IPC casing and invoke names | [Contract boundary](rust.architecture.contract-boundary.context.md) |
| plan/approve/apply, audit, CAS, TOCTOU, path traversal | [Safe mutation](rust.architecture.safe-mutation.context.md) |

Opinionated picks (persistence, workspace, CI, Tauri) live in the
`language-steering-rust` package.
