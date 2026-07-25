# Bash Safety

LEGEND: Rules carry stable IDs (BS-n) cited by the enforcing hooks.

bash-guard.sh enforces BS-1..BS-7. rm-rf-guard.sh enforces BS-8..BS-10.

MUST BS-1: treat operations that cannot be recovered as hard blocks — emit deny only for truly unrecoverable destruction, warn for recoverable ones.
NOT BS-2: emit `ask` (the human-confirmation decision) — it stalls autonomous runs.

ID index (the guard's own deny/warn message carries the rationale, with the offending target interpolated, at fire time):
BS-3 sandbox-bypass flag · BS-4 rm -rf on filesystem/home root · BS-5 mkfs · BS-6 dd to a block device ·
BS-7 curl/wget-to-shell pipe, and sudo+destructive (both warn) · BS-8 rm -rf on a system-critical tree ·
BS-9 rm -rf with an unexpanded variable target · BS-10 rm -rf outside the git working tree (warn).
