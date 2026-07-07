# Changelog

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/cmux--v0.2.0...cmux--v1.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* pin all external #main refs to SHAs; internal subpath refs to semver ranges

### Chores

* pin all external #main refs to SHAs; internal subpath refs to semver ranges ([7b32fc1](https://github.com/srobroek/agentic-packages/commit/7b32fc13d3eb75710e7c40beb2d30672d0d9dc02))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/cmux--v0.1.0...cmux--v0.2.0) (2026-07-03)


### Features

* **cmux:** add cmux terminal skills bundle ([#462](https://github.com/srobroek/agentic-packages/issues/462)) ([a11c3d4](https://github.com/srobroek/agentic-packages/commit/a11c3d43ba920948d3d347fdffb0d8d87724172f))

## 0.1.0

### Features

* Initial `cmux` bundle package: vendors the user-facing manaflow-ai/cmux skills
  (core control, workspace, customization, settings, diagnostics, socket policy,
  Ghostty, keyboard shortcuts, shared behavior) so agents can drive and configure
  the cmux terminal via its socket CLI. Contributor skills are omitted.
