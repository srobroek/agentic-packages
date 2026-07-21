import assert from "node:assert/strict";
import test from "node:test";
import { combinedChecksState, OctokitRestAdapter } from "../src/rest-adapter.js";

test("combines check runs and commit statuses conservatively", () => {
  assert.equal(
    combinedChecksState([{ status: "completed", conclusion: "success" }], {
      state: "success",
      total_count: 1,
    }),
    "pass",
  );
  assert.equal(
    combinedChecksState([{ status: "in_progress", conclusion: null }], {
      state: "success",
      total_count: 1,
    }),
    "pending",
  );
  assert.equal(
    combinedChecksState([{ status: "completed", conclusion: "failure" }], {
      state: "success",
      total_count: 1,
    }),
    "fail",
  );
  assert.equal(combinedChecksState([], { state: "pending", total_count: 0 }), "pending");
  assert.equal(
    combinedChecksState([{ status: "completed", conclusion: "success" }], {
      state: "pending",
      total_count: 0,
    }),
    "pass",
  );
});

test("maps Octokit REST pull, mergeability, and check responses", async () => {
  const pullsList = () => {};
  const checksListForRef = () => {};
  const calls = [];
  const octokit = {
    rest: {
      pulls: {
        list: pullsList,
        get: async (args) => {
          calls.push(["get", args]);
          return { data: { mergeable: true, mergeable_state: "clean" } };
        },
      },
      checks: { listForRef: checksListForRef },
      repos: {
        getCombinedStatusForRef: async (args) => {
          calls.push(["status", args]);
          return { data: { state: "success", total_count: 1 } };
        },
      },
    },
    paginate: async (method, args) => {
      calls.push(["paginate", args]);
      if (method === pullsList) {
        return [
          {
            number: 7,
            title: "Ready",
            head: { sha: "abc" },
            base: { ref: "main" },
            labels: [{ name: "priority-p1" }],
            draft: false,
            created_at: "2026-07-20T00:00:00Z",
            updated_at: "2026-07-21T00:00:00Z",
          },
        ];
      }
      if (method === checksListForRef) {
        return [{ status: "completed", conclusion: "success" }];
      }
      throw new Error("unexpected paginate method");
    },
  };

  const adapter = new OctokitRestAdapter({ octokit });
  const result = await adapter.listOpenPullRequests("owner/repo");

  assert.deepEqual(result, [
    {
      number: 7,
      title: "Ready",
      headSha: "abc",
      baseRef: "main",
      labels: ["priority-p1"],
      draft: false,
      mergeable: true,
      checks: "pass",
      createdAt: "2026-07-20T00:00:00Z",
      updatedAt: "2026-07-21T00:00:00Z",
    },
  ]);
  assert.equal(calls.some(([, args]) => args.owner === "owner" && args.repo === "repo"), true);
});

test("does not claim readiness from passing checks while the merge state is blocked", async () => {
  const pullsList = () => {};
  const checksListForRef = () => {};
  const octokit = {
    rest: {
      pulls: {
        list: pullsList,
        get: async () => ({ data: { mergeable: true, mergeable_state: "blocked" } }),
      },
      checks: { listForRef: checksListForRef },
      repos: {
        getCombinedStatusForRef: async () => ({
          data: { state: "success", total_count: 0 },
        }),
      },
    },
    paginate: async (method) => {
      if (method === pullsList) {
        return [
          {
            number: 8,
            title: "Blocked by a required signal",
            head: { sha: "def" },
            base: { ref: "main" },
            labels: [],
            draft: false,
            created_at: "2026-07-20T00:00:00Z",
            updated_at: "2026-07-21T00:00:00Z",
          },
        ];
      }
      if (method === checksListForRef) {
        return [{ status: "completed", conclusion: "success" }];
      }
      throw new Error("unexpected paginate method");
    },
  };

  const [pullRequest] = await new OctokitRestAdapter({ octokit }).listOpenPullRequests(
    "owner/repo",
  );
  assert.equal(pullRequest.checks, "pass");
  assert.equal(pullRequest.mergeable, false);
});
