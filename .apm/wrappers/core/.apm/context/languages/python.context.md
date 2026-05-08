# Python

Use `src/<package>/` layouts with `api`, `domain`, `application`, `adapters`,
and `settings.py` for services.

Keep domain code independent from framework and IO concerns.

When `lsp-python` is configured, use it for definitions, references,
diagnostics, and safe renames before text search.

Use the project setup skill or [toolchain defaults](../toolchain-defaults/toolchain-defaults-index.context.md)
for uv, Ruff, pytest, pyright, FastAPI, Pydantic, and Litestar defaults.
