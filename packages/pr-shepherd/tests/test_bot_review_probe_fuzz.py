#!/usr/bin/env python3
"""Seeded fuzz harness for bot-review-probe.py.

The probe is merge readiness: only `absent` and `clean` (exit 0) clear a merge,
so the property that matters is fail-closed classification. Four properties:

  P1  `classify` raises only ValueError -- main() maps that to exit 2 (unknown);
      any other exception is a traceback with no verdict.
  P2  exit 0 is only ever reached with no evidence of an unreviewed round: no
      bot check, no bot review, no refusal (`absent`), or a recognised count of
      zero at the exact probed head (`clean`).
  P3  a review at an OLDER head never reads as clean, and a running check never
      reads as anything but pending.
  P4  the latest round at the head decides; an earlier round at the same head
      neither blocks forever nor overrides a later verdict.

`_test_bot_review_probe.py` beside the script covers the happy adapter paths;
this file only fuzzes and probes the malformed, hostile, and boundary inputs it
does not reach.

Run standalone for a larger corpus: FUZZ_CASES=40000 pytest <this file>
"""

from __future__ import annotations

import importlib.util
import json
import os
import random
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / ".apm"
    / "skills"
    / "pr-shepherd"
    / "scripts"
    / "bot-review-probe.py"
)
SEED = 20260817
CORPUS_SIZE = int(os.environ.get("FUZZ_CASES", "6000"))
NOW = datetime(2026, 8, 17, 12, 0, 0, tzinfo=UTC)
HEAD = "a" * 40
OLD = "b" * 40
BOTS = ["coderabbitai"]


