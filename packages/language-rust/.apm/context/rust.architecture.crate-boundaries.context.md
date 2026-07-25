---
description: rust crate layout domain boundary monorepo workspace split adapter facade lib.rs
---

# Rust Crate Boundaries

- Each crate MUST compile without forcing an IO, DB, or UI rebuild. That
  constraint, not file count, decides where a split goes.
- When IO or network creeps into a domain crate, extract it into a sibling
  adapter crate instead of feature-gating it in place.
- `lib.rs` is a thin facade: module declarations and curated re-exports. Logic
  sitting in `lib.rs` is logic that leaked out of the module owning it — push it
  down. Top-level legacy aliases are a migration smell.
- Preserve stable public paths via re-export when splitting an existing crate.
