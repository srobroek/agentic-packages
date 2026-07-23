import assert from "node:assert/strict";
import test from "node:test";
import { ReleaseQueueState } from "../src/queue-state.js";
import { createWebhookReceiver } from "../src/webhook-receiver.js";

function payload() {
	return {
		action: "opened",
		repository: { full_name: "owner/repo" },
		pull_request: {
			number: 9,
			title: "Webhook PR",
			head: { sha: "abc" },
			base: { ref: "main" },
			labels: [{ name: "priority-p1" }],
			draft: false,
			mergeable: null,
			created_at: "2026-07-20T00:00:00Z",
			updated_at: "2026-07-21T00:00:00Z",
		},
	};
}

test("accepts signed events and rejects invalid signatures", async (t) => {
	const dirty = [];
	const events = [];
	const receiver = await createWebhookReceiver({
		secret: "test-secret",
		queue: new ReleaseQueueState(),
		onRepositoryDirty: (repository) => dirty.push(repository),
		onEvent: (event) => events.push(event),
	});
	t.after(() => receiver.close());
	const body = JSON.stringify(payload());
	const signature = await receiver.webhooks.sign(body);
	const send = (candidateSignature, delivery) =>
		fetch(receiver.url, {
			method: "POST",
			headers: {
				"content-type": "application/json",
				"x-github-delivery": delivery,
				"x-github-event": "pull_request",
				"x-hub-signature-256": candidateSignature,
			},
			body,
		});

	assert.equal((await send(signature, "valid-delivery")).status, 200);
	assert.equal(dirty.length, 1);
	assert.equal(events[0].event.number, 9);
	assert.equal((await send("sha256=invalid", "invalid-delivery")).status, 400);
	assert.equal(events.length, 1);
});

test("debounces equivalent check events before requesting reconciliation", async (t) => {
	const dirty = [];
	const events = [];
	const receiver = await createWebhookReceiver({
		secret: "test-secret",
		queue: new ReleaseQueueState(),
		onRepositoryDirty: (repository) => dirty.push(repository),
		onEvent: (event) => events.push(event),
		now: () => 1_000,
	});
	t.after(() => receiver.close());
	const body = JSON.stringify({
		repository: { full_name: "owner/repo" },
		check_run: { id: 42, status: "completed", conclusion: "success" },
	});
	const signature = await receiver.webhooks.sign(body);
	const send = (delivery) =>
		fetch(receiver.url, {
			method: "POST",
			headers: {
				"content-type": "application/json",
				"x-github-delivery": delivery,
				"x-github-event": "check_run",
				"x-hub-signature-256": signature,
			},
			body,
		});

	assert.equal((await send("check-1")).status, 200);
	assert.equal((await send("check-2")).status, 200);
	assert.deepEqual(dirty, ["owner/repo"]);
	assert.equal(events.length, 1);
});
