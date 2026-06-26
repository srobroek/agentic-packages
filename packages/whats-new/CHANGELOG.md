# Changelog

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
