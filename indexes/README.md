# Agentic Package Indexes

These indexes are the authoritative source for project setup recommendations.
Project setup must read these files instead of hardcoding agent or skill
recommendation matrices in steering.

- `agents.json`: generated from `.apm/agents/*.agent.md`.
- `skills.json`: generated from `.apm/skills/*/SKILL.md`.
- `external-sources.json`: curated external APM-compatible packages and
  virtual-package entries.

Regenerate local indexes after changing agents or skills:

```bash
python3 .apm/scripts/build-agentic-indexes.py
```

