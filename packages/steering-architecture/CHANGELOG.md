# Changelog

## 1.0.0

### Features

- **steering-architecture:** New opt-in steering package: compose-don't-fork
  as a cross-cutting, language-agnostic design principle. Extend existing
  subsystems through their seams instead of copying, branching, or
  re-implementing them into a variant; keep dispatch/registry/core layers
  case-agnostic; state structural invariants as a verifiable (near-empty)
  diff to the shared surface. Also documents when forking is the honest
  choice.
