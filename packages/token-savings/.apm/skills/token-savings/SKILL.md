---
name: token-savings
description: Measure whether a change actually cut token cost, from transcript usage records. Use when adopting a token-saving tool, tuning one, or running an A/B.
---

# Token savings measurement

A tool's self-reported savings is not evidence. `rtk gain` compares its own
captured output against its own filtered output for the same run, estimating
tokens as `bytes / 4` with no tokenizer, and cannot see a follow-up command
caused by over-filtering.

`scripts/tokenmeter.py` reads the `usage` block the API returned on every
assistant turn, from the transcript JSONL. That is billed cost.

## Measuring one run

```bash
python3 scripts/tokenmeter.py measure ~/.claude/projects/<project>/<session>.jsonl
```

Reports token counts per category, `turns`, `tool_calls`, `tool_result_chars`,
per-tool call counts, and `cost_weighted`.

MUST Judge compression on `cost_weighted`, not `input_tokens`. Cache reads bill
  below fresh input but are not free, and they dominate: one session showed 279
  input tokens against 14.2M cache reads, so a tool judged on `input_tokens`
  looks miraculous while changing nothing.

MUST Include subagents (`--no-subagents` is for diagnosis only). One session
  hid 45 subagents and 92 turns from a main-thread-only reading.

## Running an A/B

```bash
python3 scripts/tokenmeter.py compare --markdown \
  --baseline runs/off/ --treatment runs/on/
```

Both arms accept transcript paths, directories, or saved `measure` records, so
an arm can be assembled across days.

MUST Run at least 3 per arm. Below that `compare` labels the verdict
  "indicative only" and refuses a confident percentage, because agent runs are
  nondeterministic and a two-run A/B measures noise.

MUST Read `ranges_separated` before believing a delta. Overlapping per-run
  ranges mean the arms are not distinguished by that metric whatever the medians
  say; the verdict follows the ranges.

MUST Check the `turns` and `tool_calls` deltas even when tokens fell. The
  characteristic failure of an output filter is hiding something the agent
  needed, which it buys back as extra round trips. `compare` warns when turns
  rise.

## Designing the arms

MUST Hold the task fixed and vary only the tool. Same prompt, same starting
  commit, same model.

MUST Cover the shapes that behave differently: direct single-agent work, a
  subagent fan-out, and an orchestrated run.

MUST Disable the treatment by its own switch rather than uninstalling, so the
  arms differ in one variable. `RTK_DISABLED=1` leaves hook rewriting untouched
  (verified on 0.43.0; it affects only the rtk process). Remove the hook or set
  an empty allowlist instead.

NOT Compare across different repositories, models, or days without saying so.
NOT Report a percentage without the run count and the separation verdict.

## Structure map

`repomix-map.py` maintains a directory-tree map from `repomix --no-files`,
refreshed when HEAD moves and injected at session AND subagent start within a
token budget. Measured on a 4,107-file repository: 31,299 tokens against
10,365,403 for a full pack of the same tree, a 331x reduction.

MUST Exclude generated output before reaching for `--compress`. An ignore set
  removed 21.1% and 33.5% of a full pack on two repositories, against
  `--compress`'s 21%, and losslessly. See
  [repomix ignores](references/repomix-ignores.md).

DEFAULT `TOKEN_SAVINGS_MAP_BUDGET` (8000) caps inlining. Above it the hook names
  the file instead, because a large repository maps to ~31k tokens and paying
  that every session costs more than the exploration it saves. Search the named
  file with `rg` rather than reading it.

## Code lookup routing

Reaching for the wrong navigation tool pays twice: for the answer, and for the
follow-up when it is incomplete. Serena knows `pub` from private and is live;
graphify answers "what calls this" cheaply with typed edges but models no
visibility and truncates a file's members at 20. See
[code lookup routing](references/code-lookup-routing.md) for the measured
comparison and the command surface, which exists so no agent pays the 12,464-byte
`graphify --help` read again.

## Judging a filter's reach

MUST Measure coverage in BYTES, not in commands routed. Command counts flatter a
  filter. On one repository's history the rtk guard routes 3.6% of `Bash` output
  bytes, and 76.7% of those bytes come from tools rtk has no filter for at all
  (`wt`, `bd`, `jq`, `rg`, `head`, `python3`), which caps it at 23.3% even if
  every chain and heredoc were rewritten.
NOT Steer agents toward "more filterable" command shapes to raise that number.
  The ceiling stays under a quarter, and the constraint distorts real work.

MUST Use the map to LOCATE files, then read or search the file itself.
