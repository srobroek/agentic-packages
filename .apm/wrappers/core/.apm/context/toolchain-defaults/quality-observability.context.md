# Quality And Observability Defaults

Use layered tests that match the risk of the change:

- unit tests for isolated logic
- integration tests for contracts, adapters, persistence, and boundaries
- browser or end-to-end checks for user-visible frontend workflows

Use structured logging for services and workers. Add OpenTelemetry when a
runtime boundary, distributed workflow, or production operation needs traceable
behavior.

Use security scanners conditionally. Prefer checks that the project can run
locally and in CI without creating noisy false positives.
