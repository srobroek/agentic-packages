# Agentic Package Indexes

These indexes are the authoritative source for project setup recommendations
and package hygiene checks. Project setup must read these files instead of
hardcoding agentic asset recommendation matrices in steering.

- `agents.json`: generated from `.apm/agents/*.agent.md`.
- `skills.json`: generated from `.apm/skills/*/SKILL.md`.
- `hooks.json`: generated from `.apm/hooks/*.json` and `.apm/hooks/scripts/*`.
- `contexts.json`: generated from `.apm/context/*.context.md`.
- `instructions.json`: generated from `.apm/instructions/*.instructions.md`.
- `mcp.json`: generated from `.apm/mcp/**` when MCP assets exist.
- `scripts.json`: generated from `.apm/scripts/*`.
- `packages.json`: generated from `packages/*`.
- `assets.json`: combined index across all generated asset indexes.
- `external-sources.json`: curated external APM-compatible packages and
  virtual-package entries.

Regenerate local indexes after changing agents, skills, hooks, contexts,
instructions, MCP assets, scripts, or packages:

```bash
python3 .apm/scripts/build-agentic-indexes.py
```
