import { EventGate } from "./event-gate.js";

const PRIORITY_LABELS = new Map([
  ["p0", 0],
  ["priority-p0", 0],
  ["priority::critical", 0],
  ["priority:critical", 0],
  ["p1", 1],
  ["priority-p1", 1],
  ["priority::high", 1],
  ["priority:high", 1],
  ["p2", 2],
  ["priority-p2", 2],
  ["priority::medium", 2],
  ["priority:medium", 2],
  ["p3", 3],
  ["priority-p3", 3],
  ["priority::low", 3],
  ["priority:low", 3],
  ["p4", 4],
  ["priority-p4", 4],
  ["priority::backlog", 4],
  ["priority:backlog", 4],
]);

function priorityFromLabels(labels) {
  const priorities = labels
    .map((label) => PRIORITY_LABELS.get(label.toLowerCase()))
    .filter((priority) => priority !== undefined);
  return priorities.length === 0 ? 2 : Math.min(...priorities);
}

function compareQueueItems(left, right) {
  return (
    left.priority - right.priority ||
    left.createdAt.localeCompare(right.createdAt) ||
    left.repository.localeCompare(right.repository) ||
    left.number - right.number
  );
}

function keyFor(repository, number) {
  return `${repository}#${number}`;
}

function isEligible(item) {
  return !item.draft && item.mergeable === true && item.checks === "pass";
}

function cloneItem(item) {
  return { ...item, labels: [...item.labels] };
}

export class ReleaseQueueState {
  constructor({ maxMergeSlots = 1, eventGate = new EventGate(), now = Date.now } = {}) {
    if (!Number.isInteger(maxMergeSlots) || maxMergeSlots < 1) {
      throw new Error("maxMergeSlots must be a positive integer");
    }
    this.maxMergeSlots = maxMergeSlots;
    this.eventGate = eventGate;
    this.now = now;
    this.items = new Map();
  }

  applyPullRequestEvent(event) {
    const gate = this.eventGate.accept({
      deliveryId: event.deliveryId,
      fingerprint: [
        event.repository,
        event.number,
        event.action,
        event.headSha,
        event.updatedAt,
      ].join(":"),
      receivedAt: event.receivedAt,
    });
    if (!gate.accepted) return { ...gate, dispatches: [] };

    if (event.action === "closed") {
      this.items.delete(keyFor(event.repository, event.number));
    } else {
      this.#upsert(event, event.receivedAt ?? this.now());
    }
    return { ...gate, dispatches: this.dispatchAvailable() };
  }

  reconcileRepository(repository, pullRequests, observedAt = this.now()) {
    const seen = new Set();
    for (const pullRequest of pullRequests) {
      seen.add(keyFor(repository, pullRequest.number));
      this.#upsert({ ...pullRequest, repository }, observedAt);
    }
    for (const [key, item] of this.items) {
      if (item.repository === repository && !seen.has(key)) this.items.delete(key);
    }
    return this.dispatchAvailable();
  }

  releaseSlot(repository, number) {
    const item = this.items.get(keyFor(repository, number));
    if (!item || item.state !== "active") return [];
    item.state = isEligible(item) ? "queued" : "blocked";
    item.activeSince = null;
    return this.dispatchAvailable();
  }

  dispatchAvailable() {
    const activeCount = [...this.items.values()].filter((item) => item.state === "active").length;
    const available = this.maxMergeSlots - activeCount;
    if (available <= 0) return [];

    const candidates = [...this.items.values()]
      .filter((item) => item.state === "queued" && isEligible(item))
      .sort(compareQueueItems)
      .slice(0, available);
    const activatedAt = new Date(this.now()).toISOString();
    for (const item of candidates) {
      item.state = "active";
      item.activeSince = activatedAt;
    }
    return candidates.map(cloneItem);
  }

  snapshot() {
    return [...this.items.values()].sort(compareQueueItems).map(cloneItem);
  }

  #upsert(input, observedAt) {
    const key = keyFor(input.repository, input.number);
    const previous = this.items.get(key);
    const headChanged =
      previous !== undefined && input.headSha !== undefined && input.headSha !== previous.headSha;
    const labels = (input.labels ?? previous?.labels ?? []).map((label) =>
      typeof label === "string" ? label : label.name,
    );
    const item = {
      repository: input.repository,
      number: input.number,
      title: input.title ?? previous?.title ?? "",
      headSha: input.headSha ?? previous?.headSha ?? "",
      baseRef: input.baseRef ?? previous?.baseRef ?? "main",
      labels,
      priority: input.priority ?? priorityFromLabels(labels),
      draft: input.draft ?? previous?.draft ?? false,
      mergeable: input.mergeable ?? (headChanged ? null : previous?.mergeable) ?? null,
      checks: input.checks ?? (headChanged ? "pending" : previous?.checks) ?? "pending",
      createdAt:
        input.createdAt ?? previous?.createdAt ?? new Date(observedAt).toISOString(),
      updatedAt: input.updatedAt ?? new Date(observedAt).toISOString(),
      state: headChanged ? "blocked" : (previous?.state ?? "blocked"),
      activeSince: headChanged ? null : (previous?.activeSince ?? null),
    };

    if (!isEligible(item)) {
      item.state = "blocked";
      item.activeSince = null;
    } else if (item.state !== "active") {
      item.state = "queued";
    }
    this.items.set(key, item);
  }
}
