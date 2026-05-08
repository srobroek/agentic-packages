# Steering Index

This package keeps shared steering as APM instructions and context files, not
as runtime-specific generated output.

Load only the relevant topic:

- [Agent routing](agent-routing.context.md)
- [Toolchain defaults](toolchain-defaults/toolchain-defaults-index.context.md)
- [Languages](languages/languages-index.context.md)
- [Frontend](frontend/frontend-index.context.md)
- [Backend](backend/backend-index.context.md)
- [Data](data/data-index.context.md)
- [Infrastructure](infrastructure/infrastructure-index.context.md)
- [Docs and specs](docs-specs/docs-specs-index.context.md)
- [Tools and scripts](tools-scripts/tools-scripts-index.context.md)
- [External agent marketplaces](external-agent-marketplaces.context.md)
- [Project structure](project-structure/project-structure-index.context.md)
- [Agentic source of truth](source-of-truth.context.md)
- [External asset audit](external-assets.context.md)

Codex consumes this through compiled `AGENTS.md` links. Claude Code should use a
minimal `CLAUDE.md` pointer to `AGENTS.md`; do not compile Claude steering by
default because that duplicates full instruction bodies.
