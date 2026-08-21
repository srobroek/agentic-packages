# Report & Journal Schema

## `journal.jsonl` -- one CaseResult per line, appended as cases complete

```json
{"agent":"reviewer-low","case":"case-clean","verdict":"PASS",
 "model":"haiku","effort":"low","model_source":"pinned",
 "duration_s":18.4,"cost_usd":0.011,
 "attempts":[{"n":1,"passed":true,"failed_assertions":[],
              "reply_path":null,"exit_code":0,"duration_s":18.4}]}
```

- `verdict`: `PASS|FLAKY|FAIL|ERROR|SKIP` (FR-006).
- `failed_assertions[].kind`: `first_line|max_words|no_reprint|
  required_pattern|forbidden_pattern|artifact|timeout|budget`.
- `reply_path` non-null for every non-PASS attempt (FR-007): relative to the
  out-dir, `replies/<agent>/<case>-attempt<n>.txt`.
- SKIP lines carry `{"agent":…,"case":null,"verdict":"SKIP","reason":…}`.

## `report.json`

```json
{"run_id":"20260724T120000Z","scope":{"mode":"all","filters":[]},
 "model_overrides":null,
 "totals":{"pass":30,"flaky":1,"fail":1,"error":0,"skip":2},
 "cases":[ /* CaseResult objects, exactly one entry per agent-case */ ],
 "skips":[{"agent":"workflow-coder","reason":"…"}],
 "exit_code":1,
 "meta":{"harness_version":"0.1.0","claude_version":null,
         "concurrency":4,"retries":2,"strict_flaky":false}}
```

Invariants:
- Every discovered agent appears ≥1 time across `cases`+`skips`, and any
  agent with zero entries fails the run with ERROR (defense-in-depth on top
  of `check`).
- `meta.claude_version` is null for in-session sweeps (no CLI envelope);
  the headless fallback populates it. `meta.concurrency` is the sweep
  driver's batch width (skill-specified, default 4).
- `model_overrides` non-null whenever a model override was used; consumers MUST
  treat overridden verdicts as non-shipped-config evidence (FR-008).

## `report.md`

Human summary: totals line, then one table row per agent-case --
`| agent | case | verdict | model(source) | words | duration | cost |` --
followed by a failures section quoting `failed_assertions` details and
`reply_path` links, and the skip table with reasons. No raw replies inline.
