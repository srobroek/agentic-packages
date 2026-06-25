# Changelog

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
