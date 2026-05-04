# Source and Adaptation Notes

This skill is adapted from:

- Repository: <https://github.com/Dammyjay93/interface-design>
- Author: Damola Akinleye / Dammyjay93
- License: MIT

The upstream project is a Claude Code plugin for interface design, craft,
memory, and consistency. This local version adapts the ideas to Codex and the
agentic-tools skill format.

## Adopted Concepts

- Use the skill for product interfaces: dashboards, apps, admin panels, tools,
  settings pages, and data interfaces.
- Start with intent: human, job, desired feel, product-specific defaults to
  avoid, and a signature pattern.
- Treat token architecture, spacing, depth, typography, state design, and
  navigation context as design decisions.
- Use a project-local memory file for reusable implementation patterns:
  `.interface-design/system.md`.
- Run craft checks before presenting UI: default choices, hierarchy, token
  discipline, interaction states, and consistency.

## Local Changes

- `DESIGN.md` / `DESIGN.MD` is the primary authority in this environment.
- `.interface-design/system.md` is supporting memory only.
- Claude plugin commands are not copied; workflows are expressed as Codex skill
  procedures.
- The skill is paired with global frontend steering, including the Vercel web
  interface guidelines.
