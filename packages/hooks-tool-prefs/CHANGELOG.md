# Changelog

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/hooks-tool-prefs-v0.2.1...hooks-tool-prefs-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* mcp-package-version no longer ships the package-file-warn or pkg-version-warn hooks. Installers that relied on those hooks should install hooks-package-file-guard / hooks-pkg-version-warn (or the dependency-quality bundle) instead.
* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))
* split dependency tooling into independent packages + dependency-quality bundle ([#370](https://github.com/srobroek/agentic-packages/issues/370)) ([03d50a5](https://github.com/srobroek/agentic-packages/commit/03d50a5db3a1572fbe36a4ac1bc1e6877cd96ade))


### Bug Fixes

* **phase-1:** guard bypasses, bash-3.2/BSD portability, crashes, bundle pins + tests ([#360](https://github.com/srobroek/agentic-packages/issues/360)) ([b0c9106](https://github.com/srobroek/agentic-packages/commit/b0c91064313282a4265b9b0b8fb779f00afecd90))

## [0.2.1](https://github.com/srobroek/agentic-packages/compare/hooks-tool-prefs-v0.2.0...hooks-tool-prefs-v0.2.1) (2026-06-12)


### Bug Fixes

* **hooks-tool-prefs:** scan full pipelines, runtime-neutral wording ([#278](https://github.com/srobroek/agentic-packages/issues/278)) ([e26c475](https://github.com/srobroek/agentic-packages/commit/e26c4757ddb4699aebb04ffe850394726ccf6246))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/hooks-tool-prefs-v0.1.0...hooks-tool-prefs-v0.2.0) (2026-06-04)


### Features

* **hooks,steering:** add granular global guard hooks + pragmatic steering [skip tests] ([#248](https://github.com/srobroek/agentic-packages/issues/248)) ([11d60ed](https://github.com/srobroek/agentic-packages/commit/11d60ed5e9c4b342742e421995beebde7a157fa0))
