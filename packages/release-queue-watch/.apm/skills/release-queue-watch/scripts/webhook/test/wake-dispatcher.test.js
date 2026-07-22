import assert from "node:assert/strict";
import test from "node:test";
import { AdvisoryWakeDispatcher } from "../src/wake-dispatcher.js";

const dispatch = {
	type: "dispatch",
	pullRequest: {
		repository: "owner/repo",
		number: 42,
		headSha: "abc1234",
	},
};

function dispatcher(overrides = {}) {
	return new AdvisoryWakeDispatcher({
		resolveOrchestrate: async () => ({ status: "unmatched" }),
		resolveShepherd: async () => ({ status: "ignored" }),
		wakeOrchestrate: async () => {},
		wakeShepherd: async () => {},
		...overrides,
	});
}

test("routes an exact orchestrate owner without consulting the shepherd", async () => {
	let shepherdCalls = 0;
	const wakes = [];
	const subject = dispatcher({
		resolveOrchestrate: async () => ({
			status: "resolved",
			node: "orc-run.7",
			dispatchKey: "owner/repo#42@abc1234",
			repository: "owner/repo",
			number: 42,
			headSha: "abc1234",
			branch: "feat/change",
			baseSha: "base1234",
			requiredMetadata: {
				queue_dispatch: "owner/repo#42@abc1234",
				queue_dispatch_pending: "owner/repo#42@abc1234",
			},
		}),
		resolveShepherd: async () => {
			shepherdCalls += 1;
			return { status: "resolved" };
		},
		wakeOrchestrate: async (payload) => wakes.push(payload),
	});

	const result = await subject.enqueue(dispatch);

	assert.equal(result.route, "orchestrate");
	assert.equal(shepherdCalls, 0);
	assert.deepEqual(wakes, [
		{
			target: { kind: "orchestrate", id: "orc-run.7" },
			verb: "APPROVE",
			eventType: "dispatch",
			identity: "owner/repo#42@abc1234",
			repository: "owner/repo",
			number: 42,
			headSha: "abc1234",
			transition: undefined,
			branch: "feat/change",
			baseSha: "base1234",
			requiredMetadata: {
				queue_dispatch: "owner/repo#42@abc1234",
				queue_dispatch_pending: "owner/repo#42@abc1234",
			},
		},
	]);
});

test("routes the unchanged identity to pr-shepherd only after explicit unmatched", async () => {
	const records = [];
	const wakes = [];
	const subject = dispatcher({
		resolveShepherd: async (record) => {
			records.push(record);
			return {
				status: "replay",
				bead: "merge-42",
				eventKey: "dispatch:owner/repo#42@abc1234",
				eventType: "dispatch",
				transition: "ready",
				repository: "owner/repo",
				number: 42,
				headSha: "abc1234",
				requiredMetadata: {},
			};
		},
		wakeShepherd: async (payload) => wakes.push(payload),
	});

	const result = await subject.enqueue(dispatch);

	assert.equal(result.route, "pr-shepherd");
	assert.equal(records[0], dispatch);
	assert.deepEqual(wakes[0].target, {
		kind: "pr-shepherd",
		id: "merge-42",
	});
	assert.equal(wakes[0].action, "run-pass");
	assert.equal(wakes[0].identity, "dispatch:owner/repo#42@abc1234");
	assert.equal(wakes[0].headSha, "abc1234");
});

test("never falls through ambiguous orchestrate ownership", async () => {
	let shepherdCalls = 0;
	const fallbacks = [];
	const subject = dispatcher({
		resolveOrchestrate: async () => ({ status: "invalid" }),
		resolveShepherd: async () => {
			shepherdCalls += 1;
			return { status: "resolved" };
		},
		onFallback: async (fallback) => fallbacks.push(fallback),
	});

	const result = await subject.enqueue(dispatch);

	assert.equal(result.reason, "orchestrate-ownership-error");
	assert.equal(shepherdCalls, 0);
	assert.equal(fallbacks.length, 1);
});

test("rejects a resolved route with missing target identity", async () => {
	let wakes = 0;
	const subject = dispatcher({
		resolveOrchestrate: async () => ({
			status: "resolved",
			dispatchKey: "owner/repo#42@abc1234",
			repository: "owner/repo",
			number: 42,
			headSha: "abc1234",
		}),
		wakeOrchestrate: async () => {
			wakes += 1;
		},
	});

	const result = await subject.enqueue(dispatch);

	assert.equal(result.reason, "invalid-orchestrate-result");
	assert.equal(wakes, 0);
});

