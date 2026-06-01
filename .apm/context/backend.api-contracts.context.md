# API Contract Context

Root `schemas/` owns shared or public contracts only: OpenAPI, GraphQL,
AsyncAPI, JSON Schema, protobuf, and event contracts.

Keep generated clients out of `schemas/`. Place generated clients with
consumers or in independently versioned packages.

Use owner-local `contracts/` for private deployable-specific boundaries.
