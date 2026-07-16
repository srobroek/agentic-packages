# Changelog

## [1.2.0](https://github.com/srobroek/agentic-packages/compare/resume-cv--v1.1.0...resume-cv--v1.2.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/resume-cv-v1.0.0...resume-cv--v1.1.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/resume-cv-v0.1.0...resume-cv-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))

## 0.1.0

### Refactors

* rename `resume` → `resume-cv` to resolve the namespace collision with
  `resume-session` (CV/career bundle vs. coding-session resume); pin the two
  third-party deps (`resume-tailoring-skill`, `ResumeSkills`) to immutable
  commit SHAs since neither upstream publishes tags.

---

History prior to the rename (as `resume`):

## [0.1.0](https://github.com/srobroek/agentic-packages/compare/resume-v0.0.1...resume-v0.1.0) (2026-06-02)

### Features

* migrate hooks into packages, remove dead scripts, baseline 0.0.1 [skip tests] ([912cd0c](https://github.com/srobroek/agentic-packages/commit/912cd0ce7868e0406dd8ac0659320b1fbc577319))

### Refactors

* promote apm wrappers to packages ([bbe7484](https://github.com/srobroek/agentic-packages/commit/bbe748422b5f7dcc4ffbfe8354d21dc171c52add))
