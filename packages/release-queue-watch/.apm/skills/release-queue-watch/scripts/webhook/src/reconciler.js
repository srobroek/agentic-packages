export class PollingReconciler {
  constructor({
    repositories,
    adapter,
    queue,
    intervalMs = 60_000,
    webhookDebounceMs = 500,
    onDispatch = () => {},
    onError = () => {},
  }) {
    if (!repositories?.length) throw new Error("at least one repository is required");
    this.repositories = new Set(repositories);
    this.adapter = adapter;
    this.queue = queue;
    this.intervalMs = intervalMs;
    this.webhookDebounceMs = webhookDebounceMs;
    this.onDispatch = onDispatch;
    this.onError = onError;
    this.inFlight = new Map();
    this.requestTimers = new Map();
    this.timer = null;
  }

  async reconcileRepository(repository) {
    if (this.inFlight.has(repository)) return this.inFlight.get(repository);
    const operation = this.adapter
      .listOpenPullRequests(repository)
      .then((pullRequests) => {
        const dispatches = this.queue.reconcileRepository(repository, pullRequests);
        for (const dispatch of dispatches) this.onDispatch(dispatch);
        return dispatches;
      })
      .finally(() => this.inFlight.delete(repository));
    this.inFlight.set(repository, operation);
    return operation;
  }

  async reconcileAll() {
    const results = await Promise.allSettled(
      [...this.repositories].map((repository) => this.reconcileRepository(repository)),
    );
    results.forEach((result, index) => {
      if (result.status === "rejected") {
        this.onError(result.reason, [...this.repositories][index]);
      }
    });
    return results;
  }

  request(repository) {
    if (!this.repositories.has(repository)) return;
    clearTimeout(this.requestTimers.get(repository));
    const timer = setTimeout(() => {
      this.requestTimers.delete(repository);
      this.reconcileRepository(repository).catch((error) => this.onError(error, repository));
    }, this.webhookDebounceMs);
    timer.unref?.();
    this.requestTimers.set(repository, timer);
  }

  start() {
    if (this.timer) return;
    this.timer = setInterval(() => void this.reconcileAll(), this.intervalMs);
    this.timer.unref?.();
  }

  stop() {
    clearInterval(this.timer);
    this.timer = null;
    for (const timer of this.requestTimers.values()) clearTimeout(timer);
    this.requestTimers.clear();
  }
}
