---
name: headroom
description: Run coding agents through Headroom to compress context and cut token usage (~60-95% fewer), and to read token-savings stats. Use when the user asks to reduce token cost/usage, enable or configure headroom, wrap claude/codex with compression, run the headroom proxy, check how many tokens were saved, or troubleshoot a headroom-wrapped session.
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

- There is no separate "output shaper" toggle in this version; the `agent-90` profile that
  `wrap` enables by default IS the token/output reduction. An existing `$HEADROOM_SAVINGS_PROFILE`
  is respected, so never blindly hardcode the profile when the user has set one.
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
