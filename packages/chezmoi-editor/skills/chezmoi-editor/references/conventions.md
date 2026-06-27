# Chezmoi Conventions

## Source Of Truth

- Edit files in the chezmoi source tree, not live targets in `$HOME`.
- Resolve the source tree with `chezmoi source-path` (or `chezmoi source-path <target>`
  for a specific target); do not assume a fixed location.

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
