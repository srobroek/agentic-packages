# Background Work Context

Workers and scheduled jobs must make retry, idempotency, ordering, dead-letter,
and observability behavior explicit.

Prefer small handlers around reusable application services instead of embedding
domain logic in queue glue.

Document queue semantics when they matter for correctness: delivery guarantee,
ordering, concurrency, retry policy, and dead-letter behavior.
