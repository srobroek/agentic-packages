# Toolchain Defaults Index

Use this context when choosing or changing a project stack. Keep existing
project choices unless the current task is explicitly about setup, migration, or
standardization.

Read only the relevant detail:

- [Frontend defaults](toolchain-defaults.frontend.context.md)
- [Infrastructure defaults](toolchain-defaults.infrastructure.context.md)
- [Quality and observability defaults](toolchain-defaults.quality-observability.context.md)
- [Per-language library and tool defaults](toolchain-defaults.languages.context.md)

Language-specific structural conventions ship with each language in the
`language-<lang>` package; language failure modes and CI specifics ship in the
opt-in `language-steering-<lang>` package.

Treat `just`, `mise`, and `moon` as independent setup choices, not an
infrastructure concern:

- `just` for task aliases and repeatable local workflows.
- `mise` for language and tool version management.
- `moon` for task orchestration in larger monorepos.
