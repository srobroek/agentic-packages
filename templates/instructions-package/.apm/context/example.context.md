# Example Context

This is the on-demand context the instruction file links to. It is loaded only
when the model follows the link, so it can be as detailed as needed without
costing tokens on every turn.

Put the actual conventions, directory rules, and rationale here. Example:

- `services/` for long-lived deployables.
- `functions/` for serverless handlers.
- `workers/` for queues, schedulers, and other background workloads.

Cross-link sibling context files instead of one giant file so the model reads
only the relevant slice.
