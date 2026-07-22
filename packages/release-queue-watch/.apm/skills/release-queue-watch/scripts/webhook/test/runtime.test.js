import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { parseArgs, startReleaseQueueRuntime } from "../src/runtime.js";

function pullRequestPayload(action, overrides = {}) {
	return {
		action,
		repository: { full_name: "owner/repo" },
		pull_request: {
			number: 9,
			title: "Lifecycle PR",
			head: { sha: "head-1" },
			base: { ref: "main" },
			labels: [],
			draft: false,
			mergeable: null,
			merged: false,
			created_at: "2026-07-20T00:00:00Z",
			updated_at: "2026-07-21T00:00:00Z",
			...overrides,
		},
	};
}

test("parses repository, slot, poll, and isolated state options", () => {
	assert.deepEqual(
		parseArgs(
			[
				"--repo=owner/repo",
				"--slots",
				"2",
				"--poll-interval-ms=30000",
				"--state-dir",
				"/tmp/state",
			],
			{},
		),
		{
			repository: "owner/repo",
			host: "127.0.0.1",
			port: 0,
			maxMergeSlots: 2,
			pollIntervalMs: 30_000,
			stateDir: "/tmp/state",
		},
	);
	assert.equal(
		parseArgs(["--", "--repo=owner/repo"], {}).repository,
		"owner/repo",
	);
});

test("rejects missing repositories and unsafe numeric options", () => {
	assert.throws(() => parseArgs([], {}), /--repo/);
	assert.throws(
		() => parseArgs(["--repo", "owner/repo", "--slots", "0"], {}),
		/slots/,
	);
	assert.throws(
		() => parseArgs(["--repo", "owner/repo", "--poll-interval-ms", "10"], {}),
		/poll-interval-ms/,
	);
	assert.throws(
		() => parseArgs(["--repo", "owner/repo", "--port", "65536"], {}),
		/port/,
	);
});

test("starts the signed receiver before forwarding and shuts down cleanly", async (t) => {
	const stateDir = await mkdtemp(join(tmpdir(), "release-queue-runtime-"));
	t.after(() => rm(stateDir, { recursive: true, force: true }));
	const calls = [];
	const runtime = await startReleaseQueueRuntime(
		{
			repository: "owner/repo",
			host: "127.0.0.1",
			port: 0,
			maxMergeSlots: 1,
			pollIntervalMs: 60_000,
			stateDir,
		},
		{
			readToken: async () => "token",
			adapter: { listOpenPullRequests: async () => [] },
			startForwarder: async (options) => {
				calls.push(options);
				return {
					exit: new Promise(() => {}),
					stop: async () => ({ code: 0, signal: "SIGINT" }),
				};
			},
			logger: { log() {}, error() {} },
		},
	);

	assert.equal(
		(await fetch(runtime.receiver.url.replace("/webhooks/github", "/healthz")))
			.status,
		200,
	);
	assert.equal(calls.length, 1);
	assert.equal(calls[0].repository, "owner/repo");
	assert.equal(calls[0].url, runtime.receiver.url);
	assert.match(calls[0].secret, /^[a-f0-9]{64}$/);
	await runtime.stop();
});

test("forwards unchanged records to the advisory dispatcher and drains it", async (t) => {
	const stateDir = await mkdtemp(join(tmpdir(), "release-queue-runtime-wake-"));
	t.after(() => rm(stateDir, { recursive: true, force: true }));
	const records = [];
	let drained = false;
	const runtime = await startReleaseQueueRuntime(
		{
			repository: "owner/repo",
			host: "127.0.0.1",
			port: 0,
			maxMergeSlots: 1,
			pollIntervalMs: 60_000,
			stateDir,
		},
		{
			readToken: async () => "token",
			adapter: { listOpenPullRequests: async () => [] },
			startForwarder: async () => ({
				exit: new Promise(() => {}),
				stop: async () => ({ code: 0, signal: "SIGINT" }),
			}),
			wakeDispatcher: {
				enqueue: async (record) => records.push(record),
				drain: async () => {
					drained = true;
				},
			},
			logger: { log() {}, error() {} },
		},
	);

	await runtime.wakeDispatcher.drain();
	assert.deepEqual(records.map((record) => record.type), ["watcher-active"]);
	await runtime.stop();
	assert.equal(drained, true);
});

