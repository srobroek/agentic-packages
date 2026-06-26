# Changelog

## [1.1.0](https://github.com/srobroek/agentic-packages/compare/hooks-chezmoi-guard-v1.0.1...hooks-chezmoi-guard-v1.1.0) (2026-06-26)


### Features

* tighten autonomous-agent hook guards; add precommit-gate and close-keywords packages ([#391](https://github.com/srobroek/agentic-packages/issues/391)) ([34f155a](https://github.com/srobroek/agentic-packages/commit/34f155aab3ae1586b2ce16e2418a30a9d47b5137))

## [1.0.1](https://github.com/srobroek/agentic-packages/compare/hooks-chezmoi-guard-v1.0.0...hooks-chezmoi-guard-v1.0.1) (2026-06-26)


### Bug Fixes

* use installable package types so hooks + speckit resolve globally ([#387](https://github.com/srobroek/agentic-packages/issues/387)) ([ff2b7a2](https://github.com/srobroek/agentic-packages/commit/ff2b7a2200fc88bcf39abafe9f73ed6f5d31e942))

## [1.0.0](https://github.com/srobroek/agentic-packages/compare/hooks-chezmoi-guard-v0.1.0...hooks-chezmoi-guard-v1.0.0) (2026-06-26)


### ⚠ BREAKING CHANGES

* mcp-package-version no longer ships the package-file-warn or pkg-version-warn hooks. Installers that relied on those hooks should install hooks-package-file-guard / hooks-pkg-version-warn (or the dependency-quality bundle) instead.

### Features

* add hooks-chezmoi-guard and hooks-attribution-guard guard-hook packages ([#369](https://github.com/srobroek/agentic-packages/issues/369)) ([92814f2](https://github.com/srobroek/agentic-packages/commit/92814f2cb43a8afb417f9c2e6518b822cb8adbab))
* split dependency tooling into independent packages + dependency-quality bundle ([#370](https://github.com/srobroek/agentic-packages/issues/370)) ([03d50a5](https://github.com/srobroek/agentic-packages/commit/03d50a5db3a1572fbe36a4ac1bc1e6877cd96ade))

## 0.1.0

### Features

* **hooks-chezmoi-guard:** initial release. PreToolUse guard denying direct
  edits (Edit/Write/MultiEdit) and shell writes (redirects, `tee`, `rm`,
  `touch`, `chmod`, `chown`, `ln`, `sed -i`, `perl -pi`, `cp`/`mv` destination)
  to files chezmoi actually manages, decided by exact membership in
  `chezmoi managed` (per-user cache, 60s TTL). Read-only references to a managed
  path (`cat`/`diff`/`grep`/`>/dev/null`), `cp`/`mv` of a managed SOURCE, and
  unmanaged paths all pass. When chezmoi is not installed the guard is a clean
  allow (exit 0). Cross-tool (Claude + Codex).

### Notes

Extracted and hardened from the live global `chezmoi-guard.sh`. Fixes carried in
this release versus that source:

* String-form `tool_input` no longer bypasses the guard — both the command and
  file-path extraction use the type-checked jq idiom instead of
  `.tool_input.command // .tool_input`, which threw on a bare string.
* `..` path traversal can no longer dodge exact membership — paths are
  canonicalized lexically (portable, no filesystem access) before the membership
  test, so `~/.claude/../.claude/CLAUDE.md` resolves to its canonical form.
* Quoted write targets containing spaces in redirect / `cp` / `mv` positions are
  unquoted before the membership test (see the in-script LIMITATION note for the
  remaining unquoted-operand-with-space edge case).
* The membership cache moved from a shared, predictable TMPDIR path to a
  per-user path (`chezmoi-managed-cache.<uid>`).
