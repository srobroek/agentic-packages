# Changelog

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
