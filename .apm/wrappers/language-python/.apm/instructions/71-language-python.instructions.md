---
description: Python steering.
applyTo: "**/*.py"
---

# Python

Use `src/<package>/` layouts with `api`, `domain`, `application`, `adapters`, and
`settings.py` for services. Keep domain code independent from framework and IO
concerns.

For uv, Ruff, pytest, pyright, FastAPI, Pydantic, and Litestar defaults, use the
always-loaded toolchain defaults and the project setup skill.
