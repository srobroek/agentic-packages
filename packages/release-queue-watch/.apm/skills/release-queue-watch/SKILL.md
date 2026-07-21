---
name: release-queue-watch
description: Watch the PR queue for new, merged, and failing pull requests with debounced native gh polling. Trigger on keep watching or monitor the queue.
---

# Release Queue Watch

TRIGGER
+ "keep watching", "monitor the PR queue", "watch CI", or "alert on new, merged, or failed PRs"
- Merge, rebase, close, or repair a PR → use pr-shepherd or an implementation lane

## Workflow

1. Discover open PRs with `gh pr list --state open --json number,title,baseRefName,headRefOid,mergeStateStatus` and retain the prior snapshot.
2. For each open PR, run `gh pr checks <N> --watch --interval 30`; tolerate terminal failure so one PR cannot stop discovery.
3. Rediscover the open set every 30 seconds. Emit a debounced event once for each new PR; for removed PRs, query `gh pr view <N> --json state,mergeCommit` and emit MERGED or CLOSED.
4. Surface terminal CI failures and mergeability/check transitions once per state change; stay silent on unchanged results.

## Rules

MUST Keep the watcher read-only: never merge, rebase, close, push, or modify Beads from the watch loop.
MUST Use the native `gh pr checks --watch --interval 30` command for check polling.
MUST Debounce identical events for at least 30 seconds.
DEFAULT Run the loop in a foreground session when the user wants continuous monitoring.
NOT Treat a terminal `gh pr checks` result as the end of queue monitoring; rediscover PRs after the pass.

OUTPUT
L1 WATCHER ACTIVE — interval 30s, debounced new/merged/failure events enabled
CAP 100w clean · 180w with findings
