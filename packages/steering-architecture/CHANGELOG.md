# Changelog

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/steering-architecture--v1.0.0...steering-architecture--v1.1.0) (2026-07-03)


### Features

* add steering-architecture package (compose over fork) ([#460](https://github.com/srobroek/agentic-packages/issues/460)) ([7b3a91f](https://github.com/srobroek/agentic-packages/commit/7b3a91fce332182ec0efa3111edb511216bd3a7e))

## 1.0.0

### Features

- **steering-architecture:** New opt-in steering package: compose-don't-fork
  as a cross-cutting, language-agnostic design principle. Extend existing
  subsystems through their seams instead of copying, branching, or
  re-implementing them into a variant; keep dispatch/registry/core layers
  case-agnostic; state structural invariants as a verifiable (near-empty)
  diff to the shared surface. Also documents when forking is the honest
  choice.