def _load():
    spec = importlib.util.spec_from_file_location("bot_review_probe_fuzz", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


brp = _load()

CLEARING_STATES = frozenset({"absent", "clean"})


def review(
    body="", *, state="COMMENTED", commit=HEAD, at="2026-08-17T11:00:00Z", login="coderabbitai[bot]"
):
    return {
        "login": login,
        "state": state,
        "body": body,
        "commit": commit,
        "url": "https://example.invalid/r",
        "at": at,
    }


def notice(body, *, at="2026-08-17T11:00:00Z", login="coderabbitai[bot]"):
    return {"login": login, "body": body, "at": at}


def payload(**parts):
    base = {"checks": [], "reviews": [], "comments": [], "notices": []}
    base.update(parts)
    return base


def classify(*, head=HEAD, bots=None, now=NOW, **parts):
    return brp.classify(payload(**parts), head, bots or BOTS, now)


# --- P1: only ValueError escapes --------------------------------------------

BODIES = (
    "",
    "Actionable comments posted: 0",
    "Actionable comments posted: 12",
    "actionable comments posted: 007",
    "**Actionable comments posted: 3**",
    "rate limit reached, try again in 25 minutes",
    "quota reached; retry in 2 hours",
    "review skipped",
    "fair usage",
    "your next included review will be available in 45 minutes",
    "retry in 0 minutes",
    "x" * 20000,
    "ünicode ⏰",
)
HOSTILE = (None, True, False, 0, -1, 1.5, "", "x" * 300, [], {}, [1], {"k": 1}, 10**20)


def test_fuzz_only_value_errors_escape():
    """P1."""
    rnd = random.Random(SEED)
    escapes = []
    for _ in range(CORPUS_SIZE):
        entry = payload(
            checks=rnd.choice(
                [
                    [
                        {
                            "name": rnd.choice(["CodeRabbit", "CI", None, 1, ""]),
                            "status": rnd.choice(["completed", "in_progress", None, 1]),
                            "state": rnd.choice(["SUCCESS", "FAILURE", None]),
                            "detailsUrl": rnd.choice(["https://x/coderabbitai/1", None, 1]),
                        }
                    ],
                    [],
                    None,
                    [None, "s", 1],
                ]
            ),
            reviews=[
                {
                    "login": rnd.choice(["coderabbitai[bot]", "coderabbitai", "human", None, 1]),
                    "state": rnd.choice(["COMMENTED", "CHANGES_REQUESTED", "APPROVED", None, 1]),
                    "body": rnd.choice([*BODIES, None, 1, []]),
                    "commit": rnd.choice([HEAD, OLD, None, 1, ""]),
                    "url": rnd.choice(["u", None]),
                    "at": rnd.choice(["2026-08-17T11:00:00Z", "", "bad", None, 1]),
                }
                for _ in range(rnd.randint(0, 3))
            ],
            comments=rnd.choice(
                [
                    [
                        {
                            "login": "coderabbitai[bot]",
                            "path": rnd.choice(["p", None, 1]),
                            "line": rnd.choice([1, None, "x", []]),
                            "commit": rnd.choice([HEAD, OLD, None]),
                            "url": rnd.choice(["u", None]),
                        }
                    ],
                    [],
                    None,
                    [None, 1],
                ]
            ),
            notices=[
                rnd.choice(
                    [
                        notice(
                            rnd.choice(BODIES),
                            at=rnd.choice(["2026-08-17T11:00:00Z", "", "bad"]),
                            login=rnd.choice(["coderabbitai[bot]", "human"]),
                        ),
                        None,
                    ]
                )
                for _ in range(rnd.randint(0, 2))
            ],
        )
        try:
            result = brp.classify(entry, HEAD, BOTS, NOW)
        except ValueError:
            continue
        except Exception as error:  # noqa: BLE001 - the property under test
            escapes.append((type(error).__name__, str(error), json.dumps(entry, default=str)))
            continue
        assert result["state"] not in CLEARING_STATES or result["code"] == 0
    assert not escapes, escapes[:3]


@pytest.mark.parametrize("entry", [None, [], "s", 1, True])
def test_non_object_payload_is_unknown(entry):
    with pytest.raises(ValueError):
        brp.classify(entry, HEAD, BOTS, NOW)


@pytest.mark.parametrize("field", ["checks", "reviews", "comments", "notices"])
@pytest.mark.parametrize("bad", ["s", 1, {"k": 1}, True])
def test_non_array_evidence_is_unknown(field, bad):
    with pytest.raises(ValueError):
        brp.classify(payload(**{field: bad}), HEAD, BOTS, NOW)


@pytest.mark.parametrize("field", ["checks", "reviews", "comments", "notices"])
def test_null_evidence_reads_as_no_evidence(field):
    """`null` from a gh read is the field being absent, not a malformed one."""
    assert classify(**{field: None})["state"] == "absent"


@pytest.mark.parametrize("member", [None, "s", 1, []])
def test_non_object_review_or_notice_is_unknown(member):
    with pytest.raises(ValueError):
        brp.classify(payload(reviews=[member]), HEAD, BOTS, NOW)
    with pytest.raises(ValueError):
        brp.classify(payload(notices=[member]), HEAD, BOTS, NOW)


def test_non_object_check_or_comment_is_skipped():
    """Checks and comments are filtered by isinstance rather than rejected, so
    one malformed rollup entry does not turn the whole probe unknown.
    """
    assert classify(checks=[None, "s", 1])["state"] == "absent"
    assert (
        classify(
            checks=[{"name": "CodeRabbit", "status": "completed"}],
            reviews=[review("Actionable comments posted: 0")],
            comments=[None, 1],
        )["state"]
        == "clean"
    )


# --- P2/P3: exit 0 is fail-closed -------------------------------------------


def test_review_at_an_older_head_is_stale_never_clean():
    """P3."""
    result = classify(reviews=[review("Actionable comments posted: 0", commit=OLD)])
    assert (result["state"], result["code"]) == ("stale", brp.EXIT_STALE)


@pytest.mark.parametrize("status", ["in_progress", "queued", "", None, "COMPLETED "])
def test_incomplete_bot_check_is_pending(status):
    """P3. `check_state` lowercases, so only exactly "completed" is complete."""
    result = classify(checks=[{"name": "CodeRabbit", "status": status}])
    assert (result["state"], result["code"]) == ("pending", brp.EXIT_WAITING)


def test_legacy_status_check_success_is_not_pending():
    result = classify(
        checks=[{"name": "CodeRabbit", "state": "SUCCESS"}],
        reviews=[review("Actionable comments posted: 0")],
    )
    assert result["state"] == "clean"


def test_completed_check_without_a_review_is_pending_not_clean():
    result = classify(checks=[{"name": "CodeRabbit", "status": "completed"}])
    assert (result["state"], result["code"]) == ("pending", brp.EXIT_WAITING)


def test_unrecognised_verdict_at_head_is_pending_not_clean():
    result = classify(reviews=[review("Looks fine to me, no summary line")])
    assert (result["state"], result["code"]) == ("pending", brp.EXIT_WAITING)


def test_changes_requested_without_a_count_is_actionable():
    result = classify(reviews=[review("no count", state="CHANGES_REQUESTED")])
    assert (result["state"], result["code"]) == ("actionable", brp.EXIT_ACTIONABLE)


def test_changes_requested_with_a_zero_count_still_blocks():
    result = classify(reviews=[review("Actionable comments posted: 0", state="CHANGES_REQUESTED")])
    assert result["state"] == "actionable"


@pytest.mark.parametrize("head", ["", "A" * 40, HEAD[:7], HEAD + "\n"])
def test_head_matching_is_exact(head):
    """A near-miss head must not match a round recorded at the real head."""
    result = brp.classify(
        payload(reviews=[review("Actionable comments posted: 0")]), head, BOTS, NOW
    )
    assert result["state"] not in {"clean"}


def test_empty_bot_list_reports_absent_not_an_error():
    """An empty $PR_REVIEW_BOTS disables the probe entirely: every review is
    invisible, so the round reads as absent and clears the merge.

    Recorded as behaviour, not endorsed: this is the whole gate turning off by
    configuration typo, and nothing in the output says the list was empty.
    """
    assert brp.configured_slugs("") == []
    assert brp.configured_slugs(",  ,") == []
    result = brp.classify(payload(reviews=[review("Actionable comments posted: 9")]), HEAD, [], NOW)
    assert (result["state"], result["code"]) == ("absent", 0)


def test_misconfigured_slug_hides_reviews_entirely():
    """Review authorship is matched EXACTLY (login == slug or slug[bot]) while
    checks are matched fuzzily, so a slug of `coderabbit` still sees the check
    but never the reviews -- an actionable round degrades to pending, not clean.
    """
    entry = payload(
        checks=[{"name": "CodeRabbit", "status": "completed"}],
        reviews=[review("Actionable comments posted: 4")],
    )
    assert brp.classify(entry, HEAD, ["coderabbitai"], NOW)["state"] == "actionable"
    assert brp.classify(entry, HEAD, ["coderabbit"], NOW)["state"] == "pending"


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        ("coderabbitai", "coderabbitai", True),
        ("coderabbit", "coderabbitai", True),
        ("rabbit", "coderabbitai", True),
        ("cod", "coderabbitai", False),
        ("", "coderabbitai", False),
    ],
)
def test_slug_containment_is_symmetric_above_the_floor(left, right, expected):
    """`related` matches in BOTH directions above MIN_SLUG_MATCH, so a
    four-character substring of a slug claims the check.
    """
    assert brp.related(left, right) is expected


