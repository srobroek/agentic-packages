# Changelog

## 1.0.0 (2026-07-30)


### ⚠ BREAKING CHANGES

* mcp-repomix is removed. Eight external apm.yml files still pin it, including the global ~/.apm/apm.yml, and must drop the dependency before this lands or apm install will fail to resolve it.

### Features

* token-savings package with measured context-cost reduction ([#803](https://github.com/srobroek/agentic-packages/issues/803)) ([14b987e](https://github.com/srobroek/agentic-packages/commit/14b987edb9bcfb2bbcaf6c308af755fcea540f00))


### Bug Fixes

* allow orchestrate to install with Worktrunk 1.x ([18b38cd](https://github.com/srobroek/agentic-packages/commit/18b38cdc5a73b7044980077e62adeb5b6e8f234f))


### Refactors

* drop the mcp-repomix package for the repomix CLI ([#815](https://github.com/srobroek/agentic-packages/issues/815)) ([dc98847](https://github.com/srobroek/agentic-packages/commit/dc988471e6e41fc969bf78cd32ae479b3b2a185c))


### Documentation

* **token-savings:** measure prompt caching, and say where trimming pays ([#816](https://github.com/srobroek/agentic-packages/issues/816)) ([c7b7fab](https://github.com/srobroek/agentic-packages/commit/c7b7fab74de68bbe7633117b17773d52132ba86a))