test("quiesces producers before the final dispatcher drain", async (t) => {
	const stateDir = await mkdtemp(
		join(tmpdir(), "release-queue-runtime-quiesce-"),
	);
	t.after(() => rm(stateDir, { recursive: true, force: true }));
	let adapterCalls = 0;
	let resolveReconciliation;
	const pendingReconciliation = new Promise((resolve) => {
		resolveReconciliation = resolve;
	});
	const wakeEvents = [];
	const runtime = await startReleaseQueueRuntime(
		{
			repository: "owner/repo",
			host: "127.0.0.1",
			port: 0,
			maxMergeSlots: 1,
			pollIntervalMs: 60_000,
			stateDir,
		},
		{
			readToken: async () => "token",
			adapter: {
				listOpenPullRequests: async () => {
					adapterCalls += 1;
					return adapterCalls === 1 ? [] : pendingReconciliation;
				},
			},
			startForwarder: async () => ({
				exit: new Promise(() => {}),
				stop: async () => ({ code: 0, signal: "SIGINT" }),
			}),
			wakeDispatcher: {
				enqueue: async (record) => wakeEvents.push(`enqueue:${record.type}`),
				drain: async () => wakeEvents.push("drain"),
			},
			logger: { log() {}, error() {} },
		},
	);
	const reconciliation = runtime.reconciler.reconcileRepository("owner/repo");
	await new Promise((resolve) => setImmediate(resolve));
	const stopping = runtime.stop();
	await new Promise((resolve) => setImmediate(resolve));
	assert.equal(wakeEvents.includes("drain"), false);

	resolveReconciliation([
		{
			number: 8,
			title: "Ready during shutdown",
			headSha: "head-8",
			baseRef: "main",
			labels: [],
			draft: false,
			mergeable: true,
			checks: "pass",
			checksFingerprint: "attempt-1",
			createdAt: "2026-07-20T00:00:00Z",
			updatedAt: "2026-07-21T00:00:00Z",
		},
	]);
	await reconciliation;
	await stopping;
	await new Promise((resolve) => setImmediate(resolve));

	assert.deepEqual(wakeEvents.slice(-3), [
		"enqueue:pr-lifecycle",
		"enqueue:dispatch",
		"drain",
	]);
	assert.equal(wakeEvents.at(-1), "drain");
});

test("logs non-Error wake rejection without an unhandled rejection", async (t) => {
	const stateDir = await mkdtemp(
		join(tmpdir(), "release-queue-runtime-wake-error-"),
	);
	t.after(() => rm(stateDir, { recursive: true, force: true }));
	const unhandled = [];
	const onUnhandled = (reason) => unhandled.push(reason);
	process.on("unhandledRejection", onUnhandled);
	t.after(() => process.off("unhandledRejection", onUnhandled));
	const errors = [];
	const runtime = await startReleaseQueueRuntime(
		{
			repository: "owner/repo",
			host: "127.0.0.1",
			port: 0,
			maxMergeSlots: 1,
			pollIntervalMs: 60_000,
			stateDir,
		},
		{
			readToken: async () => "token",
			adapter: { listOpenPullRequests: async () => [] },
			startForwarder: async () => ({
				exit: new Promise(() => {}),
				stop: async () => ({ code: 0, signal: "SIGINT" }),
			}),
			wakeDispatcher: {
				enqueue: async () => Promise.reject(null),
				drain: async () => {},
			},
			logger: {
				log() {},
				error: (line) => errors.push(JSON.parse(line)),
			},
		},
	);
	await new Promise((resolve) => setImmediate(resolve));
	await runtime.stop();
	await new Promise((resolve) => setImmediate(resolve));

	assert.deepEqual(unhandled, []);
	assert.deepEqual(errors, [{ type: "wake-error", message: "null" }]);
});

test("retries failed forwarder cleanup without leaking the receiver", async (t) => {
	const stateDir = await mkdtemp(
		join(tmpdir(), "release-queue-runtime-retry-"),
	);
	t.after(() => rm(stateDir, { recursive: true, force: true }));
	let stopCalls = 0;
	const runtime = await startReleaseQueueRuntime(
		{
			repository: "owner/repo",
			host: "127.0.0.1",
			port: 0,
			maxMergeSlots: 1,
			pollIntervalMs: 60_000,
			stateDir,
		},
		{
			readToken: async () => "token",
			adapter: { listOpenPullRequests: async () => [] },
			startForwarder: async () => ({
				exit: new Promise(() => {}),
				stop: async () => {
					stopCalls += 1;
					if (stopCalls === 1)
						throw new Error("transient forwarder stop failure");
				},
			}),
			logger: { log() {}, error() {} },
		},
	);
	const healthUrl = runtime.receiver.url.replace(
		"/webhooks/github",
		"/healthz",
	);

	await assert.rejects(runtime.stop(), /shutdown did not complete/);
	await assert.rejects(fetch(healthUrl));
	await runtime.stop();
	assert.equal(stopCalls, 2);
});

