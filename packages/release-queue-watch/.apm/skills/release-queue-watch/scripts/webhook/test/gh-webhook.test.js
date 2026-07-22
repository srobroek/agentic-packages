import assert from "node:assert/strict";
import test from "node:test";
import {
	buildForwardArgs,
	ensureGhWebhookExtension,
	readGhToken,
} from "../src/gh-webhook.js";

test("provisions cli/gh-webhook in the isolated data directory", async () => {
	const calls = [];
	const execFileFn = async (command, args, options) => {
		calls.push({ command, args, dataDir: options.env.XDG_DATA_HOME });
		return { stdout: args[1] === "list" ? "" : "installed" };
	};

	await ensureGhWebhookExtension({
		dataDir: "/tmp/release-queue-gh-test",
		env: {},
		execFileFn,
	});

	assert.deepEqual(calls, [
		{
			command: "gh",
			args: ["extension", "list"],
			dataDir: "/tmp/release-queue-gh-test",
		},
		{
			command: "gh",
			args: ["extension", "install", "cli/gh-webhook"],
			dataDir: "/tmp/release-queue-gh-test",
		},
	]);
});

test("passes the secret through the only supported single-user argv boundary", () => {
	const args = buildForwardArgs({
		repository: "owner/repo",
		events: ["pull_request", "check_run"],
		secret: "secret",
		url: "http://127.0.0.1:3000/webhooks/github",
	});
	assert.deepEqual(args, [
		"webhook",
		"forward",
		"--repo=owner/repo",
		"--events=pull_request,check_run",
		"--secret=secret",
		"--url=http://127.0.0.1:3000/webhooks/github",
	]);
	assert.equal(args.join(" ").includes("smee"), false);
});

test("prefers an injected GitHub token and never shells for it", async () => {
	const token = await readGhToken({
		env: { GH_TOKEN: "token" },
		execFileFn: async () => {
			throw new Error("should not execute gh");
		},
	});
	assert.equal(token, "token");
});
