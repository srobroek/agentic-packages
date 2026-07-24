# Data Model — Agent Conformance Harness

## AgentContract (derived, in-memory)

Extracted from `packages/*/.apm/agents/<name>.agent.md` at run/check time.
Never persisted; the agent file is the source of truth.

| Field | Type | Source |
|---|---|---|
| `name` | str | frontmatter `name:` |
| `package` | str | path segment `packages/<pkg>/` |
| `model` | str \| null | frontmatter `model:` (alias like `haiku`) |
| `effort` | str \| null | frontmatter `effort:` |
| `tools` | list[str] \| null | frontmatter `tools:` |
| `body` | str | markdown body (system prompt content) |
| `first_line_pattern` | str \| null | derived from `## Output` L1/verdict/structured line |
| `caps` | {clean: int\|null, findings: int\|null, uncapped: bool} | derived from `CAP` line |
| `no_reprint` | bool | derived from "Never reprint" rule presence |

Derivation rules (mirrors write-agentic lint idioms):
- CAPS enum regex `\b[A-Z][A-Z-]{2,}(\|[A-Z][A-Z-]{2,})+\b` locates verdict enums.
- `CAP <N>w clean · <M>w with findings` → dual caps; `CAP <N>w`/`CAP <N> words` →
  single; `CAP uncapped` → uncapped=true; `≤ <N> words` prose forms → single cap.
- Agents whose Output section defies derivation (structured lines, prose caps)
  still parse to partial contracts; the case YAML supplies the rest, and
  `check` only cross-validates fields it could derive (null = not checked).

## ConformanceCase (authored, YAML)

`packages/agent-conformance/fixtures/<agent-name>/case-<slug>.yaml`

| Field | Type | Req | Notes |
|---|---|---|---|
| `agent` | str | ✔ | must match a discovered agent name |
| `regime` | `clean` \| `findings` | ✔ | which cap regime the fixture drives |
| `prompt` | str | ✔ | the task message sent to the agent |
| `sandbox.files` | map[path→content] | – | staged into fresh temp dir before run |
| `sandbox.git` | bool | – | `git init` + commit staged files (default false) |
| `assert.first_line` | str (regex) | – | anchored at first non-empty reply line; omit for prose contracts (check warns when both case and derived contract lack it) |
| `assert.max_words` | int \| `uncapped` | ✔ | for the declared regime |
| `assert.no_reprint` | bool | – | default true |
| `assert.required_patterns` | list[regex] | – | section/structure presence |
| `assert.forbidden_patterns` | list[regex] | – | e.g. findings section absent in clean regime |
| `assert.artifacts` | list[{path, line_pattern}] | – | side-effect files (FR-005) |
| `timeout_s` | int | – | default 120; in-session: driver instruction + assert checks capture duration |
| `max_reply_bytes` | int | – | default 65536; assert checks reply file size post-capture, ERROR on breach (FR-012) |
| `budget_usd` | float | – | default 1.00 |

Validation (in `check` mode, LLM-free):
- `agent` resolves; regex fields compile; `regime` matches a derivable cap
  (findings-regime case against a single-cap contract fails validation).
- `assert.first_line` and `assert.max_words` cross-checked against derived
  `first_line_pattern`/`caps` where non-null (FR-011).

## SkipEntry (authored, YAML)

`fixtures/skips.yaml`: list of `{agent: str, reason: str}`. Validated: agent
exists, no agent both skipped and cased, reason non-empty.

## CaseResult (persisted, JSONL journal)

One line per completed case attempt-set, appended as completed (partial-run
safety).

| Field | Type | Notes |
|---|---|---|
| `agent`, `case` | str | identity |
| `context_fingerprint` | str | hash of installed agent file + harness version + date (env-drift diagnosis) |
| `verdict` | PASS\|FLAKY\|FAIL\|ERROR\|SKIP | FR-006 |
| `attempts` | list[Attempt] | see below |
| `model`, `effort` | str | as invoked |
| `model_source` | `pinned`\|`inherited-session`\|`override` | R6 |
| `duration_s` | float | wall-clock per case |
| `cost_usd` | float \| null | null for in-session sweeps (no cost envelope); populated by the headless fallback only (orc-qrt) |

`Attempt`: `{n, passed, failed_assertions: [{kind, detail}], reply_path,
exit_code, duration_s}`. Raw reply persisted at `reply_path` for every
non-PASS attempt (FR-007).

## RunReport (persisted, JSON + MD)

Assembled from the journal at end of run (or from a partial journal on
demand): `{run_id, started_at, scope, totals: {pass, flaky, fail, error,
skip}, cases: [CaseResult], skips: [SkipEntry], exit_code}`. The MD twin is a
human summary table; every agent appears exactly once per FR-007.

## State transitions

```
case discovered → RUNNING → attempt 1 → pass → PASS
                          ↘ fail → retry (≤2) → pass → FLAKY
                                              ↘ all fail → FAIL
                 infra/auth/timeout-at-transport failure → ERROR
   skip entry → SKIP (no execution)
```
