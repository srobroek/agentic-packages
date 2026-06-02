# Backend Runtime Context

Use this context for services, functions, workers, API boundaries, background
work, runtime-owned assets, prompts, evals, and deployable ownership.

Read only the relevant detail:

- [API contracts](backend.api-contracts.context.md)
- [Background work](backend.background-work.context.md)

Separate backend runtime shapes:

- `services/` for long-lived deployables.
- `functions/` for serverless handlers.
- `workers/` for queues, schedulers, consumers, and other background workloads.

Nest platform second, such as `functions/aws-lambda` or `workers/cloudflare`.

Use owner-local `data/`, `contracts/`, `prompts/`, and `evals/` folders when a
backend owns those assets.
