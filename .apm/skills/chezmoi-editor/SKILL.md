---
name: chezmoi-editor
description: Use when editing chezmoi-managed dotfiles. Edit source files, not live targets.
---

# Chezmoi Editor

Use this skill when the task changes files managed by chezmoi.

## Preferred Flow

1. Inspect current chezmoi state before editing.
2. Edit the source file under the chezmoi source tree, not the target path.
3. Use `chezmoi diff` to preview the result.
4. Keep secrets in a password manager or chezmoi-supported secret mechanism, not plaintext.
5. Apply only after the intended source diff is correct.

## Steering

- Treat the chezmoi source directory as the source of truth.
- Prefer native chezmoi patterns over ad hoc symlink or copy schemes.
- Use the right chezmoi file naming conventions for dotfiles, executables, private files, and templates.
- When a live target is externally modified, prefer a chezmoi-native pattern rather than editing around it manually.

## Scripts

- Status and diff: `scripts/status.sh`

## References

- Read `references/conventions.md` when choosing file naming patterns, prefixes, or editing rules.
- Read `references/secrets.md` when handling 1Password integration or any secret values.
