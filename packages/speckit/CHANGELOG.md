# Changelog

## [0.5.0](https://github.com/srobroek/agentic-packages/compare/speckit-v0.4.0...speckit-v0.5.0) (2026-06-25)


### Features

* **speckit:** adopt memory-md 1.x across speckit, dag-hooks, and steering ([#355](https://github.com/srobroek/agentic-packages/issues/355)) ([450f1f3](https://github.com/srobroek/agentic-packages/commit/450f1f36ae8c9e42562e9270c414da34dd55dbfb))

## [0.4.0](https://github.com/srobroek/agentic-packages/compare/speckit-v0.3.0...speckit-v0.4.0) (2026-06-24)


### Features

* **speckit:** add roadmap extension to the required set ([#353](https://github.com/srobroek/agentic-packages/issues/353)) ([5bb3b73](https://github.com/srobroek/agentic-packages/commit/5bb3b7394564efc878a57ead83e2b11a755dbf52))

## [0.3.0](https://github.com/srobroek/agentic-packages/compare/speckit-v0.2.0...speckit-v0.3.0) (2026-06-24)


### Features

* **speckit:** checklist-after-tasks reorder, memory-md default, agent-assign + hook fixes ([56ceefc](https://github.com/srobroek/agentic-packages/commit/56ceefc09ae0c8e2e2f46977478f188daeb4fa7a))
* **speckit:** install memory-md by default [skip tests] ([0acdf42](https://github.com/srobroek/agentic-packages/commit/0acdf42bdeb16ba792dd36c2d509882f748fe913))

## [0.2.0](https://github.com/srobroek/agentic-packages/compare/speckit-v0.1.2...speckit-v0.2.0) (2026-06-24)


### Features

* **speckit:** align with spec-kit 0.11.x — setup ownership, DAG node fix, converge ([8b2a51b](https://github.com/srobroek/agentic-packages/commit/8b2a51b3faa914ae86bbb6944ba62e408ca2e040))
* **speckit:** own end-to-end spec-kit setup; align with spec-kit 0.11.x [skip tests] ([67e1f35](https://github.com/srobroek/agentic-packages/commit/67e1f3568bb8cebd47aca1a51ebedc4239e4613f))

## [0.1.2](https://github.com/srobroek/agentic-packages/compare/speckit-v0.1.1...speckit-v0.1.2) (2026-06-19)


### Bug Fixes

* **speckit-setup:** register extension commands for the requested integration ([#309](https://github.com/srobroek/agentic-packages/issues/309)) ([c67ee50](https://github.com/srobroek/agentic-packages/commit/c67ee50357cab8a982e28960e63b6738af93368c))

## [0.1.1](https://github.com/srobroek/agentic-packages/compare/speckit-v0.1.0...speckit-v0.1.1) (2026-06-12)


### Bug Fixes

* **speckit:** guard hardening, align workflow docs with node store ([#294](https://github.com/srobroek/agentic-packages/issues/294)) ([99de83c](https://github.com/srobroek/agentic-packages/commit/99de83c82eed004273f7f3774bb5da3cad96940b))

## [0.1.0](https://github.com/srobroek/agentic-packages/compare/speckit-v0.0.1...speckit-v0.1.0) (2026-06-02)


### Features

* migrate hooks into packages, remove dead scripts, baseline 0.0.1 [skip tests] ([912cd0c](https://github.com/srobroek/agentic-packages/commit/912cd0ce7868e0406dd8ac0659320b1fbc577319))
* publish standalone mcp packages ([3145100](https://github.com/srobroek/agentic-packages/commit/31451002a7ae874e59c7f11868dd039ba597730c))
* **speckit-dag-hooks:** self-contained Python dispatcher + JSON nodes [skip tests] ([d46f465](https://github.com/srobroek/agentic-packages/commit/d46f465b7e056ca0d1689362f3d192c8819da1a9))
* **speckit:** add code-review and security-review steps to post-implementation DAG ([3ea8d20](https://github.com/srobroek/agentic-packages/commit/3ea8d2054e0231934cbf3054704b08c9d7127dbb))
* **speckit:** add per-command DAG hook dispatcher with hard/soft steering ([e6a6cf8](https://github.com/srobroek/agentic-packages/commit/e6a6cf8fe2d6af1c6d44360781d119d8bfed4b22))
* **speckit:** add workflow overview instruction with DAG, human gating, and command reference [skip tests] ([2b356e0](https://github.com/srobroek/agentic-packages/commit/2b356e0f436bba813f9dfea9888ff67768337449))
* **speckit:** reorder DAG — critique + security-review after tasks, enforce mandatory steps ([37df18e](https://github.com/srobroek/agentic-packages/commit/37df18ee0663ece1951e951b9c9be788fbefaec9))


### Bug Fixes

* compile claude steering in setup guidance ([32d6fe3](https://github.com/srobroek/agentic-packages/commit/32d6fe31943fae7c274a8cf5365d23d0ec24269a))
* **speckit:** agent-assign is a specify extension, not missing — restore deprecation note [skip tests] ([22c4dd4](https://github.com/srobroek/agentic-packages/commit/22c4dd4092b686da85de591e6af18d371e14a5a0))
* **speckit:** Codex hook references .agents/skills/, not .claude/ ([a0aba9d](https://github.com/srobroek/agentic-packages/commit/a0aba9d9a4214737bda494217cf5b13677a1a887))
* **speckit:** correct implement deprecation — agent-assign is the replacement, not tinyspec [skip tests] ([d968741](https://github.com/srobroek/agentic-packages/commit/d9687411a983aa47bb29eafd533cb589e2bb07fc))
* **speckit:** DAG hooks never fire — glob/regex mismatch + hyphen/dot normalisation ([5376ef9](https://github.com/srobroek/agentic-packages/commit/5376ef99bf984c4e51513645552cd2f63d4209df))
* **speckit:** dispatcher resolves nodes/ from apm_modules cache ([b9b4231](https://github.com/srobroek/agentic-packages/commit/b9b4231e47d8d8789c71266eb624f6cd11d26968))
* **speckit:** downgrade sync and sync-conflicts agents from opus to sonnet on Claude ([87e47f4](https://github.com/srobroek/agentic-packages/commit/87e47f43446a3597f0880e9bf562d778c212eb8d))
* **speckit:** hook command path must be project-root-relative ([974ec1e](https://github.com/srobroek/agentic-packages/commit/974ec1e3fd2311c9a709d8db3ba1e20ae8a77bca))
* **speckit:** remove invalid Skill() if patterns from hooks — Skill is not a permission rule type ([a868530](https://github.com/srobroek/agentic-packages/commit/a86853092921f0b44e1eec34a1a953ea42e46d57))
* **speckit:** remove invalid tool restrictions from speckit agents ([4a5dc40](https://github.com/srobroek/agentic-packages/commit/4a5dc403f75cebd036b87f2e48dfce802ebebe7a))
* **speckit:** remove stale generated context + duplicate docs-specs instruction [skip tests] ([969c39d](https://github.com/srobroek/agentic-packages/commit/969c39da29d09686aa1fbaf2960efe8b10e34a09))


### Refactors

* APM-native bundles + marketplace + per-package release-please ([5e1a3e8](https://github.com/srobroek/agentic-packages/commit/5e1a3e8b6ba8039de7b737fe9e622e7bc775a43e))
* promote apm wrappers to packages ([bbe7484](https://github.com/srobroek/agentic-packages/commit/bbe748422b5f7dcc4ffbfe8354d21dc171c52add))
* **speckit:** package DAG dispatcher + nodes as a skill ([a5ecc34](https://github.com/srobroek/agentic-packages/commit/a5ecc34a2d8c7f3148c6bf337ad4244cde541978))
* **speckit:** remove root duplicates; extract workflow to steering-speckit [skip tests] ([7ff5284](https://github.com/srobroek/agentic-packages/commit/7ff52846cdc17386f83ceb5e6de187196bb0f3de))
* **steering:** split baseline into 3 opt-in packages; extract speckit hooks [skip tests] ([9a19504](https://github.com/srobroek/agentic-packages/commit/9a195043c208f8d03d462507a2720d66e7addc2c))
