# Headroom command & configuration reference

Verified against headroom-ai 0.26.0. Run `headroom <command> --help` for the authoritative,
version-specific flags.

## Install

- Managed here by mise: `pipx:headroom-ai` with `extras = "all"` (installs via `uv tool`).
  Install/update: `mise install pipx:headroom-ai` · locate: `mise where pipx:headroom-ai`.
- Direct alternatives: `pip install "headroom-ai[all]"` or `npm install headroom-ai`. Python 3.10+.

## Run an agent through Headroom (`wrap`)

`headroom wrap <tool> [TOOL_ARGS...]` starts a proxy, sets the right base-URL env var, applies
the `agent-90` savings profile by default, and launches the tool. Unknown flags pass through.

| Command | Tool |
|---|---|
| `headroom wrap claude` | Claude Code (sets `ANTHROPIC_BASE_URL`) |
| `headroom wrap codex` | OpenAI Codex CLI (sets `OPENAI_BASE_URL`) |
| `headroom wrap aider` / `goose` / `openhands` / `vibe` / `copilot` | other CLIs |
| `headroom wrap cursor` / `cline` / `continue` | print editor config instructions |

Useful `wrap claude` flags: `-p/--port N` (proxy port, default 8787), `--memory` (persistent
cross-session memory), `--learn` (mine error→recovery patterns into MEMORY.md), `--code-graph`
(index cwd), `--no-proxy` (reuse an already-running proxy), `--no-mcp` / `--no-serena` (skip MCP
registration), `-v`. `wrap codex` mirrors these.

Bypass the local shell override: `HEADROOM_DISABLE=1 claude …` or `command claude …`.

## Run the proxy standalone (`proxy`)

`headroom proxy [--port 8787]` — OpenAI/Anthropic-compatible proxy for any client. Then:
`ANTHROPIC_BASE_URL=http://localhost:8787 claude` or `OPENAI_BASE_URL=http://localhost:8787/v1`.

Key flags / env: `--port`/`HEADROOM_PORT`, `--host`/`HEADROOM_HOST` (default 127.0.0.1),
`--mode token|cache` /`HEADROOM_MODE` (token = max compression; cache = freeze prior turns for
provider prefix-cache hits), `--no-optimize` (passthrough), `--no-cache`, `--memory`,
`--budget N --budget-period daily` (reject over budget), `--stateless` (no disk writes),
`--log-file PATH` (JSONL: timestamp, model, tokens_before, tokens_after, latency_ms…).

HTTP endpoints (loopback): `GET /livez` (liveness), `GET /health`, `GET /stats` (full metrics,
includes `proxy_savings_percent`), `GET /stats?cached=1` (fast dashboard snapshot),
`GET /metrics` (Prometheus, e.g. `headroom_tokens_saved_total`), `POST /stats/reset`.

## Savings & performance

- `headroom perf` — analyze recent proxy logs and print compression performance.
- `headroom agent-savings` — render the savings profile env (`--format shell|json`,
  `--profile agent-90`); `--check-perf --hours 24` asserts recent logs meet the target.
- Persisted savings file: `~/.headroom/proxy_savings.json` (override with `HEADROOM_SAVINGS_PATH`,
  or relocate the config dir with `HEADROOM_CONFIG_DIR`). Schema:
  - `lifetime`: `{requests, tokens_saved, compression_savings_usd, total_input_tokens, total_input_cost_usd}`
  - `display_session`: lifetime fields **plus** `savings_percent`, `started_at`, `last_activity_at`
  - `history`: `[]`, `projects`: `{}`
  The status bar reads `display_session.tokens_saved` / `.savings_percent` from this file.

## Savings-profile env (what `agent-90` sets)

`agent-90` exports (see `headroom agent-savings --format shell`): `HEADROOM_MODE=token`,
`HEADROOM_SAVINGS_PROFILE=agent-90`, `HEADROOM_SAVINGS_TARGET=0.90`,
`HEADROOM_COMPRESS_USER_MESSAGES=1`, `HEADROOM_COMPRESS_SYSTEM_MESSAGES=1`,
`HEADROOM_PROTECT_RECENT=2`, `HEADROOM_MIN_TOKENS=120`, `HEADROOM_FORCE_KOMPRESS=1`,
`HEADROOM_ACCURACY_GUARD=strict`, etc. `wrap` applies these by default unless
`HEADROOM_SAVINGS_PROFILE` is already set.

### `HEADROOM_OUTPUT_SHAPER`

The docs show `export HEADROOM_OUTPUT_SHAPER=1` (off by default) to enable output-token
shaping. Caveat: in 0.26.0 (== PyPI latest) the shipped code does not reference this variable
anywhere — verified against the Python package and the native `_core.abi3.so` — so it is a
**no-op today**; actual reduction comes from the `agent-90` compression profile. It is safe to
export for forward-compatibility (and the local fish wrappers do), but do not rely on it as the
sole reduction mechanism on this version.

## Other commands

`headroom init` (durable integrations), `headroom install` (persistent deployments),
`headroom unwrap` (undo durable wrapping), `headroom memory …`, `headroom learn` (learn from
past tool-call failures), `headroom mcp` (MCP server for Claude Code), `headroom tools` (bundled
ast-grep/difft/scc binaries), `headroom update`.

## Troubleshooting

- Proxy exits immediately with `ImportError: Using SOCKS proxy, but 'socksio' is not installed`:
  a `socks://` value in `ALL_PROXY`/`HTTPS_PROXY` is being inherited. Unset it for the headroom
  process, or `pip install "httpx[socks]"` into the headroom env.
- Agent loads every tool schema eagerly (inflated local context) under a custom base URL: keep
  Claude Code's deferral active with `headroom wrap claude --tool-search true` (default).
- Verify a session is wrapped: `ANTHROPIC_BASE_URL` (Claude) / `OPENAI_BASE_URL` (Codex) points
  at `127.0.0.1`/`localhost`.
