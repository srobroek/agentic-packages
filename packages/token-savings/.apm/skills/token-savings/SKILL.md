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

MUST Judge compression on `cost_weighted`, not `input_tokens`. One session showed
  279 input tokens against 14.2M cache reads, so a tool judged on `input_tokens`
  looks miraculous while changing nothing.

MUST Include subagents (`--no-subagents` is diagnosis only). One session hid 45
  subagents and 92 turns from a main-thread-only reading.

## Running an A/B

```bash
python3 scripts/tokenmeter.py compare --markdown \
  --baseline runs/off/ --treatment runs/on/
```

Both arms accept transcript paths, directories, or saved `measure` records, so
an arm can be assembled across days.

MUST Run at least 3 per arm. Below that `compare` refuses a confident percentage,
  because agent runs are nondeterministic and a two-run A/B measures noise.

MUST Read `ranges_separated` before believing a delta. Overlapping per-run ranges
  mean the arms are not distinguished, whatever the medians say.

MUST Check `turns` and `tool_calls` even when tokens fell. An output filter's
  characteristic failure is hiding something the agent needed, which it buys back
  as extra round trips.

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

## Repository pack

A pack is a search target, never a read: 6,349,248 tokens on a 4,107-file
repository, roughly six context windows. Searching it beats the live tree (0.023s
against 0.126s to list a directory's paths) and is faithful.

MUST Search the pack, never read it. A `PreToolUse` guard denies `Read`, `cat`,
  `bat`, `less`, and an oversized `head`/`tail` on one, and names the search:

    rg '<pattern>' repomix-full.xml
    rg -o 'path="[^"]*<name>[^"]*"' repomix-full.xml    # locate a file
    awk '/<file path="<path>">/,/<\/file>/' repomix-full.xml   # one file

MUST Read the actual source file once the pack says where it is; a pack goes
  stale on the first edit.
DEFAULT `TOKEN_SAVINGS_ALLOW_PACK_READ=1` steps the guard aside when the whole
  pack genuinely is what you want.
MUST Generate it with `repomix`, which reads the committed
  `repomix.config.json`. Filter by PATH there before any content flag: an
  allowlist plus a blocklist removed 29% to 89%, losslessly, where `--compress`
  manages 21% and regresses on comment-dense files. Re-derive with
  `scripts/repomix-tune.py --repo <path>`. See
  [repomix ignores](references/repomix-ignores.md).
NOT Leave a pack unignored. Two 40 MB packs were committed during this work, and
  an unignored artifact feeds the next pack: `graphify-out/` measured 38% of one.
  See [standard paths](references/standard-paths.md).

## Code lookup routing

MUST Route by question shape, not habit. Serena knows `pub` from private and is
  live; graphify answers "what calls this" cheaply with typed edges but models no
  visibility and truncates a file's members at 20. See
  [code lookup routing](references/code-lookup-routing.md).

## Judging a filter's reach

MUST Measure coverage in BYTES, not commands routed. Command counts flatter a
  filter: the rtk guard routes 7.5% of `Bash` output bytes, and most of the rest
  comes from tools rtk cannot filter at all.
NOT Steer agents toward "more filterable" command shapes. The ceiling stays low
  and the constraint distorts real work.

MUST Use the map to LOCATE files, then read the file itself.
