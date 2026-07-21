---
name: release-queue-watch
description: Runs a verified local PR queue receiver. Trigger on keep watching, monitor the queue, watch CI, or dispatch merge slots.
---

# Release Queue Watch

TRIGGER
+ "keep watching", "monitor the PR queue", or "watch CI"
+ "dispatch the next PR" or "use available merge slots"
- Merge, rebase, close, or repair a PR → use pr-shepherd or an implementation lane

## Workflow

1. Resolve `scripts/webhook/` relative to this file.
2. Run `pnpm install --frozen-lockfile` in that directory before each first start or lockfile change.
3. Run `pnpm start --repo=OWNER/REPO --slots=NUMBER`. The runtime creates a private persisted secret, provisions `cli/gh-webhook` in isolated XDG data, and starts the signed local receiver before forwarding.
4. Consume JSON `dispatch` records as agent-owned work slots. The runtime ranks ready PRs by priority label, enqueue time, repository, then PR number.
5. Leave REST reconciliation enabled. It repairs missed webhook state every 60 seconds by default.
6. Stop with SIGINT or SIGTERM. LOAD `references/runtime.md` when hook setup or cleanup needs diagnosis.

## Rules

MUST Keep the runtime read-only: never merge, rebase, close, push, or modify Beads.
MUST Accept webhook state only after `@octokit/webhooks` verifies the signature.
MUST Debounce equivalent events for 30 seconds and reject repeated delivery IDs.
DEFAULT Use one merge slot unless the user supplies another positive integer.
NOT Use Smee; `cli/gh-webhook` is the local development transport.
NOT Treat webhook delivery as complete state; Octokit REST reconciliation remains active.

OUTPUT
L1 WATCHER ACTIVE — signed events, REST reconciliation, and <N> merge slot(s)
CAP 100w clean · 180w with findings
