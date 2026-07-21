import assert from "node:assert/strict";
import test from "node:test";
import { EventGate } from "../src/event-gate.js";
import { ReleaseQueueState } from "../src/queue-state.js";

function pull(number, overrides = {}) {
  return {
    deliveryId: `delivery-${number}`,
    receivedAt: 1_000,
    action: "upsert",
    repository: "owner/repo",
    number,
    title: `PR ${number}`,
    headSha: `sha-${number}`,
    baseRef: "main",
    labels: [],
    draft: false,
    mergeable: true,
    checks: "pass",
    createdAt: `2026-07-${String(number).padStart(2, "0")}T00:00:00Z`,
    updatedAt: "2026-07-21T00:00:00Z",
    ...overrides,
  };
}

test("deduplicates deliveries and debounces equivalent state", () => {
  const queue = new ReleaseQueueState({
    eventGate: new EventGate({ debounceMs: 30_000 }),
  });
  assert.equal(queue.applyPullRequestEvent(pull(1)).accepted, true);
  assert.equal(queue.applyPullRequestEvent(pull(1)).reason, "duplicate-delivery");
  assert.equal(
    queue.applyPullRequestEvent(pull(1, { deliveryId: "retry", receivedAt: 2_000 })).reason,
    "debounced",
  );
});

test("ranks ready pull requests and dispatches when an agent-owned slot frees", () => {
  let now = 1_000;
  const queue = new ReleaseQueueState({ maxMergeSlots: 1, now: () => now });
  const first = queue.applyPullRequestEvent(pull(10, { labels: ["priority-p2"] }));
  assert.deepEqual(first.dispatches.map((item) => item.number), [10]);

  now += 1_000;
  const higherPriority = queue.applyPullRequestEvent(
    pull(20, { deliveryId: "delivery-20", labels: ["priority::critical"] }),
  );
  assert.deepEqual(higherPriority.dispatches, []);
  assert.equal(queue.snapshot().find((item) => item.number === 20).state, "queued");

  assert.deepEqual(queue.releaseSlot("owner/repo", 10).map((item) => item.number), [20]);
  assert.equal(queue.snapshot().find((item) => item.number === 20).state, "active");

  const closed = queue.applyPullRequestEvent(
    pull(20, { deliveryId: "closed-20", action: "closed", updatedAt: "closed" }),
  );
  assert.deepEqual(closed.dispatches.map((item) => item.number), [10]);
});

test("reconciliation blocks changed pull requests and removes closed ones", () => {
  const queue = new ReleaseQueueState({ maxMergeSlots: 2 });
  queue.reconcileRepository("owner/repo", [pull(1), pull(2)]);
  assert.equal(queue.snapshot().filter((item) => item.state === "active").length, 2);

  queue.reconcileRepository("owner/repo", [
    pull(2, { mergeable: false, checks: "fail", deliveryId: undefined }),
  ]);
  assert.deepEqual(queue.snapshot().map((item) => item.number), [2]);
  assert.equal(queue.snapshot()[0].state, "blocked");
});
