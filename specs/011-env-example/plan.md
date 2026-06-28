# Implementation Plan: env-example-from-stack

**Branch**: `feat/project-setup-modular-redesign` (continues) | **Date**: 2026-06-28
| **Spec**: [spec.md](./spec.md)

**Input**: `specs/011-env-example/spec.md` + synthesis sequencing (011 ships third —
new standalone module, only depends on 003/004 which are green).

## Summary

New opt-in module `env-example`: an agent maps the resolved stack (framework_python /
framework_ts / extra_env_hints) to a structured `env_keys` list; a soft init_only gate
previews it; a python step writes `.env.example` with **placeholder tokens only**, to a
**hard-coded path**, **hard-refusing** any placeholder that `sdk.looks_like_secret`
flags (G8 defense-in-depth). Zero runner change — reuses the resolve→gate→write seam
(003/004) and the existing `looks_like_secret` + `idempotent_write` primitives.

## OQ resolutions (per spec memory leans — all design-detail)

- **OQ-1 (how framework_python/_ts populate)** → declared as `[[inputs]]` on the
  module (default ""); the agent reads them from its context dict (the same way
  lang-python's resolve reads its inputs). Cross-module value flow is the enablement
  layer's answer dict at build_plan — no new runner API (Settled Decision B).
- **OQ-2 (env_keys shape)** → structured objects `{name, placeholder, comment,
  secret_bool}` (Settled Decision C), not a flat string list — needed for the
  comment-wording + the secret_bool hard-refuse rule.
- **OQ-3 (comment format)** → inline `KEY=placeholder  # comment` suffix (FR-011).

## Technical Context

Python ≥3.11 / uv, stdlib only. No network (agent works from framework knowledge; no
pins, no `verify_pins`). No new deps, no MCP (FR-016). Output is byte-identical for the
same frozen `env_keys` (sorted + fixed preamble — Tier-1, FR-014). Reproduce replays
the frozen `env_keys` zero-network (FR-013). The fixed `.env.example` path + the
`looks_like_secret` hard-refuse are the safety invariants (FR-008/009/012, G8).

## Constitution Check

No ratified constitution. Gates on: spec Settled Decisions A–H, the 003 agent-decides/
python-writes seam, the 004 soft-gate + init_only calibration, and the G8 secret guard.
No runner-contract change — module-only + reuse of shipped SDK helpers.

## Phase 1 — module skeleton + agent + gate

1. `modules/env-example/module.toml`: `[module]` id=env-example, default_enabled=false,
   reconcile=true; `[order] after=["lang-python","lang-ts"]` (soft, no requires);
   `[[inputs]]` framework_python / framework_ts / extra_env_hints (all string,
   not-required, default ""). `[[steps]]`: resolve(agent,
   steering="steering/resolve.md") → preview(gate, hardness="soft", init_only=true,
   message with `{decision}`) → write(python).
2. `modules/env-example/steering/resolve.md` (FR-003/004/005/006): instruct the agent
   to derive canonical env-var NAMES per framework (Django: SECRET_KEY/DEBUG/
   ALLOWED_HOSTS; FastAPI: DATABASE_URL/SECRET_KEY/DEBUG; Nuxt: NUXT_PUBLIC_*/
   NUXT_SECRET; Vite: VITE_*; Next: NEXT_PUBLIC_*/NEXTAUTH_*), add normalized
   extra_env_hints names, dedup by name, emit `env_keys` as agent-steered objects
   {name, placeholder, comment, secret_bool} with NON-EMPTY placeholder tokens, NEVER
   a real value/range/path, NO network/MCP.

## Phase 2 — python write step (deterministic + hard-refuse)

`modules/env-example/module.py` (STEP_HANDLERS = {"write": _do_write}; resolve+gate are
runner-dispatched). `_do_write`:
1. read `env_keys` (get_list, default []).
2. validate each entry: `name` matches `^[A-Z][A-Z0-9_]*$` (else skip + warn, FR-010);
   `looks_like_secret(placeholder)` non-None → HARD ERROR, write nothing
   (status=error, INPUT_VALUE_INVALID, name the offending key, FR-008); `secret_bool`
   true + empty placeholder → same hard error (FR-009).
3. sanitize newline-in-placeholder → space + warn (Edge Case).
4. sort by name (FR-011); render the fixed 2-line preamble + `KEY=placeholder` (+ `  #
   comment` if present) per entry.
5. `sdk.idempotent_write(".env.example", body, reconcile=inputs.reconcile,
   inspect=args.inspect)` — path HARD-CODED (FR-012). Emit ModuleResult.

## Phase 3 — tests + verification

`tests/test_module_env_example.py` (subprocess `--step write` with a frozen plan
carrying canned `env_keys`, mirroring test_module_agents_md.py):
- SC-001 FastAPI keys present, no placeholder trips looks_like_secret.
- SC-002 injected `ghp_…` placeholder → status=error, nothing written.
- SC-003 sorted + preamble + byte-identical on two runs.
- SC-004 empty env_keys → preamble-only file, no error.
- SC-007 bad name skipped+warned, valid entries still written.
- SC-008 secret_bool=true + empty placeholder → error.
- manifest parses (step list resolve/preview/write, gate soft+init_only).
Then full suite green (638 baseline → +new). Runner-level SCs (005/006 gate/reproduce)
are covered by the shared two-phase machinery (same note as 006 AS-BUILT) — the
module's own logic (the hard-refuse + determinism) is the directly-testable surface.

## Project Structure

```text
modules/env-example/
├── module.toml          # resolve(agent)→preview(gate soft init_only)→write(python)
├── module.py            # STEP_HANDLERS={"write": _do_write}; hard-refuse + sorted write
└── steering/resolve.md  # agent derives env_keys from framework knowledge
tests/test_module_env_example.py
```

**Structure Decision**: new module (Settled Decision A) — cross-stack concern, wrong
to couple into lang-python/ts. Zero runner change; reuses looks_like_secret +
idempotent_write + the soft/init_only gate.

## Complexity Tracking

| Decision | Why | Rejected alternative |
|---|---|---|
| New module, not steps on lang-* | env-example is cross-stack (reads both py+ts framework); coupling picks a side | Steps on lang-python would exclude ts projects; on both = duplication |
| Hard-coded `.env.example` path | structurally impossible for the agent to redirect to a real `.env` | A path input is the exact secret-leak vector the invariant forbids |
| Re-validate looks_like_secret at write (not just persist-time G8) | defense-in-depth vs a misbehaving agent step that froze a secret-shaped placeholder | Trusting persist-time G8 alone leaves the write path unguarded |
