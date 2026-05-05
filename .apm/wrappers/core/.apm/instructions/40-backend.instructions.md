---
description: Backend runtime steering for services, functions, and workers.
applyTo: "{services/**,functions/**,workers/**}"
---

# Backend Runtimes

Separate backend runtime shapes: `services/` for long-lived deployables,
`functions/` for serverless handlers, and `workers/` for queue, scheduler, and
consumer workloads. Nest platform second, such as `functions/aws-lambda` or
`workers/cloudflare`.

Use owner-local `data/`, `contracts/`, `prompts/`, and `evals/` folders when a
backend owns those assets.