def test_unrelated_check_claimed_through_its_details_url():
    """A details URL containing the slug anywhere -- including a repository or
    org name -- makes an unrelated check the bot's check, holding the probe at
    pending until that check finishes.
    """
    result = classify(
        checks=[
            {
                "name": "CI",
                "status": "in_progress",
                "detailsUrl": "https://github.com/acme/coderabbitai-config/actions/runs/1",
            }
        ]
    )
    assert result["state"] == "pending"


# --- P4: latest round at the head wins --------------------------------------


def test_latest_counted_round_at_the_same_head_wins():
    """P4."""
    rounds = [
        review("Actionable comments posted: 5", at="2026-08-17T10:00:00Z"),
        review("Actionable comments posted: 0", at="2026-08-17T11:00:00Z"),
    ]
    assert classify(reviews=rounds)["state"] == "clean"
    assert classify(reviews=list(reversed(rounds)))["state"] == "clean"


def test_a_later_round_finding_new_problems_reopens_the_bounce():
    rounds = [
        review("Actionable comments posted: 0", at="2026-08-17T10:00:00Z"),
        review("Actionable comments posted: 2", at="2026-08-17T11:00:00Z"),
    ]
    assert classify(reviews=rounds)["actionable"] == 2


def test_a_round_with_no_timestamp_sorts_first_and_loses():
    """`at` sorts as a string, so an empty timestamp is the OLDEST round. A
    genuinely newest round that arrives without `submitted_at` is therefore
    discarded in favour of an older one.
    """
    rounds = [
        review("Actionable comments posted: 0", at="2026-01-01T00:00:00Z"),
        review("Actionable comments posted: 5", at=""),
    ]
    assert classify(reviews=rounds)["state"] == "clean"


