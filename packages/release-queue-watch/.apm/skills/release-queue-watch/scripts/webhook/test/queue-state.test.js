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

test("a synchronized head resets queued and active readiness until reconciliation", () => {
  const queue = new ReleaseQueueState({ maxMergeSlots: 1 });
  queue.applyPullRequestEvent(pull(1));
  queue.applyPullRequestEvent(pull(2));
  queue.applyPullRequestEvent(pull(3));

  const queuedSynchronize = queue.applyPullRequestEvent(
    pull(3, {
      deliveryId: "sync-queued",
      headSha: "new-queued-sha",
      checks: undefined,
      mergeable: undefined,
      updatedAt: "2026-07-21T00:30:00Z",
    }),
  );
  assert.deepEqual(queuedSynchronize.dispatches, []);
  const queued = queue.snapshot().find((item) => item.number === 3);
  assert.equal(queued.state, "blocked");
  assert.equal(queued.checks, "pending");
  assert.equal(queued.mergeable, null);

  const activeSynchronize = queue.applyPullRequestEvent(
    pull(1, {
      deliveryId: "sync-active",
      headSha: "new-active-sha",
      checks: undefined,
      mergeable: undefined,
      updatedAt: "2026-07-21T01:00:00Z",
    }),
  );
  assert.deepEqual(activeSynchronize.dispatches.map((item) => item.number), [2]);
  const active = queue.snapshot().find((item) => item.number === 1);
  assert.equal(active.state, "blocked");
  assert.equal(active.checks, "pending");
  assert.equal(active.mergeable, null);
  assert.equal(active.activeSince, null);
  assert.equal(queue.snapshot().find((item) => item.number === 3).state, "blocked");
});

test("an older head snapshot stays stale when its request starts after synchronize", () => {
  const queue = new ReleaseQueueState();
  queue.applyPullRequestEvent(pull(1));
  queue.applyPullRequestEvent(
    pull(1, {
      deliveryId: "sync-before-request",
      headSha: "new-sha",
      checks: undefined,
      mergeable: undefined,
      updatedAt: "2026-07-21T02:00:00Z",
    }),
  );
  const requestGeneration = queue.reconciliationGeneration();

  assert.deepEqual(
    queue.reconcileRepository(
      "owner/repo",
      [pull(1, { deliveryId: undefined, updatedAt: "2026-07-21T00:00:00Z" })],
      2_000,
      requestGeneration,
    ),
    [],
  );
  const [current] = queue.snapshot();
  assert.equal(current.headSha, "new-sha");
  assert.equal(current.checks, "pending");
  assert.equal(current.mergeable, null);
  assert.equal(current.state, "blocked");
});
