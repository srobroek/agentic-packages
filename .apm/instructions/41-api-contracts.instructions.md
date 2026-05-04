---
description: API and cross-boundary contract steering.
applyTo: "{services/api/**,services/graphql/**,services/rpc/**,services/webhooks/**,schemas/**,**/contracts/**}"
---

# APIs And Contracts

Root `schemas/` owns shared/public contracts only: OpenAPI, GraphQL, AsyncAPI,
JSON Schema, protobuf, and event contracts. Keep generated clients out of
`schemas/`; place them with consumers or in independently versioned packages.

Use owner-local `contracts/` for private deployable-specific boundaries.
