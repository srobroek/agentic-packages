<!--
Title must follow Conventional Commits so release-please picks it up, e.g.:
  feat(frontend): add accessibility steering
  fix(agent-coder): correct codex sandbox mode
  chore(repo): bump CI actions
Scope is usually the package name (the release-please component). Only feat/fix
bump a version; chore/docs/refactor/test/ci do not.
-->

## What changed

<!-- One or two sentences. What does this PR do and why? -->

## Affected packages

<!-- List each packages/<name> this touches, or "repo tooling" for root-level
changes (scripts, workflows, marketplace block, README). -->

-

## Type

- [ ] `feat` -- new capability (minor bump)
- [ ] `fix` -- bug fix (patch bump)
- [ ] `chore` / `docs` / `refactor` / `test` / `ci` -- no version bump

## Checklist

- [ ] Edited package sources only (not generated `.claude/`, `.codex/`, `.agents/`, `AGENTS.md`, `CLAUDE.md`)
- [ ] Ran `apm run build-artifacts` and committed the regenerated marketplace manifests, README tables, and release-please config
- [ ] `apm pack --check-clean`, `apm run check-readme-tables`, and `apm run check-release-please` pass locally
- [ ] If a bundle now depends on a new/renamed member, the dependency uses the repo-locator form `srobroek/agentic-packages/packages/<name>#<name>-v<version>` (not `<name>@srobroek-agentic`) and is pinned to an existing tag
- [ ] New/changed hooks reference scripts via `${PLUGIN_ROOT}/scripts/<name>.sh` and the scripts live under the owning package
- [ ] No AI attribution in commit messages; content-only commits end the subject with `[skip tests]`
