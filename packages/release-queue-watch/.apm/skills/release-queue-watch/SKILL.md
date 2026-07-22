---
name: release-queue-watch
description: Runs a verified local PR queue receiver. Trigger on keep watching, monitor the queue, watch CI, or dispatch merge slots.
disable-model-invocation: true
---

# Release Queue Watch

TRIGGER
+ "keep watching", "monitor the PR queue", or "watch CI"
+ "dispatch the next PR" or "use available merge slots"
- Merge, rebase, close, or repair a PR → use pr-shepherd or an implementation lane

## Workflow

1. Resolve `scripts/webhook/` relative to this file.
2. Run `pnpm install --frozen-lockfile` in that directory before each first start or lockfile change.
3. Run `pnpm --silent start --repo=OWNER/REPO --slots=NUMBER` so stdout remains NDJSON. The runtime creates a private persisted secret, provisions `cli/gh-webhook` in isolated XDG data, and starts the signed local receiver before forwarding. Consume structured error lines from stderr too.
4. Consume JSON `pr-lifecycle` records as read-only state changes and `dispatch` records as agent-owned work slots. Use `AdvisoryWakeDispatcher` to serialize the handoff when the watcher runs beside a supervisor. Resolve an exact orchestrate node first; only an explicit unmatched result may route the unchanged record once to pr-shepherd. The runtime ranks ready PRs by priority label, enqueue time, repository, then PR number.
5. Leave REST reconciliation enabled. It repairs missed webhook state and emits fallback lifecycle records every 60 seconds by default.
6. Stop with SIGINT or SIGTERM. LOAD `references/runtime.md` for record schemas, fallback semantics, hook setup, or cleanup diagnosis.

## Rules

MUST Keep the runtime read-only: never merge, rebase, close, push, or modify Beads.
MUST Accept webhook state only after `@octokit/webhooks` verifies the signature.
MUST Debounce equivalent events for 30 seconds and reject repeated delivery IDs.
MUST Treat lifecycle and dispatch records as input only; the selected orchestrate gatekeeper or PR shepherd owns Beads, gates, conflict probes, and merge mutations.
MUST Never fan one record to both orchestrate and pr-shepherd consumers.
MUST Keep one advisory wake in flight; persist the resolver's required receipt metadata inside the selected consumer before sending its wake.
MUST Run the development forwarder only on a trusted single-user host; `cli/gh-webhook` v0.2.0 exposes its required `--secret` value in the child argument list.
DEFAULT Use one merge slot unless the user supplies another positive integer.
NOT Use Smee; `cli/gh-webhook` is the local development transport.
NOT Treat webhook delivery as complete state; Octokit REST reconciliation remains active.

OUTPUT
L1 WATCHER ACTIVE — signed events, REST reconciliation, and <N> merge slot(s)
CAP 100w clean · 180w with findings
