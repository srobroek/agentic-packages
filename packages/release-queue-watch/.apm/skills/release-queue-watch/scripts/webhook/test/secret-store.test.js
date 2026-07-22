import assert from "node:assert/strict";
import { mkdtemp, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { loadOrCreateWebhookSecret } from "../src/secret-store.js";

test("creates one random persisted secret with private permissions", async (t) => {
	const stateDir = await mkdtemp(join(tmpdir(), "release-queue-secret-"));
	t.after(() => rm(stateDir, { recursive: true, force: true }));
	let randomCalls = 0;
	const randomBytes = () => {
		randomCalls += 1;
		return Buffer.alloc(32, 0xab);
	};

	const first = await loadOrCreateWebhookSecret(stateDir, { randomBytes });
	const second = await loadOrCreateWebhookSecret(stateDir, { randomBytes });

	assert.equal(first.created, true);
	assert.equal(second.created, false);
	assert.equal(first.secret, "ab".repeat(32));
	assert.equal(second.secret, first.secret);
	assert.equal(randomCalls, 1);
	assert.equal((await stat(first.path)).mode & 0o777, 0o600);
	assert.equal((await stat(stateDir)).mode & 0o777, 0o700);
});
