"""Coverage for tokenmeter.py, the A/B measurement instrument.

The negative cases carry the weight here. This script exists to stop a
token-saving tool being adopted on a flattering self-report, so the tests that
matter most are the ones proving it REFUSES to call a delta real: overlapping
run ranges, too few runs, and a turn-count regression all have to surface
rather than be averaged away.

The subagent-discovery test is here because the first implementation built its
temp path from the username while the real directory is keyed by numeric UID.
It found zero subagents on every run and reported that as "no delegation".
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / ".apm"
    / "skills"
    / "token-savings"
    / "scripts"
    / "tokenmeter.py"
)


def _turn(inp=0, cache_write=0, cache_read=0, out=0, content=None):
    message = {"role": "assistant", "usage": {}}
    message["usage"] = {
        "input_tokens": inp,
        "cache_creation_input_tokens": cache_write,
        "cache_read_input_tokens": cache_read,
        "output_tokens": out,
    }
    if content is not None:
        message["content"] = content
    return {"type": "assistant", "message": message}


def _write(path: Path, objs) -> Path:
    path.write_text("".join(json.dumps(o) + "\n" for o in objs), encoding="utf-8")
    return path


def _run(*args) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=True
    )
    return json.loads(proc.stdout)


def _arm(tmp_path: Path, name: str, costs: list[int]) -> list[str]:
    """One transcript per run, each with a single turn of the given output size."""
    paths = []
    for i, cost in enumerate(costs):
        p = _write(tmp_path / f"{name}-{i}.jsonl", [_turn(out=cost)])
        paths.append(str(p))
    return paths


def test_measure_totals_usage_across_turns(tmp_path):
    t = _write(
        tmp_path / "s.jsonl",
        [_turn(inp=10, cache_write=100, cache_read=1000, out=5), _turn(inp=1, out=2)],
    )
    got = _run("measure", str(t))
    assert got["input_tokens"] == 11
    assert got["cache_creation_input_tokens"] == 100
    assert got["cache_read_input_tokens"] == 1000
    assert got["output_tokens"] == 7
    assert got["turns"] == 2


def test_cost_weighted_prices_cache_reads_below_fresh_input(tmp_path):
    """A cache read is discounted, not free. A compression tool that only moves
    cache reads must still show a cost_weighted change, or it looks free."""
    cheap = _write(tmp_path / "cheap.jsonl", [_turn(cache_read=1000)])
    dear = _write(tmp_path / "dear.jsonl", [_turn(inp=1000)])
    cheap_cost = _run("measure", str(cheap))["cost_weighted"]
    dear_cost = _run("measure", str(dear))["cost_weighted"]
    assert 0 < cheap_cost < dear_cost


def test_output_tokens_dominate_cost_weighted(tmp_path):
    """Output bills well above input, so a filter that trims input while
    provoking more reasoning must not read as a saving."""
    t = _write(tmp_path / "s.jsonl", [_turn(inp=100)])
    o = _write(tmp_path / "o.jsonl", [_turn(out=100)])
    assert _run("measure", str(o))["cost_weighted"] > _run("measure", str(t))["cost_weighted"]


def test_malformed_and_partial_lines_are_skipped(tmp_path):
    """A live transcript can end mid-write; that must not abort a measurement."""
    p = tmp_path / "s.jsonl"
    p.write_text(
        json.dumps(_turn(out=5)) + "\n" + "not json\n" + '{"type":"assistant","mess',
        encoding="utf-8",
    )
    assert _run("measure", str(p))["output_tokens"] == 5


def test_tool_calls_and_result_size_are_counted(tmp_path):
    t = _write(
        tmp_path / "s.jsonl",
        [
            _turn(content=[{"type": "tool_use", "name": "Bash"}, {"type": "tool_use", "name": "Read"}]),
            _turn(content=[{"type": "tool_result", "content": "x" * 50}]),
        ],
    )
    got = _run("measure", str(t))
    assert got["tool_calls"] == 2
    assert got["tool_calls_by_name"] == {"Bash": 1, "Read": 1}
    assert got["tool_result_chars"] == 50


def test_subagent_transcripts_are_attributed(tmp_path):
    """Orchestration moves cost into subagents. Missing them makes any
    delegating change look like a huge saving."""
    project = tmp_path / "-proj"
    project.mkdir()
    main = _write(project / "sess.jsonl", [_turn(out=10)])
    tasks = project / "sess" / "tasks"
    tasks.mkdir(parents=True)
    _write(tasks / "a.output", [_turn(out=100)])
    _write(tasks / "b.output", [_turn(out=200)])

    got = _run("measure", str(main))
    assert got["subagent_count"] == 2
    assert got["subagent_turns"] == 2
    assert got["output_tokens"] == 310

    alone = _run("measure", "--no-subagents", str(main))
    assert alone["output_tokens"] == 10
    assert alone["subagent_count"] == 0


def test_underpowered_comparison_refuses_a_confident_verdict(tmp_path):
    """Two runs per arm measures noise. It must say so."""
    base = _arm(tmp_path, "b", [1000, 1010])
    treat = _arm(tmp_path, "t", [500, 510])
    got = _run("compare", "--baseline", *base, "--treatment", *treat)
    assert any(w.startswith("underpowered") for w in got["warnings"])
    assert "indicative only" in got["verdict"]


def test_overlapping_ranges_report_no_measurable_effect(tmp_path):
    """Medians can differ while the arms are indistinguishable. The verdict
    must follow the ranges, not the medians."""
    base = _arm(tmp_path, "b", [100, 500, 900])
    treat = _arm(tmp_path, "t", [90, 450, 880])
    got = _run("compare", "--baseline", *base, "--treatment", *treat)
    assert got["deltas"]["output_tokens"]["ranges_separated"] is False
    assert "no measurable effect" in got["verdict"]


def test_separated_ranges_confirm_a_real_saving(tmp_path):
    base = _arm(tmp_path, "b", [1000, 1005, 1010])
    treat = _arm(tmp_path, "t", [500, 505, 510])
    got = _run("compare", "--baseline", *base, "--treatment", *treat)
    assert got["deltas"]["cost_weighted"]["ranges_separated"] is True
    assert "saving confirmed" in got["verdict"]
    assert got["deltas"]["cost_weighted"]["pct_change"] == pytest.approx(-50.0, abs=1.0)


def test_a_regression_is_named_as_one(tmp_path):
    base = _arm(tmp_path, "b", [500, 505, 510])
    treat = _arm(tmp_path, "t", [1000, 1005, 1010])
    got = _run("compare", "--baseline", *base, "--treatment", *treat)
    assert "regression" in got["verdict"]


def test_extra_turns_are_flagged_even_when_tokens_fall(tmp_path):
    """The core failure mode: a filter hides what the agent needed, so it
    re-runs the command. Tokens can fall while the run gets worse."""
    base = [
        str(_write(tmp_path / f"b{i}.jsonl", [_turn(out=1000)]))
        for i in range(3)
    ]
    treat = [
        str(_write(tmp_path / f"t{i}.jsonl", [_turn(out=200)] * 5))
        for i in range(3)
    ]
    got = _run("compare", "--baseline", *base, "--treatment", *treat)
    assert any("turns rose" in w for w in got["warnings"])


def test_arms_can_be_assembled_from_saved_records(tmp_path):
    """Runs happen over time; an arm must be composable from saved measures."""
    rec = _run("measure", str(_write(tmp_path / "s.jsonl", [_turn(out=100)])))
    saved = tmp_path / "saved.json"
    saved.write_text(json.dumps([rec, rec, rec]), encoding="utf-8")
    base = _arm(tmp_path, "b", [100, 100, 100])
    got = _run("compare", "--baseline", *base, "--treatment", str(saved))
    assert got["treatment"]["runs"] == 3


def test_directory_argument_collects_every_transcript(tmp_path):
    arm = tmp_path / "arm"
    arm.mkdir()
    for i in range(3):
        _write(arm / f"r{i}.jsonl", [_turn(out=100)])
    base = _arm(tmp_path, "b", [100, 100, 100])
    got = _run("compare", "--baseline", *base, "--treatment", str(arm))
    assert got["treatment"]["runs"] == 3


def test_markdown_output_renders_a_table(tmp_path):
    base = _arm(tmp_path, "b", [1000, 1005, 1010])
    treat = _arm(tmp_path, "t", [500, 505, 510])
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "compare", "--markdown", "--baseline", *base, "--treatment", *treat],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "| Metric | Baseline | Treatment |" in proc.stdout
    assert "cost_weighted" in proc.stdout


def test_empty_arm_exits_nonzero(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    base = _arm(tmp_path, "b", [100])
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "compare", "--baseline", *base, "--treatment", str(empty)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
