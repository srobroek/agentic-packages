# Bash Safety

LEGEND: Rules carry stable IDs (BS-n) cited by the enforcing hooks.

bash-safety-guard.py enforces BS-1..BS-10. It tokenizes the command with a real
shell lexer, so a guarded verb is found wherever it sits (behind a wrapper or an
env assignment, inside a subshell or loop body, on a later line) while the same
text inside a quoted argument stays an argument.

MUST BS-1: treat operations that cannot be recovered as hard blocks -- emit deny only for truly unrecoverable destruction, warn for recoverable ones.
NOT BS-2: emit `ask` (the human-confirmation decision) -- it stalls autonomous runs.

ID index (the guard's own deny/warn message carries the rationale, with the offending target interpolated, at fire time):
BS-3 sandbox-bypass flag · BS-4 rm -rf on filesystem/home root · BS-5 mkfs · BS-6 dd to a block device ·
BS-7 curl/wget-to-shell pipe, and sudo+destructive (both warn) · BS-8 rm -rf on a system-critical tree ·
BS-9 rm -rf with an unexpanded variable target · BS-10 rm -rf outside the git working tree (warn).