test("writes verified and deduplicated pull request lifecycle records", async (t) => {
	const stateDir = await mkdtemp(
		join(tmpdir(), "release-queue-runtime-lifecycle-"),
	);
	const output = [];
	const runtime = await startReleaseQueueRuntime(
		{
			repository: "owner/repo",
			host: "127.0.0.1",
			port: 0,
			maxMergeSlots: 1,
			pollIntervalMs: 60_000,
			stateDir,
		},
		{
			readToken: async () => "token",
			adapter: { listOpenPullRequests: async () => [] },
			startForwarder: async () => ({
				exit: new Promise(() => {}),
				stop: async () => ({ code: 0, signal: "SIGINT" }),
			}),
			logger: {
				log: (line) => output.push(JSON.parse(line)),
				error() {},
			},
		},
	);
	t.after(async () => {
		await runtime.stop();
		await rm(stateDir, { recursive: true, force: true });
	});

	const send = async (payload, delivery, signature) => {
		const body = JSON.stringify(payload);
		const signed = signature ?? (await runtime.receiver.webhooks.sign(body));
		return fetch(runtime.receiver.url, {
			method: "POST",
			headers: {
				"content-type": "application/json",
				"x-github-delivery": delivery,
				"x-github-event": "pull_request",
				"x-hub-signature-256": signed,
			},
			body,
		});
	};

	const opened = pullRequestPayload("opened");
	assert.equal((await send(opened, "opened-9")).status, 200);
	assert.equal((await send(opened, "opened-9")).status, 200);
	assert.equal(
		(
			await send(
				pullRequestPayload("synchronize", {
					head: { sha: "head-2" },
					updated_at: "2026-07-21T01:00:00Z",
				}),
				"sync-9",
			)
		).status,
		200,
	);
	assert.equal(
		(
			await send(
				pullRequestPayload("closed", {
					head: { sha: "head-2" },
					merged: true,
					updated_at: "2026-07-21T02:00:00Z",
				}),
				"merged-9",
			)
		).status,
		200,
	);
	assert.equal(
		(
			await send(
				pullRequestPayload("opened", {
					number: 10,
					title: "Closed lifecycle PR",
					head: { sha: "head-10" },
					updated_at: "2026-07-21T03:00:00Z",
				}),
				"opened-10",
			)
		).status,
		200,
	);
	assert.equal(
		(
			await send(
				pullRequestPayload("closed", {
					number: 10,
					title: "Closed lifecycle PR",
					head: { sha: "head-10" },
					updated_at: "2026-07-21T04:00:00Z",
				}),
				"closed-10",
			)
		).status,
		200,
	);
	assert.equal((await send(opened, "invalid-9", "sha256=invalid")).status, 400);

	const lifecycle = output.filter((record) => record.type === "pr-lifecycle");
	assert.deepEqual(
		lifecycle.map((record) => record.transition),
		["opened", "updated", "merged", "opened", "closed"],
	);
	assert.equal(lifecycle[0].deliveryId, "opened-9");
	assert.equal(lifecycle[1].webhookAction, "synchronize");
	assert.equal(lifecycle[2].pullRequest.headSha, "head-2");
	assert.equal(lifecycle[4].pullRequest.number, 10);
});

test("writes reconciled lifecycle records without changing dispatch records", async (t) => {
	const stateDir = await mkdtemp(
		join(tmpdir(), "release-queue-runtime-reconcile-"),
	);
	const output = [];
	const pull = (number, overrides = {}) => ({
		number,
		title: `PR ${number}`,
		headSha: `head-${number}`,
		baseRef: "main",
		labels: [],
		draft: false,
		mergeable: true,
		checks: "pass",
		createdAt: "2026-07-20T00:00:00Z",
		updatedAt: "2026-07-21T00:00:00Z",
		...overrides,
	});
	const runtime = await startReleaseQueueRuntime(
		{
			repository: "owner/repo",
			host: "127.0.0.1",
			port: 0,
			maxMergeSlots: 1,
			pollIntervalMs: 60_000,
			stateDir,
		},
		{
			readToken: async () => "token",
			adapter: {
				listOpenPullRequests: async () => [
					pull(12, { checks: "fail", mergeable: false }),
					pull(13),
				],
			},
			startForwarder: async () => ({
				exit: new Promise(() => {}),
				stop: async () => ({ code: 0, signal: "SIGINT" }),
			}),
			logger: {
				log: (line) => output.push(JSON.parse(line)),
				error() {},
			},
		},
	);
	t.after(async () => {
		await runtime.stop();
		await rm(stateDir, { recursive: true, force: true });
	});

	const lifecycle = output.filter((record) => record.type === "pr-lifecycle");
	assert.deepEqual(
		lifecycle.map((record) => [
			record.pullRequest.number,
			record.transition,
			record.source,
		]),
		[
			[12, "opened", "reconciliation"],
			[12, "failed", "reconciliation"],
			[13, "opened", "reconciliation"],
		],
	);
	const dispatch = output.find((record) => record.type === "dispatch");
	assert.deepEqual(Object.keys(dispatch), ["type", "pullRequest"]);
	assert.equal("checksFingerprint" in dispatch.pullRequest, false);
	assert.equal(dispatch.pullRequest.number, 13);
	assert.ok(
		output.indexOf(dispatch) <
			output.findIndex((record) => record.type === "watcher-active"),
	);
});
