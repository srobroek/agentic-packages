# Code Economy

Before writing any code, in order:
0. Need — does this need to exist? Can existing code, config, or deletion solve it?
1. Stdlib — a standard-library function that does this?
2. Library — a popular, maintained, light library? Reject heavyweights for one function.
3. Hand-roll — the smallest implementation that solves the actual problem.

Rules:
- Extend an existing function that covers most of the need instead of adding a near-duplicate.
- Logic needed twice: extract into a shared function/module/package/crate — never copy.
- No speculative generality (YAGNI); no wrappers around wrappers.
- Smallest diff that solves the problem; no drive-by refactors.
- Prefer deleting code over adding it.
