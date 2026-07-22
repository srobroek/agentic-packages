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
	assert.equal(
		queue.applyPullRequestEvent(pull(1)).reason,
		"duplicate-delivery",
	);
	assert.equal(
		queue.applyPullRequestEvent(
			pull(1, { deliveryId: "retry", receivedAt: 2_000 }),
		).reason,
		"debounced",
	);
	assert.equal(
		queue.applyPullRequestEvent(
			pull(1, {
				deliveryId: "reopened",
				receivedAt: 3_000,
				transition: "opened",
				webhookAction: "reopened",
				updatedAt: "2026-07-21T01:00:00Z",
			}),
		).accepted,
		true,
	);
});

test("emits deterministic lifecycle transitions once across webhooks and reconciliation", () => {
	const lifecycle = [];
	const queue = new ReleaseQueueState({
		eventGate: new EventGate({ debounceMs: 30_000 }),
		onLifecycle: (record) => lifecycle.push(record),
	});
	const opened = pull(1, {
		transition: "opened",
		webhookAction: "opened",
	});

	queue.applyPullRequestEvent(opened);
	queue.applyPullRequestEvent(opened);
	queue.applyPullRequestEvent(
		pull(1, {
			deliveryId: "synchronize-1",
			receivedAt: 40_000,
			transition: "updated",
			webhookAction: "synchronize",
			headSha: "new-sha-1",
			checks: undefined,
			mergeable: undefined,
			updatedAt: "2026-07-21T01:00:00Z",
		}),
	);
	queue.reconcileRepository("owner/repo", [
		pull(1, {
			deliveryId: undefined,
			headSha: "new-sha-1",
			checks: "fail",
			mergeable: false,
			updatedAt: "2026-07-21T01:00:00Z",
		}),
	]);
	queue.reconcileRepository("owner/repo", [
		pull(1, {
			deliveryId: undefined,
			headSha: "new-sha-1",
			checks: "fail",
			mergeable: false,
			updatedAt: "2026-07-21T01:00:00Z",
		}),
	]);
	queue.applyPullRequestEvent(
		pull(1, {
			deliveryId: "merged-1",
			receivedAt: 80_000,
			action: "closed",
			transition: "merged",
			webhookAction: "closed",
			headSha: "new-sha-1",
			updatedAt: "2026-07-21T02:00:00Z",
		}),
	);

	assert.deepEqual(
		lifecycle.map((record) => [record.transition, record.source]),
		[
			["opened", "webhook"],
			["updated", "webhook"],
			["failed", "reconciliation"],
			["merged", "webhook"],
		],
	);
	assert.equal(new Set(lifecycle.map((record) => record.lifecycleKey)).size, 4);
	assert.equal(lifecycle[0].type, "pr-lifecycle");
	assert.equal(lifecycle[0].deliveryId, "delivery-1");
	assert.equal(lifecycle[1].webhookAction, "synchronize");
	assert.equal(lifecycle[2].reason, "checks-failed");
	assert.equal(lifecycle[3].pullRequest.state, "closed");
});

test("emits reconciliation readiness changes when the PR timestamp is unchanged", () => {
	const lifecycle = [];
	const queue = new ReleaseQueueState({
		onLifecycle: (record) => lifecycle.push(record),
	});
	const updatedAt = "2026-07-21T01:00:00Z";

	queue.applyPullRequestEvent(
		pull(1, {
			transition: "updated",
			webhookAction: "synchronize",
			headSha: "new-sha-1",
			checks: undefined,
			mergeable: undefined,
			updatedAt,
		}),
	);
	queue.reconcileRepository("owner/repo", [
		pull(1, {
			deliveryId: undefined,
			headSha: "new-sha-1",
			checks: "pass",
			checksFingerprint: "checks-pass-1",
			mergeable: true,
			updatedAt,
		}),
	]);

	assert.deepEqual(
		lifecycle.map((record) => [
			record.transition,
			record.source,
			record.pullRequest.mergeable,
			record.pullRequest.checks,
		]),
		[
			["updated", "webhook", null, "pending"],
			["updated", "reconciliation", true, "pass"],
		],
	);
	assert.notEqual(lifecycle[0].lifecycleKey, lifecycle[1].lifecycleKey);
	assert.equal("checksFingerprint" in lifecycle[1].pullRequest, false);
});

