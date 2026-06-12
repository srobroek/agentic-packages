---
name: chezmoi-editor
description: Edit chezmoi-managed dotfiles from their authoritative source files. Use when changing dotfiles, global agent/tool config, templates, private files, symlinked config, or any live target that may be managed by chezmoi.
---

# Chezmoi Editor

Use this skill when a task changes files managed by chezmoi. Resolve the managed
source first; do not edit the rendered live target as the durable fix.

## Workflow

1. Determine whether the target is managed:
   - `chezmoi managed`
   - `chezmoi source-path <target>` when a specific target is known
   - existing symlink/source layout when chezmoi cannot resolve it directly
2. Edit the source under the chezmoi source tree, not `$HOME` runtime output.
3. Use native chezmoi names for dotfiles, executables, private files, readonly
   files, symlinks, and templates.
4. Keep secrets in your credential manager or vault, never plaintext (see
   `references/secrets.md`).
5. Preview with `chezmoi diff`. Apply only when the source diff is correct and
   the user wants the live target updated now.

## Rules

- Treat the chezmoi source directory as the source of truth.
- Prefer native chezmoi patterns over ad hoc symlink or copy schemes.
- If a live target changed outside chezmoi, reconcile it back into source
  instead of patching around the generated copy.
- Temporary runtime experiments are allowed only when the user explicitly asks
  for them; record how to promote the result into source.

## Scripts

- Status and diff: `scripts/status.sh`.

## References

- Read `references/conventions.md` when choosing file naming patterns, prefixes,
  or editing rules.
- Read `references/secrets.md` when handling secret values.