def test_only_bot_comments_at_the_probed_head_are_listed():
    comments = [
        {"login": "coderabbitai[bot]", "path": "a.py", "line": 3, "commit": HEAD, "url": "u1"},
        {"login": "coderabbitai[bot]", "path": "b.py", "line": 4, "commit": OLD, "url": "u2"},
        {"login": "human", "path": "c.py", "line": 5, "commit": HEAD, "url": "u3"},
    ]
    result = classify(reviews=[review("Actionable comments posted: 1")], comments=comments)
    assert result["files"] == ["a.py:3 u1"]


# --- decline notices --------------------------------------------------------


def test_fresh_decline_without_any_review_is_declined():
    result = classify(notices=[notice("Rate limit reached. Try again in 30 minutes")])
    assert (result["state"], result["code"]) == ("declined", brp.EXIT_DECLINED)
    assert result["wait"] == (NOW - timedelta(minutes=30)).isoformat()


def test_a_real_review_at_head_beats_an_older_decline_notice():
    result = classify(
        reviews=[review("Actionable comments posted: 0")],
        notices=[notice("quota reached; retry in 30 minutes", at="2026-08-17T10:00:00Z")],
    )
    assert result["state"] == "clean"


def test_a_stale_review_beats_a_decline_notice():
    result = classify(
        reviews=[review("Actionable comments posted: 0", commit=OLD)],
        notices=[notice("quota reached; retry in 30 minutes")],
    )
    assert result["state"] == "stale"


@pytest.mark.parametrize(
    "body",
    [
        "limit is currently reached",
        "fair usage limit",
        "rate-limit hit",
        "your quota is exhausted",
        "usage limit reached",
        "review skipped",
    ],
)
def test_every_decline_indicator_is_recognised(body):
    assert brp.indicates_decline(body)


@pytest.mark.parametrize(
    "body",
    [
        "**Actionable comments posted: 3**\n\nAdds rate-limit handling to the client.",
        "Actionable comments posted: 0\n\nsrc/quota.py now enforces the quota.",
        "Actionable comments posted: 2\n\nthe review skipped nothing this round",
    ],
)
def test_a_real_review_body_that_mentions_rate_limiting_is_not_a_decline(body):
    """DEFECT (documented, not xfail because the outcome is fail-CLOSED): the
    decline matcher is deliberately loose, and a genuine round reviewing
    rate-limit or quota CODE is reclassified as a refusal. The count and the
    per-file comment list are dropped, and the operator is told to re-trigger
    the bot rather than fix the findings.
    """
    result = classify(reviews=[review(body)])
    assert result["state"] == "declined"
    assert result["actionable"] == 0
    assert result["files"] == []


def test_declined_never_clears_a_merge():
    """The false-positive decline above is at least not a merge-through."""
    result = classify(reviews=[review("Actionable comments posted: 0\nquota")])
    assert result["code"] == brp.EXIT_DECLINED
    assert result["state"] not in CLEARING_STATES


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("try again in 25 minutes", 25),
        ("try again in 2 hours", 120),
        ("available in **45** minutes", 45),
        ("no figure here", None),
        ("in 0 minutes", 0),
    ],
)
def test_wait_minutes_reads_any_wording(body, expected):
    assert brp.wait_minutes(body) == expected


def test_decline_with_no_figure_is_declined_with_an_unknown_wait():
    result = classify(notices=[notice("rate limit reached")])
    assert (result["state"], result["wait"]) == ("declined", "UNKNOWN")