test("emits each distinct failing CI attempt on the same PR head", () => {
	const lifecycle = [];
	const queue = new ReleaseQueueState({
		onLifecycle: (record) => lifecycle.push(record),
	});
	const input = {
		deliveryId: undefined,
		headSha: "same-head",
		mergeable: false,
		updatedAt: "2026-07-21T01:00:00Z",
	};

	queue.reconcileRepository("owner/repo", [
		pull(2, { ...input, checks: "fail", checksFingerprint: "failure-1" }),
	]);
	queue.reconcileRepository("owner/repo", [
		pull(2, { ...input, checks: "pass", checksFingerprint: "success-2" }),
	]);
	queue.reconcileRepository("owner/repo", [
		pull(2, { ...input, checks: "fail", checksFingerprint: "failure-3" }),
	]);

	assert.deepEqual(
		lifecycle.map((record) => [record.transition, record.pullRequest.checks]),
		[
			["opened", "fail"],
			["failed", "fail"],
			["updated", "pass"],
			["failed", "fail"],
		],
	);
	assert.notEqual(lifecycle[1].lifecycleKey, lifecycle[3].lifecycleKey);
});

test("reconciliation emits opened and closed fallback records only on state change", () => {
	const lifecycle = [];
	const queue = new ReleaseQueueState({
		onLifecycle: (record) => lifecycle.push(record),
	});

	queue.reconcileRepository("owner/repo", [pull(2, { deliveryId: undefined })]);
	queue.applyPullRequestEvent(
		pull(2, {
			deliveryId: "opened-after-reconcile",
			transition: "opened",
			webhookAction: "opened",
		}),
	);
	queue.reconcileRepository("owner/repo", [pull(2, { deliveryId: undefined })]);
	queue.reconcileRepository("owner/repo", []);
	queue.reconcileRepository("owner/repo", []);

	assert.deepEqual(
		lifecycle.map((record) => [
			record.transition,
			record.source,
			record.reason,
		]),
		[
			["opened", "reconciliation", undefined],
			["closed", "reconciliation", "absent-from-open-pulls"],
		],
	);
});

test("ranks ready pull requests and dispatches when an agent-owned slot frees", () => {
	let now = 1_000;
	const queue = new ReleaseQueueState({ maxMergeSlots: 1, now: () => now });
	const first = queue.applyPullRequestEvent(
		pull(10, { labels: ["priority-p2"] }),
	);
	assert.deepEqual(
		first.dispatches.map((item) => item.number),
		[10],
	);

	now += 1_000;
	const higherPriority = queue.applyPullRequestEvent(
		pull(20, { deliveryId: "delivery-20", labels: ["priority::critical"] }),
	);
	assert.deepEqual(higherPriority.dispatches, []);
	assert.equal(
		queue.snapshot().find((item) => item.number === 20).state,
		"queued",
	);

	assert.deepEqual(
		queue.releaseSlot("owner/repo", 10).map((item) => item.number),
		[20],
	);
	assert.equal(
		queue.snapshot().find((item) => item.number === 20).state,
		"active",
	);

	const closed = queue.applyPullRequestEvent(
		pull(20, {
			deliveryId: "closed-20",
			action: "closed",
			updatedAt: "closed",
		}),
	);
	assert.deepEqual(
		closed.dispatches.map((item) => item.number),
		[10],
	);
});

test("reconciliation blocks changed pull requests and removes closed ones", () => {
	const queue = new ReleaseQueueState({ maxMergeSlots: 2 });
	queue.reconcileRepository("owner/repo", [pull(1), pull(2)]);
	assert.equal(
		queue.snapshot().filter((item) => item.state === "active").length,
		2,
	);

	queue.reconcileRepository("owner/repo", [
		pull(2, { mergeable: false, checks: "fail", deliveryId: undefined }),
	]);
	assert.deepEqual(
		queue.snapshot().map((item) => item.number),
		[2],
	);
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
	assert.deepEqual(
		activeSynchronize.dispatches.map((item) => item.number),
		[2],
	);
	const active = queue.snapshot().find((item) => item.number === 1);
	assert.equal(active.state, "blocked");
	assert.equal(active.checks, "pending");
	assert.equal(active.mergeable, null);
	assert.equal(active.activeSince, null);
	assert.equal(
		queue.snapshot().find((item) => item.number === 3).state,
		"blocked",
	);
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

test("a close tombstone rejects an older open snapshot at the current generation", () => {
	const queue = new ReleaseQueueState();
	queue.applyPullRequestEvent(pull(1));
	queue.applyPullRequestEvent(
		pull(1, {
			deliveryId: "close-before-request",
			action: "closed",
			updatedAt: "2026-07-21T01:00:00Z",
		}),
	);
	const requestGeneration = queue.reconciliationGeneration();
	const staleOpen = pull(1, {
		deliveryId: undefined,
		updatedAt: "2026-07-21T00:00:00Z",
	});

	assert.deepEqual(
		queue.reconcileRepository(
			"owner/repo",
			[staleOpen],
			2_000,
			requestGeneration,
		),
		[],
	);
	assert.deepEqual(queue.snapshot(), []);
	queue.reconcileRepository("owner/repo", [], 3_000, requestGeneration);
	assert.deepEqual(
		queue.reconcileRepository(
			"owner/repo",
			[staleOpen],
			4_000,
			requestGeneration,
		),
		[],
	);
	assert.deepEqual(queue.snapshot(), []);
});
