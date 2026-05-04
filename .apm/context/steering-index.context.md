# Steering Index

This package keeps shared steering as APM instructions and context files, not
as runtime-specific generated output.

Load only the relevant topic:

- [Agent routing](agent-routing.context.md)
- [Project structure](project-structure.context.md)
- [Agentic source of truth](source-of-truth.context.md)
- [External asset audit](external-assets.context.md)

Codex consumes this through compiled `AGENTS.md` links. Claude Code consumes
installed `.claude/rules`; do not compile Claude by default unless a project
explicitly needs a single `CLAUDE.md` summary.
