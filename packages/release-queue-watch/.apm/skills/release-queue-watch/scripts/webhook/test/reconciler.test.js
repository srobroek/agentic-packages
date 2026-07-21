import assert from "node:assert/strict";
import test from "node:test";
import { ReleaseQueueState } from "../src/queue-state.js";
import { PollingReconciler } from "../src/reconciler.js";

test("coalesces concurrent reconciliation and emits dispatches", async () => {
  let calls = 0;
  let resolveList;
  const adapter = {
    listOpenPullRequests() {
      calls += 1;
      return new Promise((resolve) => {
        resolveList = resolve;
      });
    },
  };
  const dispatched = [];
  const reconciler = new PollingReconciler({
    repositories: ["owner/repo"],
    adapter,
    queue: new ReleaseQueueState(),
    onDispatch: (item) => dispatched.push(item.number),
  });

  const first = reconciler.reconcileRepository("owner/repo");
  const second = reconciler.reconcileRepository("owner/repo");
  resolveList([
    {
      number: 3,
      title: "Ready",
      headSha: "abc",
      baseRef: "main",
      labels: [],
      draft: false,
      mergeable: true,
      checks: "pass",
      createdAt: "2026-07-20T00:00:00Z",
      updatedAt: "2026-07-21T00:00:00Z",
    },
  ]);
  await Promise.all([first, second]);

  assert.equal(calls, 1);
  assert.deepEqual(dispatched, [3]);
});
