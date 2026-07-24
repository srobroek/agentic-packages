# Changelog

## [8.1.4](https://github.com/srobroek/agentic-packages/compare/speckit--v8.1.3...speckit--v8.1.4) (2026-07-24)


### Bug Fixes

* **agents:** verdict line is the literal first line — no preamble, no markdown emphasis ([#688](https://github.com/srobroek/agentic-packages/issues/688)) ([0cef5d6](https://github.com/srobroek/agentic-packages/commit/0cef5d6698a0ee7b5f3337ef993a4bf9fb653e9a))

## [8.1.3](https://github.com/srobroek/agentic-packages/compare/speckit--v8.1.2...speckit--v8.1.3) (2026-07-23)


### Bug Fixes

* **agents:** converge Claude effort and Codex reasoning_effort pins ([#663](https://github.com/srobroek/agentic-packages/issues/663)) ([9f149f2](https://github.com/srobroek/agentic-packages/commit/9f149f2cda79e819ce25b37e5eba2ffdd52fd115))

## [8.1.2](https://github.com/srobroek/agentic-packages/compare/speckit--v8.1.1...speckit--v8.1.2) (2026-07-23)


### Bug Fixes

* **agents:** harden isolation and delivery rules for delegated workers ([#657](https://github.com/srobroek/agentic-packages/issues/657)) ([956f6e1](https://github.com/srobroek/agentic-packages/commit/956f6e1615a484746023d8e63085d8f514b07bf7))

## [8.1.1](https://github.com/srobroek/agentic-packages/compare/speckit--v8.1.0...speckit--v8.1.1) (2026-07-22)


### Bug Fixes

* route agent code discovery through Serena ([bf9593c](https://github.com/srobroek/agentic-packages/commit/bf9593c14f5d486af11f2d364e8d5dd66d3b0306))

## [8.1.0](https://github.com/srobroek/agentic-packages/compare/speckit--v8.0.0...speckit--v8.1.0) (2026-07-21)


### Features

* **agents:** preserve model routing in workflow packages ([df86afc](https://github.com/srobroek/agentic-packages/commit/df86afc45f5c6da979e939aba1ed7f5fe2fcbc6a))

## [8.0.0](https://github.com/srobroek/agentic-packages/compare/speckit--v7.0.0...speckit--v8.0.0) (2026-07-21)


### ⚠ BREAKING CHANGES

* **speckit:** remove noisy stop hooks ([#574](https://github.com/srobroek/agentic-packages/issues/574))

### Features

* **speckit:** remove noisy stop hooks ([#574](https://github.com/srobroek/agentic-packages/issues/574)) ([7637119](https://github.com/srobroek/agentic-packages/commit/76371191da9da679e92c99d3b8b6a6b3817065d7))


### Bug Fixes

* stop noisy hook warnings and broken pipes ([#575](https://github.com/srobroek/agentic-packages/issues/575)) ([f9f1acf](https://github.com/srobroek/agentic-packages/commit/f9f1acfabe0e16578f87a9d7a1e3b1b6bd7992b4))

## [7.0.0](https://github.com/srobroek/agentic-packages/compare/speckit--v6.0.0...speckit--v7.0.0) (2026-07-21)


### ⚠ BREAKING CHANGES

* share MCP backends through 1MCP

### Features

* share MCP backends through 1MCP ([4896601](https://github.com/srobroek/agentic-packages/commit/4896601ca0326762493f340526a97a341b98e24a))

## [6.0.0](https://github.com/srobroek/agentic-packages/compare/speckit--v5.1.2...speckit--v6.0.0) (2026-07-20)


### ⚠ BREAKING CHANGES

* retire speckit-dag-hooks; formula resolves from user-level ~/.beads/formulas

### Features

* retire speckit-dag-hooks; formula resolves from user-level ~/.beads/formulas ([5607757](https://github.com/srobroek/agentic-packages/commit/5607757b1c6b8c777fc9ace5ebb5306e8b3264d8))

## [5.1.2](https://github.com/srobroek/agentic-packages/compare/speckit--v5.1.1...speckit--v5.1.2) (2026-07-20)


### Bug Fixes

* **probes:** unknown is not clean, and count claims for the git user ([13660e9](https://github.com/srobroek/agentic-packages/commit/13660e9f66dcf181b031b24198a6c696c1b2f3c1))
* **speckit:** quote bd query values and pin JSON shape in hooks ([5cd1d15](https://github.com/srobroek/agentic-packages/commit/5cd1d15c3afb94d6bfeaaeebd573225b4499e2bc))

## [5.1.1](https://github.com/srobroek/agentic-packages/compare/speckit--v5.1.0...speckit--v5.1.1) (2026-07-20)


### Bug Fixes

* PR guidance names the branch the pull request is actually from ([3bb818b](https://github.com/srobroek/agentic-packages/commit/3bb818b5272f0fbb9c69e48db1edce60e9a4cadd))

## [5.1.0](https://github.com/srobroek/agentic-packages/compare/speckit--v5.0.0...speckit--v5.1.0) (2026-07-16)


### Features

* **codex:** add first-class APM parity across packages ([f0c988b](https://github.com/srobroek/agentic-packages/commit/f0c988b76740f23d2a6017c40fece7a1ea53e631))

## [5.0.0](https://github.com/srobroek/agentic-packages/compare/speckit--v4.0.0...speckit--v5.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* workflow gates via speckit-gate; deprecate speckit-dag-hooks ([#493](https://github.com/srobroek/agentic-packages/issues/493))

### Features

* workflow gates via speckit-gate; deprecate speckit-dag-hooks ([#493](https://github.com/srobroek/agentic-packages/issues/493)) ([8e3414a](https://github.com/srobroek/agentic-packages/commit/8e3414a0f4768b1cc174e00cd6e7c00c57153131))


### Bug Fixes

* **speckit-setup:** harden init, status-report fetch, and add 0.12.x floor ([#492](https://github.com/srobroek/agentic-packages/issues/492)) ([2b123fe](https://github.com/srobroek/agentic-packages/commit/2b123fef14c9d65254edf400ce4a3e52b1818010))

## [4.0.0](https://github.com/srobroek/agentic-packages/compare/speckit--v3.1.1...speckit--v4.0.0) (2026-07-07)


### ⚠ BREAKING CHANGES

* **speckit:** Wave 3b — extension set 28→12, verify via local agent, DAG 19 nodes
* **speckit:** Wave 3 — cull advisory DAG nodes, merge agents 6→4, compress steering and setup

### Features

* **speckit:** shrink extension set 28→12, replace verify/checkpoint with native steps ([72673e2](https://github.com/srobroek/agentic-packages/commit/72673e2b6c4757b3e9b36f21c687546fd2f1cd33))
* **speckit:** update verify agent contract, bugfix skill, and workflow steering ([22f9570](https://github.com/srobroek/agentic-packages/commit/22f957056fa1b10603441795caa8ea10912b8e4e))
* **speckit:** Wave 3 — cull advisory DAG nodes, merge agents 6→4, compress steering and setup ([bb1a623](https://github.com/srobroek/agentic-packages/commit/bb1a62369b9d5b5f4ae23e6234a1f29f6ba8148f))
* **speckit:** Wave 3b — extension set 28→12, verify via local agent, DAG 19 nodes ([dcc2281](https://github.com/srobroek/agentic-packages/commit/dcc22810108e93b5422329fb22e604844a990bd4))


### Refactors

* **speckit:** cut speckit-setup SKILL.md to 53 lines ([299bc9b](https://github.com/srobroek/agentic-packages/commit/299bc9ba8be136fd2633045c505401afac9dacab))
* **speckit:** merge 6 agents to 4 via mode/scope dispatch ([1578676](https://github.com/srobroek/agentic-packages/commit/1578676b19355078eae7ec8a01ff9cc0de2b0b79))

## [3.1.1](https://github.com/srobroek/agentic-packages/compare/speckit--v3.1.0...speckit--v3.1.1) (2026-06-30)


### Bug Fixes

* **hooks:** rework PreToolUse guards to never stall auto mode ([#432](https://github.com/srobroek/agentic-packages/issues/432)) ([e00ebb7](https://github.com/srobroek/agentic-packages/commit/e00ebb723fd8e00031fdf28c02ca6b846053d652))

## [3.1.0](https://github.com/srobroek/agentic-packages/compare/speckit--v3.0.0...speckit--v3.1.0) (2026-06-29)


### Features

* **speckit:** swap status extension for the maintained status-report ([#422](https://github.com/srobroek/agentic-packages/issues/422)) ([da823c6](https://github.com/srobroek/agentic-packages/commit/da823c6b6d238591f619c90284408455894ae78b))

## [3.0.0](https://github.com/srobroek/agentic-packages/compare/speckit--v2.0.0...speckit--v3.0.0) (2026-06-29)


### ⚠ BREAKING CHANGES

* standalone, agent-driven project scaffolding with git-distributed add-on modules ([#418](https://github.com/srobroek/agentic-packages/issues/418))

### Features

* standalone, agent-driven project scaffolding with git-distributed add-on modules ([#418](https://github.com/srobroek/agentic-packages/issues/418)) ([318dc97](https://github.com/srobroek/agentic-packages/commit/318dc975d485dd04cf1903262b1227242204d482))

## [2.0.0](https://github.com/srobroek/agentic-packages/compare/speckit--v1.1.0...speckit--v2.0.0) (2026-06-29)


### ⚠ BREAKING CHANGES

* **speckit:** the /speckit.memory-md.* commands and the mcp-speckit-memory MCP server are no longer installed by speckit setup.

### Features

* **speckit:** drop memory-md extension and mcp-speckit-memory package ([#415](https://github.com/srobroek/agentic-packages/issues/415)) ([855bd7d](https://github.com/srobroek/agentic-packages/commit/855bd7d86bf8cadadbdc94179bc80c35eb06119d))

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/speckit-v1.0.1...speckit--v1.1.0) (2026-06-27)


### Features

* install this marketplace natively in Claude Code and Codex ([#400](https://github.com/srobroek/agentic-packages/issues/400)) ([105c91c](https://github.com/srobroek/agentic-packages/commit/105c91c45dfbc0333a098d52934d19f4bfe6a630))


### Bug Fixes

* **agents:** drop abstract tools: so Claude grants a working toolset ([#402](https://github.com/srobroek/agentic-packages/issues/402)) ([564de79](https://github.com/srobroek/agentic-packages/commit/564de793da6858b7b697778da4560dda5084ef54))

## [1.0.1](https://github.com/srobroek/agentic-packages/compare/speckit-v1.0.0...speckit-v1.0.1) (2026-06-26)


### Bug Fixes

* use installable package types so hooks + speckit resolve globally ([#387](https://github.com/srobroek/agentic-packages/issues/387)) ([ff2b7a2](https://github.com/srobroek/agentic-packages/commit/ff2b7a2200fc88bcf39abafe9f73ed6f5d31e942))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/speckit-v0.5.1...speckit-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* retire unused packages (resume->resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368))

### Features

* migrate hooks into packages, remove dead scripts, baseline 0.0.1 [skip tests] ([912cd0c](https://github.com/srobroek/agentic-packages/commit/912cd0ce7868e0406dd8ac0659320b1fbc577319))
* publish standalone mcp packages ([3145100](https://github.com/srobroek/agentic-packages/commit/31451002a7ae874e59c7f11868dd039ba597730c))
* register the memory-md MCP server (mcp-speckit-memory) for SpecKit ([#371](https://github.com/srobroek/agentic-packages/issues/371)) ([adb8223](https://github.com/srobroek/agentic-packages/commit/adb8223c723bc8fc95a8152047b33b285847c1a4))
* retire unused packages (resume-&gt;resume-cv, drop prompt-lookup/hyperresearch), self-describe catalog categories ([#368](https://github.com/srobroek/agentic-packages/issues/368)) ([883945f](https://github.com/srobroek/agentic-packages/commit/883945feb3ee8f651f83b82f5f8d2ed520edf98f))
* **speckit-dag-hooks:** self-contained Python dispatcher + JSON nodes [skip tests] ([d46f465](https://github.com/srobroek/agentic-packages/commit/d46f465b7e056ca0d1689362f3d192c8819da1a9))
* **speckit:** add code-review and security-review steps to post-implementation DAG ([3ea8d20](https://github.com/srobroek/agentic-packages/commit/3ea8d2054e0231934cbf3054704b08c9d7127dbb))
* **speckit:** add per-command DAG hook dispatcher with hard/soft steering ([e6a6cf8](https://github.com/srobroek/agentic-packages/commit/e6a6cf8fe2d6af1c6d44360781d119d8bfed4b22))
* **speckit:** add roadmap extension to the required set ([#353](https://github.com/srobroek/agentic-packages/issues/353)) ([5bb3b73](https://github.com/srobroek/agentic-packages/commit/5bb3b7394564efc878a57ead83e2b11a755dbf52))
* **speckit:** add workflow overview instruction with DAG, human gating, and command reference [skip tests] ([2b356e0](https://github.com/srobroek/agentic-packages/commit/2b356e0f436bba813f9dfea9888ff67768337449))
* **speckit:** adopt memory-md 1.x across speckit, dag-hooks, and steering ([#355](https://github.com/srobroek/agentic-packages/issues/355)) ([450f1f3](https://github.com/srobroek/agentic-packages/commit/450f1f36ae8c9e42562e9270c414da34dd55dbfb))
* **speckit:** align with spec-kit 0.11.x — setup ownership, DAG node fix, converge ([8b2a51b](https://github.com/srobroek/agentic-packages/commit/8b2a51b3faa914ae86bbb6944ba62e408ca2e040))
* **speckit:** auto-detect primary integration in setup-speckit ([#358](https://github.com/srobroek/agentic-packages/issues/358)) ([991535d](https://github.com/srobroek/agentic-packages/commit/991535d525bbf10c998a5015ae49b310e48d6fba))
* **speckit:** checklist-after-tasks reorder, memory-md default, agent-assign + hook fixes ([56ceefc](https://github.com/srobroek/agentic-packages/commit/56ceefc09ae0c8e2e2f46977478f188daeb4fa7a))
* **speckit:** install memory-md by default [skip tests] ([0acdf42](https://github.com/srobroek/agentic-packages/commit/0acdf42bdeb16ba792dd36c2d509882f748fe913))
* **speckit:** own end-to-end spec-kit setup; align with spec-kit 0.11.x [skip tests] ([67e1f35](https://github.com/srobroek/agentic-packages/commit/67e1f3568bb8cebd47aca1a51ebedc4239e4613f))
* **speckit:** reorder DAG — critique + security-review after tasks, enforce mandatory steps ([37df18e](https://github.com/srobroek/agentic-packages/commit/37df18ee0663ece1951e951b9c9be788fbefaec9))


### Bug Fixes

* compile claude steering in setup guidance ([32d6fe3](https://github.com/srobroek/agentic-packages/commit/32d6fe31943fae7c274a8cf5365d23d0ec24269a))
* **hooks:** repair silently-dead hook filters (if-alternation bug) ([#372](https://github.com/srobroek/agentic-packages/issues/372)) ([659d5fe](https://github.com/srobroek/agentic-packages/commit/659d5fe6bb24a27b1876f46c6a750379eb66ec87))
* **phase-1:** guard bypasses, bash-3.2/BSD portability, crashes, bundle pins + tests ([#360](https://github.com/srobroek/agentic-packages/issues/360)) ([b0c9106](https://github.com/srobroek/agentic-packages/commit/b0c91064313282a4265b9b0b8fb779f00afecd90))
* **speckit-setup:** register extension commands for the requested integration ([#309](https://github.com/srobroek/agentic-packages/issues/309)) ([c67ee50](https://github.com/srobroek/agentic-packages/commit/c67ee50357cab8a982e28960e63b6738af93368c))
* **speckit:** agent-assign is a specify extension, not missing — restore deprecation note [skip tests] ([22c4dd4](https://github.com/srobroek/agentic-packages/commit/22c4dd4092b686da85de591e6af18d371e14a5a0))
* **speckit:** Codex hook references .agents/skills/, not .claude/ ([a0aba9d](https://github.com/srobroek/agentic-packages/commit/a0aba9d9a4214737bda494217cf5b13677a1a887))
* **speckit:** correct implement deprecation — agent-assign is the replacement, not tinyspec [skip tests] ([d968741](https://github.com/srobroek/agentic-packages/commit/d9687411a983aa47bb29eafd533cb589e2bb07fc))
* **speckit:** DAG hooks never fire — glob/regex mismatch + hyphen/dot normalisation ([5376ef9](https://github.com/srobroek/agentic-packages/commit/5376ef99bf984c4e51513645552cd2f63d4209df))
* **speckit:** dispatcher resolves nodes/ from apm_modules cache ([b9b4231](https://github.com/srobroek/agentic-packages/commit/b9b4231e47d8d8789c71266eb624f6cd11d26968))
* **speckit:** downgrade sync and sync-conflicts agents from opus to sonnet on Claude ([87e47f4](https://github.com/srobroek/agentic-packages/commit/87e47f43446a3597f0880e9bf562d778c212eb8d))
* **speckit:** guard hardening, align workflow docs with node store ([#294](https://github.com/srobroek/agentic-packages/issues/294)) ([99de83c](https://github.com/srobroek/agentic-packages/commit/99de83c82eed004273f7f3774bb5da3cad96940b))
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