@pytest.mark.parametrize("at", ["", "not-a-date", "2026-13-45"])
def test_decline_with_an_unreadable_timestamp_reports_the_relative_figure(at):
    result = classify(notices=[notice("rate limit reached, retry in 30 minutes", at=at)])
    assert (result["state"], result["wait"]) == ("declined", "30m")


@pytest.mark.parametrize(
    "body",
    [
        "rate limit reached, retry in 999999999999999999999999 minutes",
        "quota reached; retry in 100000000 hours",
    ],
)
def test_an_absurd_wait_figure_is_clamped_not_a_crash(body):
    """The figure comes from the bot's own prose, so it is data the tool cannot vet.

    `timedelta` raises OverflowError past its range and main() maps only
    ValueError/JSONDecodeError, so an absurd figure exited 1 with a traceback instead
    of a verdict. It is clamped to a week now: anything beyond that means the same
    thing operationally, and the probe still answers.
    """
    minutes = brp.wait_minutes(body)
    assert minutes is not None
    instant = brp.reopen_instant("2026-01-01T00:00:00Z", minutes)
    assert instant is not None, "an absurd figure must still yield an instant"
    assert instant.year == 2026, f"clamp did not bound the figure: {instant}"


def test_a_reopened_window_says_re_trigger():
    result = classify(
        notices=[notice("rate limit reached, retry in 5 minutes", at="2026-08-17T10:00:00Z")]
    )
    assert "reopened" in result["detail"]


def test_a_naive_notice_timestamp_is_read_as_utc():
    assert brp.reopen_instant("2026-08-17T10:00:00", 30) == datetime(
        2026, 8, 17, 10, 30, tzinfo=UTC
    )


def test_the_newest_refusal_notice_wins():
    result = classify(
        notices=[
            notice("rate limit reached, retry in 5 minutes", at="2026-08-17T09:00:00Z"),
            notice("rate limit reached, retry in 90 minutes", at="2026-08-17T11:30:00Z"),
        ]
    )
    assert result["wait"] == datetime(2026, 8, 17, 13, 0, tzinfo=UTC).isoformat()


def test_a_human_refusal_lookalike_is_not_the_bot_declining():
    result = classify(notices=[notice("rate limit reached", login="human")])
    assert result["state"] == "absent"


# --- adapters ---------------------------------------------------------------


def test_unknown_bot_gets_the_generic_adapter():
    adapter = brp.adapter_for("greptile")
    assert adapter.count("Actionable comments posted: 3") is None
    result = brp.classify(
        payload(reviews=[review("x", state="CHANGES_REQUESTED", login="greptile[bot]")]),
        HEAD,
        ["greptile"],
        NOW,
    )
    assert result["state"] == "actionable"


def test_generic_adapter_review_without_changes_requested_is_pending():
    result = brp.classify(
        payload(reviews=[review("looks good", login="greptile[bot]")]),
        HEAD,
        ["greptile"],
        NOW,
    )
    assert result["state"] == "pending"


@pytest.mark.parametrize("count", ["0", "007", "12", "999999999999999999999"])
def test_count_parsing_accepts_any_digit_run(count):
    assert brp.ADAPTERS["coderabbitai"].count(f"Actionable comments posted: {count}") == int(count)


def test_render_is_single_line_per_verdict():
    result = classify(reviews=[review("Actionable comments posted: 0")])
    assert brp.render(result).count("\n") == 0
    assert brp.render(result).startswith("BOT_REVIEW clean ")


# --- CLI and fetch ----------------------------------------------------------


def _classify_cli(stdin: str | bytes, *extra: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "classify", HEAD, "--bots", "coderabbitai", *extra],
        input=stdin,
        capture_output=True,
        text=isinstance(stdin, str),
        check=False,
    )


@pytest.mark.parametrize("stdin", ["", "not json", "null", "[]", "3"])
def test_cli_unreadable_evidence_is_exit_2(stdin):
    completed = _classify_cli(stdin)
    assert completed.returncode == brp.EXIT_UNKNOWN
    assert "Traceback" not in completed.stderr


