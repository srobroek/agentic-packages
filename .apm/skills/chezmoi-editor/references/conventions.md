# Chezmoi Conventions

## Source Of Truth

- Edit files in the chezmoi source tree, not live targets in `$HOME`.
- For this setup, the source tree is expected under the user's chezmoi directory.

## Naming

- `dot_` for dotfiles
- `private_` for `0600` files
- `executable_` for executable scripts
- `readonly_` for read-only files
- `.tmpl` for Go-template-managed files

## Workflow

- Read the existing source file first.
- Make the source edit.
- Preview with `chezmoi diff`.
- Apply only when the source diff is correct.
