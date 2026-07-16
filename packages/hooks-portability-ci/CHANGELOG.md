# Changelog

## [0.4.0](https://github.com/srobroek/agentic-packages/compare/hooks-portability-ci--v0.3.0...hooks-portability-ci--v0.4.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [0.3.0](https://github.com/srobroek/agentic-packages/compare/hooks-portability-ci-v0.2.0...hooks-portability-ci--v0.3.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/hooks-portability-ci-v0.1.0...hooks-portability-ci-v0.2.0) (2026-06-26)


### Features

* add secrets-scan, dep-audit CI, and codex-hook-contract packages ([#374](https://github.com/srobroek/agentic-packages/issues/374)) ([036efaa](https://github.com/srobroek/agentic-packages/commit/036efaa29b7133a73fad0b3aa652d8d952c7981d))


### Bug Fixes

* co-locate skill scripts so they resolve after install ([#376](https://github.com/srobroek/agentic-packages/issues/376)) ([1bb71cc](https://github.com/srobroek/agentic-packages/commit/1bb71ccac2ac14992506bddf11f0ae0ff5db5d0d))

## 0.1.0

### Features

* Initial release: on-demand CI gate that lints shipped hook scripts for the
  portability failure modes surfaced by the Phase-1/Phase-2 audits.
  `scripts/portability-check.sh [dir]` discovers every `*.sh` under
  `*/scripts/` and `*/hooks` paths (defaulting to `packages/`) and runs three
  checks per script: a bash 3.2 parse via `/bin/bash -n` plus a `mapfile`/
  `readarray` grep (bash-4 runtime builtins that parse but exit 127 on 3.2);
  a GNU-only sed/grep scan (`\b` word boundaries in sed, `+?`/`*?` lazy
  quantifiers in sed/grep that BSD tooling rejects), skipping comment lines;
  and a string-form `tool_input` payload probe (wall-clock bounded) that
  asserts the script does not crash jq with "Cannot index string ...". Prints a
  per-failure summary and exits non-zero on any failure so it can gate CI.
  Portable to bash 3.2.57 + BSD sed/grep (stock macOS).
