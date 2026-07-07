# Changelog

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/whats-new--v1.1.0...whats-new--v2.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* Wave 5 — agent output contracts, fleet de-hedge, keyword convention, audit-steering absorbs project-hygiene + optimize-steering

### Features

* Wave 5 — agent output contracts, fleet de-hedge, keyword convention, audit-steering absorbs project-hygiene + optimize-steering ([9cb202d](https://github.com/srobroek/agentic-packages/commit/9cb202d2b76a649dda0489baaeefd61a2e0829e1))


### Refactors

* **agentic:** replace sigil grammar with MUST/DEFAULT/ASK/NOT keywords throughout ([52a8958](https://github.com/srobroek/agentic-packages/commit/52a895874110733cc0f5f11197366659d3fe6074))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/whats-new-v1.0.0...whats-new--v1.1.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/whats-new-v0.1.0...whats-new-v1.0.0) (2026-06-26)


### Features

* add whats-new upgrade-research skill ([#378](https://github.com/srobroek/agentic-packages/issues/378)) ([b330834](https://github.com/srobroek/agentic-packages/commit/b330834182d1dc42e511da1901fd04bc9f333797))
* extend whats-new to services, platforms, and model families ([#379](https://github.com/srobroek/agentic-packages/issues/379)) ([a72e2d8](https://github.com/srobroek/agentic-packages/commit/a72e2d824d55fe8afb0dc31b8ce4789e35bfbaee))


### Chores

* release whats-new and secrets-scan at 1.0.0 ([#382](https://github.com/srobroek/agentic-packages/issues/382)) ([1a153fb](https://github.com/srobroek/agentic-packages/commit/1a153fbbbe8271cfb6856b5638452c95c4c49e34))

## 0.1.0

### Features

* Initial release: on-demand upgrade- & change-research skill. For a named tool,
  CLI, library, framework, runtime, or any dependency — OR a technology, cloud
  service, hosted API, platform, or model family (AWS Bedrock, Anthropic/Claude,
  OpenAI, GCP, Azure, …) — or, with no target, the current repo's dependencies —
  researches what changed between what is in use and the latest, and summarizes
  it as breaking changes, deprecations, new features/capabilities, and fixes
  against a fixed report template. Distinguishes two target kinds: versioned
  software (research a version span) and services/streams (research a dated
  announcement window).
* `scripts/detect.sh`: offline, toolchain-free enumeration of declared
  dependencies and pinned versions across npm/pnpm/yarn, pip/poetry/uv, cargo,
  go, rubygems, and composer (prefers `jq` for JSON manifests, with a
  pure-shell fallback). Used to pick a target when none is named.
* `references/recipes.md`: a programmatic fetch cookbook so the agent resolves
  versions, source repos, changelogs, release notes, and the commit log via
  machine endpoints (`curl`+`jq`, `gh`/`glab`, `git ls-remote`, bare-clone
  `git log`) instead of reading rendered web pages. Host-agnostic git core
  covers GitHub/GitLab/Bitbucket/Codeberg/sr.ht and private remotes; host APIs
  add curated release notes. Honors `GOPROXY=direct` and the crates.io
  user-agent requirement. Step E covers services via machine-readable
  announcement streams: AWS What's-New RSS (per-service title filter), GCP
  per-service Atom feeds, Azure updates RSS, and the Anthropic/OpenAI models
  APIs — with guidance to switch to web-fetch when a vendor's release-notes page
  is client-rendered (JS) rather than scrape an empty shell.
* `references/report-template.md`: the fixed output structure (Breaking changes,
  Deprecations, New features, Fixes, Upgrade notes, Coverage, Sources).