def test_cli_non_utf8_stdin_is_exit_2():
    completed = _classify_cli(b"\xff\xfe")
    assert completed.returncode == brp.EXIT_UNKNOWN


def test_cli_exit_codes_match_the_state():
    cases = {
        json.dumps(payload()): 0,
        json.dumps(payload(reviews=[review("Actionable comments posted: 0")])): 0,
        json.dumps(payload(reviews=[review("Actionable comments posted: 1")])): brp.EXIT_ACTIONABLE,
        json.dumps(
            payload(reviews=[review("Actionable comments posted: 0", commit=OLD)])
        ): brp.EXIT_STALE,
        json.dumps(
            payload(checks=[{"name": "CodeRabbit", "status": "in_progress"}])
        ): brp.EXIT_WAITING,
        json.dumps(payload(notices=[notice("rate limit reached")])): brp.EXIT_DECLINED,
    }
    for stdin, expected in cases.items():
        assert _classify_cli(stdin).returncode == expected, stdin


def _gh_shim(tmp_path: Path, mode: str) -> dict[str, str]:
    """A fake `gh` on PATH. The real binary is never reachable from these tests."""
    shim = tmp_path / "bin"
    shim.mkdir(exist_ok=True)
    (shim / "gh").write_text(
        "#!/bin/sh\n"
        'case "$GH_FAKE" in\n'
        "  empty) exit 0 ;;\n"
        "  bad) echo 'not json' ;;\n"
        '  fail) echo "gh: HTTP 403" >&2; exit 1 ;;\n'
        "  null) echo null ;;\n"
        "  *) echo '{}' ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    (shim / "gh").chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{shim}{os.pathsep}{env.get('PATH', '')}"
    env["GH_FAKE"] = mode
    return env


def _fetch_cli(env):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "fetch", "owner/repo", "1"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=30,
    )


@pytest.mark.parametrize("mode", ["bad", "fail"])
def test_fetch_reports_unreadable_gh_output_as_unknown(tmp_path, mode):
    completed = _fetch_cli(_gh_shim(tmp_path, mode))
    assert completed.returncode == brp.EXIT_UNKNOWN
    assert "Traceback" not in completed.stderr


@pytest.mark.parametrize("mode", ["empty", "null"])
def test_fetch_refuses_a_payload_with_no_head(tmp_path, mode):
    completed = _fetch_cli(_gh_shim(tmp_path, mode))
    assert completed.returncode == brp.EXIT_UNKNOWN


@pytest.mark.parametrize("mode", ["empty", "null"])
def test_silent_gh_no_longer_clears_the_merge(tmp_path, mode):
    """Silence from an upstream read is not evidence that a check passed.

    `gh` exiting 0 with empty stdout became `null`, which built a payload with an
    empty head and all-empty review arrays -- and that classified as `absent`, exit 0,
    clearing the bot gate as though it had been satisfied. A wedged auth or an empty
    upstream response produced it. gh_json now refuses an empty body outright.
    """
    fetched = _fetch_cli(_gh_shim(tmp_path, mode))
    assert fetched.returncode != 0, "an empty gh body must not read as a clean fetch"
    combined = f"{fetched.stdout}{fetched.stderr}"
    assert "empty output" in combined or "headRefOid" in combined, combined[:200]


def test_fetch_bounds_a_wedged_gh(tmp_path):
    env = _gh_shim(tmp_path, "hang")
    shim = Path(env["PATH"].split(os.pathsep)[0]) / "gh"
    shim.write_text("#!/bin/sh\nsleep 30\n", encoding="utf-8")
    shim.chmod(0o755)
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "fetch", "owner/repo", "1"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=6,
    )
    assert completed.returncode == brp.EXIT_UNKNOWN


def test_bots_subcommand_lists_configured_adapters(tmp_path):
    env = dict(os.environ, PR_REVIEW_BOTS="coderabbitai,greptile")
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "bots"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert completed.returncode == 0
    assert "coderabbitai\t" in completed.stdout
    assert "greptile\t" in completed.stdout


def test_script_is_executable():
    assert SCRIPT.stat().st_mode & 0o111
