---
name: token-savings
description: Measure whether a change actually cut token cost, from transcript usage records. Use when adopting a token-saving tool, tuning one, or running an A/B.
---

# Token savings measurement

Every token-saving tool reports its own savings, and that number is not
evidence. `rtk gain` compares rtk's captured output against rtk's filtered
output for the same run, estimating tokens as `bytes / 4` with no tokenizer. It
cannot see the follow-up command the agent issued because detail was filtered
away. Its own documentation says a command showing 90% fewer output bytes does
not make a session 90% cheaper.

`scripts/tokenmeter.py` reads the `usage` block the API returned on every
assistant turn, from the transcript JSONL. That is billed cost.

## Measuring one run

```bash
python3 scripts/tokenmeter.py measure ~/.claude/projects/<project>/<session>.jsonl
```

Reports `input_tokens`, `cache_creation_input_tokens`,
`cache_read_input_tokens`, `output_tokens`, `turns`, `tool_calls`,
`tool_result_chars`, per-tool call counts, and `cost_weighted`.

MUST Judge a compression tool on `cost_weighted`, not `input_tokens`. Cache
  reads bill at a fraction of fresh input but are not free, and they dominate:
  one measured session showed 279 input tokens against 14.2M cache reads. A
  tool judged on `input_tokens` alone looks miraculous while changing nothing.

MUST Include subagents. `measure` finds the per-agent `.output` transcripts
  automatically; `--no-subagents` exists for diagnosis only. Orchestration moves
  cost into subagents, so a main-thread-only measurement makes any delegating
  change look like a large saving. One measured session attributed 45 subagents
  and 92 extra turns that were invisible without them.

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
  subagent fan-out, and an orchestrated run. A filter that helps a shell-heavy
  single agent can be neutral for a fan-out that spends its budget on
  delegation.

MUST Disable the treatment by its own switch rather than uninstalling, so the
  arms differ in one variable. `RTK_DISABLED=1` leaves hook rewriting untouched
  (verified on 0.43.0; it affects only the rtk process). Remove the hook or set
  an empty allowlist instead.

NOT Compare across different repositories, models, or days without saying so.
NOT Report a percentage without the run count and the separation verdict.

## Structure map

`scripts/../../../scripts/repomix-map.py` maintains a directory-tree map from
`repomix --no-files`, refreshed when HEAD moves and injected at session start
within a token budget.

Measured on a 741-file repository: the map is 6,093 tokens against 1,022,188
for a full `repomix` pack, a 168x reduction. `--compress` (Tree-sitter signature
extraction) removed only 8% on source files and 1.4% repository-wide, because
the bulk is test fixtures and cached artifacts rather than function bodies.

DEFAULT `TOKEN_SAVINGS_MAP_BUDGET` (8000) caps inlining. Above it the hook names
  the file instead, because a large repository maps to ~31k tokens and paying
  that every session costs more than the exploration it saves. Search the named
  file with `rg` rather than reading it.

MUST Use the map to LOCATE files. It carries no file contents; read or search
  the file itself once the map says where it is.
