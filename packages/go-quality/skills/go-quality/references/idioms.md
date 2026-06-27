# Go References

Use these in this order:

1. Local package conventions and existing code patterns
2. Context7 for framework and library docs
3. Canonical Go docs for language-level and API-style questions

## Context7

- Use Context7 when the question depends on the current package version or tool behavior.
- Start with the exact package docs for the repo, then narrow to the topic:
  - `gin`
  - `cobra`
  - `grpc-go`
  - `sqlc`
  - any package actually used in the project

## Canonical Docs

- Effective Go: https://go.dev/doc/effective_go
- Go Code Review Comments: https://go.dev/wiki/CodeReviewComments
- Go language docs: https://go.dev/doc/

## Steering Notes

- Prefer simple package boundaries and explicit dependencies.
- Keep interfaces small and defined where they are consumed.
- Prefer straightforward control flow and error handling over abstraction-heavy designs.
- Optimize for readability and maintenance before cleverness.
