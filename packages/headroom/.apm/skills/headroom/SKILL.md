---
name: headroom
description: Compress context via Headroom to cut token usage. Use when asked to reduce token cost, wrap claude/codex, run the headroom proxy, or check token savings.
---

# Headroom

Headroom is a local proxy that compresses context (and trims output) before requests reach the
LLM, then reports how many tokens it saved — lower token cost without changing the agent's
answers. It installs via mise (`pipx:headroom-ai`) and exposes the `headroom` CLI on PATH.

## Workflow

1. Confirm it is available: `headroom --version`. If missing, install with
   `mise install pipx:headroom-ai` (PyPI `headroom-ai[all]`, requires Python 3.10+).
2. Run an agent through Headroom — this starts a local proxy, points the agent at it (sets
   `ANTHROPIC_BASE_URL`/`OPENAI_BASE_URL`), and applies the `agent-90` savings profile by
   default (~90% target, Headroom's most aggressive compression / output-token reduction):
   - `headroom wrap claude` (Claude Code) or `headroom wrap codex` (Codex). Unknown args
     pass through to the tool (e.g. `headroom wrap claude --resume <id>`).
   - On this machine `claude`/`codex` are already overridden to launch this way; bypass with
     `HEADROOM_DISABLE=1` or `command claude` / `command codex`.
3. For any other OpenAI/Anthropic-compatible client, run the proxy directly and point the
   client at it: `headroom proxy --port 8787`, then set `ANTHROPIC_BASE_URL` /
   `OPENAI_BASE_URL` yourself.
4. Check savings: `headroom perf` (analyzes proxy logs) or read `~/.headroom/proxy_savings.json`
   — `display_session.tokens_saved` / `.savings_percent` for the live session, `lifetime` for
   cumulative totals. LOAD references/commands.md for the full command + env + endpoint reference.
5. Render or verify the savings target with `headroom agent-savings` (use `--check-perf` to
   assert recent logs meet the profile target).

## Steering

- Output token reduction: the docs document `HEADROOM_OUTPUT_SHAPER=1`, but the released
  code (0.26.0, == PyPI latest) does not read it yet — real token/output reduction comes from
  the `agent-90` profile that `wrap` applies. Set `HEADROOM_OUTPUT_SHAPER=1` anyway for
  forward-compatibility (no-op in 0.26.0; wired in a future release). Never hardcode a
  profile if `$HEADROOM_SAVINGS_PROFILE` is set.
- Compression is reversible (originals retrievable on demand), but if an agent misbehaves under
  compression, isolate it: rerun with `HEADROOM_DISABLE=1` / `command <tool>` to confirm whether
  Headroom is the cause before debugging further.
- Output-token savings are estimated (counterfactual — Headroom never sees what the model would
  have written), so treat output percentages as directional, not exact.
- Prefer `wrap` over a hand-managed proxy for coding agents — it wires env vars and the MCP
  retrieve tool for you; `proxy` is for non-agent or custom clients.
- Keep secrets out of logs: do not enable `--log-messages` on shared machines.
- For Bedrock, do not point `--bedrock-api-url` at a re-signing gateway — rewriting the body
  breaks SigV4.
