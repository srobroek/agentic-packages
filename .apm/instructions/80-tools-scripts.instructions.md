---
description: Repo tooling and automation steering.
applyTo: "{scripts/**,tools/**,justfile,Justfile,Taskfile.yml,Makefile,mise.toml,.moon/**}"
---

# Tools And Scripts

Use `scripts/` for thin repo automation. Use `tools/` for maintained CLIs,
generators, MCP server implementations, and reusable developer tooling.

Project orchestration is composable: `just`, `mise`, and `moon` are independent
setup choices.
