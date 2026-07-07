# Bash Safety

LEGEND: Rules carry stable IDs (BS-n) cited by the enforcing hooks.

bash-guard.sh enforces BS-1..BS-7. rm-rf-guard.sh enforces BS-8..BS-10.

MUST BS-1: treat operations that cannot be recovered as hard blocks — emit deny only for truly unrecoverable destruction (rm -rf on / or $HOME root, mkfs, dd to a real block device, sandbox-bypass flag).
NOT BS-2: emit `ask` (the human-confirmation decision) — it stalls autonomous runs; use deny for unrecoverable ops and warn for recoverable ones.
NOT BS-3: run with --dangerously-bypass-approvals-and-sandbox — this disables the safety envelope itself.
NOT BS-4: run rm -rf on the filesystem root (/, //, /*) or the home directory root (~, $HOME, ${HOME}).
NOT BS-5: run mkfs or its filesystem-specific variants (mkfs.ext4, mkfs.xfs, ...) — formats a filesystem; destroys all data.
NOT BS-6: run dd writing to a real block device (of=/dev/..., excluding the pseudo-devices /dev/null, /dev/zero, /dev/random, /dev/urandom, /dev/stdout, /dev/stdin).
MUST BS-7: warn (allow + advisory) when curl or wget is piped into a shell — the command proceeds but the agent is informed that unverified remote code will run.
NOT BS-8: run rm -rf on a system-critical directory as a whole tree (/, /usr, /etc, /bin, /var, ...) or the home root.
NOT BS-9: run rm -rf with an unexpanded shell variable as the target ($DIR, ${DIR}) — the guard cannot verify the resolved path; re-run with the variable resolved to a literal first.
MUST BS-10: warn (allow + advisory) when rm -rf targets a path outside the project's git working tree (repo root/.git, ~/subpath, or any path that is not git-recoverable).
