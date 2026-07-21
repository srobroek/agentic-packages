import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { parseArgs, startReleaseQueueRuntime } from "../src/runtime.js";

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
  assert.equal(parseArgs(["--", "--repo=owner/repo"], {}).repository, "owner/repo");
});

test("rejects missing repositories and unsafe numeric options", () => {
  assert.throws(() => parseArgs([], {}), /--repo/);
  assert.throws(() => parseArgs(["--repo", "owner/repo", "--slots", "0"], {}), /slots/);
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

  assert.equal((await fetch(runtime.receiver.url.replace("/webhooks/github", "/healthz"))).status, 200);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].repository, "owner/repo");
  assert.equal(calls[0].url, runtime.receiver.url);
  assert.match(calls[0].secret, /^[a-f0-9]{64}$/);
  await runtime.stop();
});

test("retries failed forwarder cleanup without leaking the receiver", async (t) => {
  const stateDir = await mkdtemp(join(tmpdir(), "release-queue-runtime-retry-"));
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
          if (stopCalls === 1) throw new Error("transient forwarder stop failure");
        },
      }),
      logger: { log() {}, error() {} },
    },
  );
  const healthUrl = runtime.receiver.url.replace("/webhooks/github", "/healthz");

  await assert.rejects(runtime.stop(), /shutdown did not complete/);
  await assert.rejects(fetch(healthUrl));
  await runtime.stop();
  assert.equal(stopCalls, 2);
});
