---
description: rust mutation plan approve apply audit side-effect reversibility trash archive TOCTOU CAS gates
---

# Rust Safe Mutation

## Rules

- Model side-effecting operations as a serializable plan of typed items; require explicit review and approval before apply — never apply eagerly.
- Approval is a re-verified token checked at apply time, not a boolean stored at review; a stale token MUST error, never silently proceed.
- Write an audit record per attempted action AND its outcome (applied / refused / failed); the audit trail is append-only and is never replaced by the live progress stream (the stream is additive).
- Default conflict policy fails if the destination exists; NEVER overwrite silently; prefer trash/archive over permanent delete; permanent delete requires a separate explicit consent.
- Revalidate item freshness (size + mtime compare-and-swap) at apply time; a changed item pauses the plan.
- Normalize paths lexically (no `canonicalize`); `lstat` each component; reject symlink/junction traversal unless explicitly enabled per root.
- Run a deterministic per-item gate pipeline (destructive → path → freshness → protection → mutate); each gate emits a typed refusal reason.
- Eventual linkage: when a reference cannot resolve at write time, enqueue it and backfill later via an idempotent guarded update.

## Mutation lifecycle

```mermaid
flowchart TD
  plan["Create plan"] --> review["Review"]
  review --> approve["Approve — token"]
  approve --> gate{"Safety gates"}
  gate -->|pass| mutate["Mutate"]
  gate -->|refuse| ar["Audit: refused"]
  mutate --> aa["Audit: applied / failed"]
```

## Per-item gates

```mermaid
flowchart LR
  g1["Destructive"] --> g2["Path"]
  g2 --> g3["Freshness CAS"]
  g3 --> g4["Protection"]
  g4 --> g5["Execute"]
  g1 -. fail .-> r["Typed refusal + audit reason"]
```
