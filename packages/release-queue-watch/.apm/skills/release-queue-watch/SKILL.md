---
name: release-queue-watch
description: Watch open PR checks every five minutes with gh and rediscover new PRs. Trigger on keep watching, monitor the queue, or watch CI.
---

# Release Queue Watch

TRIGGER
+ "keep watching", "monitor the PR queue", "watch CI", or "check every five minutes"
- Merge, rebase, close, or repair a PR → use pr-shepherd or an implementation lane

## Workflow

1. Discover open PR numbers with `gh pr list --state open --json number`.
2. For each PR, run `gh pr checks <N> --watch --interval 300`; tolerate terminal failure so one PR cannot stop discovery.
3. Sleep 300 seconds, rediscover PRs, and repeat in a foreground session.
4. Surface only new PRs, check transitions, terminal failures, or mergeability changes; stay silent on unchanged results.

## Rules

MUST Keep the watcher read-only: never merge, rebase, close, push, or modify Beads from the watch loop.
MUST Use the native `gh pr checks --watch --interval 300` command for check polling.
DEFAULT Run the loop in a foreground session when the user wants continuous monitoring.
NOT Treat a terminal `gh pr checks` result as the end of queue monitoring; rediscover PRs after the pass.

OUTPUT
L1 WATCHER ACTIVE — interval 300s, open PR discovery enabled
CAP 80w clean · 160w with findings
