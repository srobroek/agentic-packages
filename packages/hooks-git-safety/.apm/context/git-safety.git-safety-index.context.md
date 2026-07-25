# Git Safety

LEGEND: Rules carry stable IDs (GS-n) cited by the enforcing hooks.

git-guard.sh enforces GS-1..GS-6.

NOT GS-1: emit `ask` (the human-confirmation decision) — it stalls autonomous runs; deny for unverifiable targets, warn for recoverable ops.

ID index (the guard's own deny/warn message carries the rationale, with the offending target interpolated, at fire time):
GS-2 destructive op via unexpanded variable/`~` target (deny) · GS-3 reset --hard on a dirty tree ·
GS-4 push --force · GS-5 checkout -- / restore discarding uncommitted changes · GS-6 clean -f (all warn).
