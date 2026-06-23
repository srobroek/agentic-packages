---
description: rust architecture conventions index — route to crate boundaries, domain modeling, contract boundary, safe mutation
---

# Rust Architecture Index

Structural conventions for organizing a Rust project. Keep existing project
choices unless the task is about setup, refactor, or standardization. Load only
the relevant topic:

| Task / keyword | Doc |
|---|---|
| crate split, dependency direction, monorepo layout, workspace, `lib.rs` facade | [Crate boundaries](rust.architecture.crate-boundaries.context.md) |
| newtype, value object, smart constructor, state machine, port trait, identity | [Domain modeling](rust.architecture.domain-modeling.context.md) |
| DTO boundary, contract envelope, generated bindings, codegen, IPC casing | [Contract boundary](rust.architecture.contract-boundary.context.md) |
| plan/approve/apply, audit, reversible side effects, CAS, TOCTOU, trash | [Safe mutation](rust.architecture.safe-mutation.context.md) |

Opinionated picks (persistence, workspace/CI, error model) live in the
`language-steering-rust` package.
