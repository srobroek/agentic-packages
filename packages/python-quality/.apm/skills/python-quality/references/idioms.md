# Python References

Use these in this order:

1. Local project conventions and existing code patterns
2. Context7 for framework and library docs
3. Canonical Python style and typing docs for language-level questions

## Context7

- Use Context7 when the question depends on the current framework or library version.
- Start with the relevant package docs, then narrow to the exact topic:
  - Python language and stdlib references when mirrored in Context7
  - Django, FastAPI, Pydantic, pytest, Ruff, SQLAlchemy, etc. for project-specific behavior

## Canonical Docs

- PEP 8: https://peps.python.org/pep-0008/
- Python typing specification: https://typing.python.org/en/latest/spec/
- Python tutorial and standard library docs: https://docs.python.org/3/

## Steering Notes

- Prefer clear data flow and explicit names over compact cleverness.
- Prefer typed interfaces at module boundaries.
- Use dataclasses, TypedDict, Protocol, or pydantic-style models intentionally instead of ad hoc dicts when structure matters.
- Keep side effects near the edges and core logic easy to test.
