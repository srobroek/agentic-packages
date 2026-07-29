#!/usr/bin/env python3
"""Measure token cost from agent transcripts, and compare two sets of runs.

Every token-saving tool ships a savings number it computed about itself. Those
numbers are marketing, not measurement: the tool counts the bytes it removed
from one command's output and reports the difference, which says nothing about
the tokens the session actually billed. A filter that halves one `git status`
and then costs the agent an extra turn to re-run the command unfiltered has
negative value and a great-looking self-report.

This reads the only ground truth available on this machine: the `usage` block
the API returns on every assistant turn, as recorded in the transcript JSONL.
It attributes subagent cost too, by reading the per-agent `.output` transcripts
a run leaves behind.

Two subcommands:

  measure   one run (a transcript) -> a JSON record of its token cost
  compare   a baseline set vs a treatment set -> per-metric deltas

`compare` reports a range and a per-run table rather than a single percentage.
Agent runs are not deterministic: the same task run twice differs in turn count
and tool calls, so a two-run A/B measures noise as much as it measures the
change. With fewer than MIN_RUNS runs per arm it says so in `warnings` instead
of implying the delta is real.

BILLING NOTE. `input_tokens` excludes cached reads, which are billed at a
fraction of the input rate but are NOT free. A context-compression tool can
shrink `cache_read_input_tokens` a lot while barely moving `input_tokens`, so
this reports both separately plus a blended `cost_weighted` figure. Judge a
compression tool on `cost_weighted`; judge an output filter on `input_tokens`.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

# Below this many runs per arm, a delta is not distinguishable from run-to-run
# variance and the report says so rather than printing a confident percentage.
MIN_RUNS = 3

# Cache reads bill at a discount to fresh input rather than free, and cache
# writes at a premium. Anthropic's published multipliers for the 5-minute TTL:
# a cache write costs 1.25x the base input rate, a cache read 0.1x. Used only
# for the blended `cost_weighted` metric, in input-token-equivalents.
CACHE_READ_WEIGHT = 0.1
CACHE_WRITE_WEIGHT = 1.25

# Output tokens bill far above input (commonly 5x for a given model). A tool
# that trims input while provoking extra reasoning is not a saving, so output
# is weighted rather than pooled with input.
OUTPUT_WEIGHT = 5.0

METRICS = (
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens",
    "cost_weighted",
    "turns",
    "tool_calls",
    "tool_result_chars",
)


def _iter_jsonl(path: Path):
    """Yield parsed objects, skipping malformed lines.

    A live transcript can end mid-write, so a trailing partial line is normal
    and must not abort a measurement.
    """
    try:
        handle = path.open(encoding="utf-8", errors="replace")
    except OSError:
        return
    with handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict):
                yield obj


def _usage_of(obj: dict) -> dict | None:
    message = obj.get("message")
    if not isinstance(message, dict):
        return None
    usage = message.get("usage")
    return usage if isinstance(usage, dict) else None


def _int(usage: dict, key: str) -> int:
    value = usage.get(key)
    return value if isinstance(value, int) else 0


def _content_blocks(obj: dict):
    message = obj.get("message")
    if not isinstance(message, dict):
        return
    content = message.get("content")
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                yield block


def _subagent_transcripts(transcript: Path) -> list[Path]:
    """Locate the per-subagent `.output` transcripts belonging to this run.

    Claude Code writes them to a task directory named after the session id, in
    a temp tree rather than next to the transcript. The temp root is keyed by
    numeric UID (`claude-503`), not by username, so glob for it instead of
    reconstructing the name -- an earlier version built `claude-<login>` and
    silently found zero subagents on every run, which reads as "no delegation"
    rather than as a broken lookup.

    Absent that directory (Codex, or a run with no subagents) the caller
    measures the main thread alone, which is correct rather than an error.
    """
    session_id = transcript.stem
    project_dir = transcript.parent.name

    candidates = [transcript.parent / session_id / "tasks"]
    for root in (Path("/private/tmp"), Path("/tmp")):
        candidates.extend(sorted(root.glob(f"claude-*/{project_dir}/{session_id}/tasks")))

    for tasks_dir in candidates:
        if tasks_dir.is_dir():
            return sorted(tasks_dir.glob("*.output"))
    return []


def measure(transcript: Path, include_subagents: bool = True) -> dict:
    """Total the token cost of one run.

    Counts the main thread and, unless suppressed, every subagent transcript.
    Orchestration moves cost into subagents, so a main-thread-only measurement
    makes any delegating change look like a huge saving.
    """
    record = {
        "transcript": str(transcript),
        "input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "output_tokens": 0,
        "turns": 0,
        "tool_calls": 0,
        "tool_result_chars": 0,
        "tool_calls_by_name": {},
        "subagent_count": 0,
        "subagent_turns": 0,
    }

    def absorb(path: Path, is_subagent: bool) -> None:
        for obj in _iter_jsonl(path):
            usage = _usage_of(obj)
            if usage is not None:
                record["input_tokens"] += _int(usage, "input_tokens")
                record["cache_creation_input_tokens"] += _int(usage, "cache_creation_input_tokens")
                record["cache_read_input_tokens"] += _int(usage, "cache_read_input_tokens")
                record["output_tokens"] += _int(usage, "output_tokens")
                record["turns"] += 1
                if is_subagent:
                    record["subagent_turns"] += 1
            for block in _content_blocks(obj):
                kind = block.get("type")
                if kind == "tool_use":
                    record["tool_calls"] += 1
                    name = block.get("name")
                    if isinstance(name, str):
                        by_name = record["tool_calls_by_name"]
                        by_name[name] = by_name.get(name, 0) + 1
                elif kind == "tool_result":
                    content = block.get("content")
                    if content is not None:
                        # Char count is a size proxy for what a filter actually
                        # removed. It is NOT a token count and is reported
                        # alongside billed tokens, never instead of them.
                        record["tool_result_chars"] += len(
                            content if isinstance(content, str) else json.dumps(content)
                        )

    absorb(transcript, is_subagent=False)
    if include_subagents:
        subagents = _subagent_transcripts(transcript)
        record["subagent_count"] = len(subagents)
        for sub in subagents:
            absorb(sub, is_subagent=True)

    record["cost_weighted"] = round(
        record["input_tokens"]
        + CACHE_WRITE_WEIGHT * record["cache_creation_input_tokens"]
        + CACHE_READ_WEIGHT * record["cache_read_input_tokens"]
        + OUTPUT_WEIGHT * record["output_tokens"],
        1,
    )
    return record


def _summarize(records: list[dict]) -> dict:
    """Median and spread per metric. Median, not mean: one runaway retry loop
    in an arm would drag a mean far enough to invert the verdict."""
    summary = {}
    for metric in METRICS:
        values = [r[metric] for r in records if metric in r]
        if not values:
            continue
        summary[metric] = {
            "median": round(statistics.median(values), 1),
            "min": round(min(values), 1),
            "max": round(max(values), 1),
            "n": len(values),
        }
    return summary


def compare(baseline: list[dict], treatment: list[dict]) -> dict:
    """Per-metric deltas between two arms, with an explicit noise verdict."""
    base_summary = _summarize(baseline)
    treat_summary = _summarize(treatment)

    deltas = {}
    for metric in METRICS:
        if metric not in base_summary or metric not in treat_summary:
            continue
        base_median = base_summary[metric]["median"]
        treat_median = treat_summary[metric]["median"]
        change = treat_median - base_median
        pct = (change / base_median * 100.0) if base_median else None
        # Overlapping [min,max] ranges mean the arms are not separated by this
        # metric, whatever the medians say.
        separated = (
            treat_summary[metric]["max"] < base_summary[metric]["min"]
            or treat_summary[metric]["min"] > base_summary[metric]["max"]
        )
        deltas[metric] = {
            "baseline_median": base_median,
            "treatment_median": treat_median,
            "change": round(change, 1),
            "pct_change": round(pct, 1) if pct is not None else None,
            "ranges_separated": separated,
        }

    warnings = []
    if len(baseline) < MIN_RUNS or len(treatment) < MIN_RUNS:
        warnings.append(
            f"underpowered: {len(baseline)} baseline / {len(treatment)} treatment runs, "
            f"need >={MIN_RUNS} per arm. Treat every delta below as indicative only."
        )
    for metric, delta in deltas.items():
        if delta["pct_change"] is not None and abs(delta["pct_change"]) >= 5 and not delta["ranges_separated"]:
            warnings.append(
                f"{metric}: medians differ by {delta['pct_change']}% but the run ranges "
                f"overlap, so this is not distinguishable from run-to-run variance."
            )
    if any(d["pct_change"] is not None and d["pct_change"] > 2 for m, d in deltas.items() if m == "turns"):
        warnings.append(
            "turns rose in the treatment arm: a filter that hides something the agent "
            "needs buys back its savings in extra round trips. Check tool_calls too."
        )

    return {
        "baseline": {"runs": len(baseline), "summary": base_summary},
        "treatment": {"runs": len(treatment), "summary": treat_summary},
        "deltas": deltas,
        "warnings": warnings,
        "verdict": _verdict(deltas, warnings),
    }


def _verdict(deltas: dict, warnings: list[str]) -> str:
    cost = deltas.get("cost_weighted")
    if not cost or cost["pct_change"] is None:
        return "inconclusive: no cost_weighted data"
    pct = cost["pct_change"]
    underpowered = any(w.startswith("underpowered") for w in warnings)
    if underpowered:
        return f"indicative only: cost_weighted {pct:+.1f}% (underpowered, add runs before deciding)"
    if not cost["ranges_separated"]:
        return f"no measurable effect: cost_weighted {pct:+.1f}% with overlapping ranges"
    if pct < 0:
        return f"saving confirmed: cost_weighted {pct:+.1f}% with separated ranges"
    return f"regression: cost_weighted {pct:+.1f}% with separated ranges"


def _load_records(paths: list[str], include_subagents: bool) -> list[dict]:
    records = []
    for raw in paths:
        path = Path(raw).expanduser()
        if path.is_dir():
            targets = sorted(path.glob("*.jsonl"))
        else:
            targets = [path]
        for target in targets:
            if target.suffix == ".json":
                # A previously saved measure record, so an arm can be assembled
                # over time instead of requiring all runs in one invocation.
                try:
                    loaded = json.loads(target.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                records.extend(loaded if isinstance(loaded, list) else [loaded])
            else:
                records.append(measure(target, include_subagents))
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    m = sub.add_parser("measure", help="measure one or more transcripts")
    m.add_argument("transcripts", nargs="+")
    m.add_argument("--no-subagents", action="store_true", help="main thread only (usually wrong)")

    c = sub.add_parser("compare", help="compare a baseline arm against a treatment arm")
    c.add_argument("--baseline", nargs="+", required=True, metavar="PATH")
    c.add_argument("--treatment", nargs="+", required=True, metavar="PATH")
    c.add_argument("--no-subagents", action="store_true")
    c.add_argument("--markdown", action="store_true", help="human-readable table instead of JSON")

    args = parser.parse_args(argv)

    if args.command == "measure":
        records = [
            measure(Path(t).expanduser(), include_subagents=not args.no_subagents) for t in args.transcripts
        ]
        print(json.dumps(records if len(records) > 1 else records[0], indent=2))
        return 0

    baseline = _load_records(args.baseline, not args.no_subagents)
    treatment = _load_records(args.treatment, not args.no_subagents)
    if not baseline or not treatment:
        print("both arms need at least one transcript", file=sys.stderr)
        return 1
    result = compare(baseline, treatment)
    print(_render_markdown(result) if args.markdown else json.dumps(result, indent=2))
    return 0


def _render_markdown(result: dict) -> str:
    lines = [
        f"# Token A/B: {result['baseline']['runs']} baseline vs {result['treatment']['runs']} treatment runs",
        "",
        f"**{result['verdict']}**",
        "",
        "| Metric | Baseline | Treatment | Change | Separated |",
        "| --- | --- | --- | --- | --- |",
    ]
    for metric, delta in result["deltas"].items():
        pct = "n/a" if delta["pct_change"] is None else f"{delta['pct_change']:+.1f}%"
        lines.append(
            f"| {metric} | {delta['baseline_median']} | {delta['treatment_median']} "
            f"| {pct} | {'yes' if delta['ranges_separated'] else 'no'} |"
        )
    if result["warnings"]:
        lines += ["", "## Warnings", ""]
        lines += [f"- {w}" for w in result["warnings"]]
    return "\n".join(lines)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
