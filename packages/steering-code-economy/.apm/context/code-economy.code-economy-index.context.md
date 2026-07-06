# Code Economy

Before writing any code, in order:

| # | Check | Passes when |
|---|---|---|
| 0 | Need | existing code, config, or deletion cannot solve it |
| 1 | Stdlib | no standard-library function does this |
| 2 | Library | no popular, maintained, light library fits — reject heavyweights for one function |
| 3 | Hand-roll | smallest implementation that solves the actual problem |

MUST Extend an existing function that covers most of the need instead of adding a near-duplicate.
MUST Logic needed twice: extract into a shared function/module/package/crate — never copy.
NOT Speculative generality (YAGNI); wrappers around wrappers; drive-by refactors.
DEFAULT Smallest diff that solves the problem; prefer deleting code over adding it.
