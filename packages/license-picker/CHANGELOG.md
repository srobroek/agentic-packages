# Changelog

## [1.3.0](https://github.com/srobroek/agentic-packages/compare/license-picker--v1.2.0...license-picker--v1.3.0) (2026-07-22)


### Features

* make Codex and Claude APM integration target-aware ([#643](https://github.com/srobroek/agentic-packages/issues/643)) ([83fe64b](https://github.com/srobroek/agentic-packages/commit/83fe64b7bf119cb91aaea3f3d7932b2781a45eee))

## [1.2.0](https://github.com/srobroek/agentic-packages/compare/license-picker--v1.1.0...license-picker--v1.2.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/license-picker--v1.0.0...license-picker--v1.1.0) (2026-07-14)


### Features

* add license-picker skill and steering-licensing package ([#530](https://github.com/srobroek/agentic-packages/issues/530)) ([9ad3395](https://github.com/srobroek/agentic-packages/commit/9ad33956bede48b2c5676dbb640af8ab13c27fba))
* **user-journeys:** service-agnostic user-journey lifecycle package ([#532](https://github.com/srobroek/agentic-packages/issues/532)) ([5799976](https://github.com/srobroek/agentic-packages/commit/57999765c239a322883d662545ab1b2739f19792))


### Refactors

* fold steering-licensing into license-picker skill ([#531](https://github.com/srobroek/agentic-packages/issues/531)) ([c06d7e2](https://github.com/srobroek/agentic-packages/commit/c06d7e2e4886d98c785d0d28f888072a8f3e0e93))

## 1.0.0 (2026-07-14)

### Added
- Interactive license picker skill with structured question flow
- Decision matrix mapping project type + threat model → license
- Common contradictions reference (surfaces conflicting goals)
- Ecosystem norms reference (Rust, Python, TypeScript, Go, C/embedded)
- Validation phase (SPDX, static linking, output contamination checks)
- Implementation phase (LICENSE file, manifest fields, headers, CLA setup)
