---
description: Global routing for shared agentic tools installed by APM.
applyTo: "**/*"
---

# Agentic Tooling Routing

Use APM-managed primitives as the source of truth for shared agents, skills,
hooks, MCP server definitions, instructions, context, and project setup.

For progressive disclosure, start with
[the steering index](../context/steering-index.context.md), then load only the
topic-specific context needed for the current task.

Author shared agentic assets in `agentic-packages/.apm/`, not in generated
runtime folders such as `.codex/agents`, `.claude/agents`, `.claude/rules`, or
`.agents/skills`. Project-local exceptions must be documented in `apm.yml`.

After installing or updating this package in a project, run the project-local
setup script when it exists:

```bash
apm run setup-agentic-tools
```

If the project has not added that script yet, run the steps manually:

```bash
apm install --target claude,codex,agent-skills
apm compile --target codex
python3 apm_modules/_local/agentic-packages/.apm/scripts/patch-runtime-agents.py --all
python3 apm_modules/_local/agentic-packages/.apm/scripts/audit-agentic-assets.py
```

Do not compile Claude by default; APM install already deploys Claude rules under
`.claude/rules`. Compiling Claude additionally creates `CLAUDE.md` and duplicates
those rules.

Do not treat generated Codex TOML, Claude agent files, or installed skill copies
as authoritative source.
