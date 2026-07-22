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

test("rejects an old REST snapshot that completes after a new head event", async () => {
	const oldPull = {
		number: 3,
		title: "Ready",
		headSha: "old-sha",
		baseRef: "main",
		labels: [],
		draft: false,
		mergeable: true,
		checks: "pass",
		createdAt: "2026-07-20T00:00:00Z",
		updatedAt: "2026-07-21T00:00:00Z",
	};
	const queue = new ReleaseQueueState();
	queue.reconcileRepository("owner/repo", [oldPull]);
	let resolveList;
	const reconciler = new PollingReconciler({
		repositories: ["owner/repo"],
		adapter: {
			listOpenPullRequests: () =>
				new Promise((resolve) => {
					resolveList = resolve;
				}),
		},
		queue,
	});

	const oldRequest = reconciler.reconcileRepository("owner/repo");
	queue.applyPullRequestEvent({
		...oldPull,
		deliveryId: "synchronize-new-sha",
		receivedAt: 1_000,
		action: "upsert",
		repository: "owner/repo",
		headSha: "new-sha",
		mergeable: undefined,
		checks: undefined,
		updatedAt: "2026-07-21T01:00:00Z",
	});
	resolveList([oldPull]);

	assert.deepEqual(await oldRequest, []);
	assert.deepEqual(queue.snapshot(), [
		{
			...oldPull,
			repository: "owner/repo",
			headSha: "new-sha",
			mergeable: null,
			checks: "pending",
			updatedAt: "2026-07-21T01:00:00Z",
			priority: 2,
			state: "blocked",
			activeSince: null,
		},
	]);
});
