# Changelog

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/resume-session-v1.0.0...resume-session--v1.1.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/resume-session-v0.2.1...resume-session-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))


### Bug Fixes

* **phase-1:** guard bypasses, bash-3.2/BSD portability, crashes, bundle pins + tests ([#360](https://github.com/srobroek/agentic-packages/issues/360)) ([b0c9106](https://github.com/srobroek/agentic-packages/commit/b0c91064313282a4265b9b0b8fb779f00afecd90))

## [0.2.1](https://github.com/srobroek/agentic-packages/compare/resume-session-v0.2.0...resume-session-v0.2.1) (2026-06-20)


### Bug Fixes

* **resume-session:** enforce select/confirm stop-gates, repo-root default, and per-session summaries ([#330](https://github.com/srobroek/agentic-packages/issues/330)) ([6976294](https://github.com/srobroek/agentic-packages/commit/69762946aecaa8fb855555c16d28e8ee68b98808))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/resume-session-v0.1.0...resume-session-v0.2.0) (2026-06-20)


### Features

* **resume-session:** add agent session-resume skill ([#325](https://github.com/srobroek/agentic-packages/issues/325)) ([1f9aaf9](https://github.com/srobroek/agentic-packages/commit/1f9aaf953ad27941eadc8375256624d1d53c9f46))

## 0.1.0 (2026-06-20)


### Features

* **resume-session:** discover prior Claude Code and Codex sessions for a repo and resume one from its transcript without loading full history
* **resume-session:** incremental newest-first transcript reader with filtered output, latest plan/todo extraction, and backward paging
