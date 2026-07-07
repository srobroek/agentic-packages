# Git Safety

LEGEND: Rules carry stable IDs (GS-n) cited by the enforcing hooks.

git-guard.sh enforces GS-1..GS-6.

NOT GS-1: emit `ask` (the human-confirmation decision) — it stalls autonomous runs; git safety guards use deny for unverifiable targets and warn for recoverable ops.
NOT GS-2: run a destructive git op (reset --hard, checkout --, restore, clean -f) whose target working tree is specified through an unexpanded shell variable or ~ — the guard cannot verify which tree will be affected; resolve the variable to a literal path first.
MUST GS-3: warn (allow + advisory) when git reset --hard would discard uncommitted tracked changes — staged and unstaged changes to tracked files are gone for good, not in the reflog.
MUST GS-4: warn (allow + advisory) on git push --force, --force-with-lease, or -f — force push rewrites remote history and may overwrite others' commits.
MUST GS-5: warn (allow + advisory) when git checkout -- <path> or git restore (worktree) would discard uncommitted changes to tracked files.
MUST GS-6: warn (allow + advisory) when git clean -f would delete untracked files — they are not recoverable from the reflog.