test("suppresses acknowledged duplicates and informational lifecycle records", async () => {
	let wakes = 0;
	const duplicate = dispatcher({
		resolveOrchestrate: async () => ({ status: "duplicate" }),
		wakeOrchestrate: async () => {
			wakes += 1;
		},
	});
	const informational = dispatcher({
		resolveOrchestrate: async () => ({
			status: "resolved",
			wakeGatekeeper: false,
			requiredMetadata: { queue_lifecycle_ack: "lifecycle:key" },
		}),
		wakeOrchestrate: async () => {
			wakes += 1;
		},
	});

	assert.equal((await duplicate.enqueue(dispatch)).status, "duplicate");
	assert.equal(
		(await informational.enqueue({ type: "pr-lifecycle" })).status,
		"observed",
	);
	assert.equal(wakes, 0);
});

test("surfaces malformed output without resolving or waking", async () => {
	let resolves = 0;
	const fallbacks = [];
	const subject = dispatcher({
		resolveOrchestrate: async () => {
			resolves += 1;
			return { status: "unmatched" };
		},
		onFallback: async (fallback) => fallbacks.push(fallback),
	});

	const result = await subject.enqueueLine("not-json", "stderr");

	assert.equal(result.reason, "malformed-output");
	assert.equal(result.source, "stderr");
	assert.equal(resolves, 0);
	assert.equal(fallbacks.length, 1);
});

test("normalizes unknown orchestrate resolver failures", async () => {
	const fallbacks = [];
	const subject = dispatcher({
		resolveOrchestrate: async () => {
			throw null;
		},
		onFallback: async (fallback) => fallbacks.push(fallback),
	});

	const result = await subject.enqueue(dispatch);

	assert.equal(result.reason, "orchestrate-resolution-error");
	assert.equal(result.message, "null");
	assert.deepEqual(fallbacks, [result]);
});

test("normalizes unknown standalone resolver failures", async () => {
	const fallbacks = [];
	const subject = dispatcher({
		resolveShepherd: async () => {
			throw { code: "standalone-failed" };
		},
		onFallback: async (fallback) => fallbacks.push(fallback),
	});

	const result = await subject.enqueue(dispatch);

	assert.equal(result.reason, "shepherd-resolution-error");
	assert.equal(result.message, '{"code":"standalone-failed"}');
	assert.deepEqual(fallbacks, [result]);
});

test("keeps one wake in flight and preserves input order", async () => {
	let releaseFirst;
	let inFlight = 0;
	let maxInFlight = 0;
	const started = [];
	const firstBlocked = new Promise((resolve) => {
		releaseFirst = resolve;
	});
	const subject = dispatcher({
		resolveOrchestrate: async (record) => ({
			status: "resolved",
			node: `node-${record.pullRequest.number}`,
			dispatchKey: `owner/repo#${record.pullRequest.number}@abc1234`,
			repository: "owner/repo",
			number: record.pullRequest.number,
			headSha: "abc1234",
			branch: "feat/change",
			baseSha: "base1234",
		}),
		wakeOrchestrate: async (payload) => {
			inFlight += 1;
			maxInFlight = Math.max(maxInFlight, inFlight);
			started.push(payload.number);
			if (payload.number === 1) await firstBlocked;
			inFlight -= 1;
		},
	});

	const first = subject.enqueue({
		...dispatch,
		pullRequest: { ...dispatch.pullRequest, number: 1 },
	});
	const second = subject.enqueue({
		...dispatch,
		pullRequest: { ...dispatch.pullRequest, number: 2 },
	});
	await new Promise((resolve) => setImmediate(resolve));
	assert.deepEqual(started, [1]);
	releaseFirst();
	await Promise.all([first, second, subject.drain()]);

	assert.deepEqual(started, [1, 2]);
	assert.equal(maxInFlight, 1);
});

test("continues after a failed wake without overlapping the next record", async () => {
	const started = [];
	const subject = dispatcher({
		resolveOrchestrate: async (record) => ({
			status: "resolved",
			node: `node-${record.pullRequest.number}`,
			dispatchKey: `owner/repo#${record.pullRequest.number}@abc1234`,
			repository: "owner/repo",
			number: record.pullRequest.number,
			headSha: "abc1234",
			branch: "feat/change",
			baseSha: "base1234",
		}),
		wakeOrchestrate: async (payload) => {
			started.push(payload.number);
			if (payload.number === 1) throw new Error("wake failed");
		},
	});

	await assert.rejects(
		subject.enqueue({
			...dispatch,
			pullRequest: { ...dispatch.pullRequest, number: 1 },
		}),
		/wake failed/,
	);
	await subject.enqueue({
		...dispatch,
		pullRequest: { ...dispatch.pullRequest, number: 2 },
	});

	assert.deepEqual(started, [1, 2]);
});
