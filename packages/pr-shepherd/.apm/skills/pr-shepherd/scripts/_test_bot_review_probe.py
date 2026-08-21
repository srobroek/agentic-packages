#!/usr/bin/env python3
"""Self-tests for bot-review-probe.py (stdlib unittest, no deps)."""

import importlib.util
import json
import os
import subprocess
import sys
import unittest
from datetime import UTC, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PROBE = os.path.join(HERE, "bot-review-probe.py")
SPEC = importlib.util.spec_from_file_location("bot_review_probe", PROBE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

HEAD = "a" * 40
OLD_HEAD = "b" * 40
CODERABBIT = "coderabbitai[bot]"


def review(body="", commit=HEAD, state="COMMENTED", login=CODERABBIT, url="u", at="x"):
    return {"login": login, "state": state, "body": body, "commit": commit,
            "url": url, "at": at}


def comment(path="a.py", line=12, commit=HEAD, login=CODERABBIT, url="c"):
    return {"login": login, "path": path, "line": line, "commit": commit, "url": url}


def payload(checks=None, reviews=None, comments=None, notices=None):
    return {"checks": checks or [], "reviews": reviews or [], "comments": comments or [],
            "notices": notices or []}


NOW = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
POSTED = "2026-07-30T11:00:00Z"
# CodeRabbit's wording at the time of the incident. The probe must not depend on
# this exact sentence -- see the reworded variants below.
LIMIT_BODY = (
    "Your included review limit is currently reached under our Fair Usage Limits "
    "Policy. This review may still proceed through usage-based billing if eligible. "
    "Your next included review will be available in 48 minutes."
)


def notice(body=LIMIT_BODY, at=POSTED, login=CODERABBIT):
    return {"login": login, "body": body, "at": at}


def classify(data, head=HEAD, bots="coderabbitai", now=NOW):
    return MODULE.classify(data, head, MODULE.configured_slugs(bots), now=now)


def run_cli(data, head=HEAD, env_extra=None, raw=None):
    env = os.environ.copy()
    env.pop("PR_REVIEW_BOTS", None)
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, PROBE, "classify", head],
        input=raw if raw is not None else json.dumps(data),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


class AbsenceTest(unittest.TestCase):
    def test_no_configured_bot_is_absent_not_a_wait(self):
        result = classify(payload(checks=[{"name": "test", "status": "COMPLETED"}]))
        self.assertEqual(result["state"], "absent")
        self.assertEqual(result["code"], 0)

    def test_human_reviews_alone_are_not_a_bot_round(self):
        result = classify(payload(reviews=[review(login="sjors", state="APPROVED", body="lgtm")]))
        self.assertEqual(result["state"], "absent")

    def test_unconfigured_bot_stays_invisible(self):
        data = payload(
            checks=[{"name": "Greptile", "status": "COMPLETED"}],
            reviews=[review(login="greptile-apps[bot]", body="Actionable comments posted: 3")],
        )
        self.assertEqual(classify(data)["state"], "absent")


class PendingTest(unittest.TestCase):
    def test_running_check_is_pending(self):
        result = classify(payload(checks=[{"name": "CodeRabbit", "status": "IN_PROGRESS"}]))
        self.assertEqual(result["state"], "pending")
        self.assertEqual(result["code"], MODULE.EXIT_WAITING)

    def test_check_matched_by_details_url(self):
        data = payload(checks=[{"name": "review", "detailsUrl": "https://coderabbit.ai/x",
                                "status": "IN_PROGRESS"}])
        self.assertEqual(classify(data)["state"], "pending")

    def test_completed_check_without_a_review_is_still_pending(self):
        data = payload(checks=[{"name": "CodeRabbit", "status": "COMPLETED"}])
        result = classify(data)
        self.assertEqual(result["state"], "pending")
        self.assertIn("no review posted yet", result["detail"])

    def test_review_without_a_recognised_verdict_is_pending(self):
        data = payload(reviews=[review(body="just some prose")])
        self.assertEqual(classify(data)["state"], "pending")


class StaleTest(unittest.TestCase):
    def test_review_of_an_older_head_only_is_stale_never_clean(self):
        data = payload(reviews=[review(body="Actionable comments posted: 3", commit=OLD_HEAD)])
        result = classify(data)
        self.assertEqual(result["state"], "stale")
        self.assertEqual(result["code"], MODULE.EXIT_STALE)


class VerdictTest(unittest.TestCase):
    def test_zero_actionable_is_clean(self):
        data = payload(
            checks=[{"name": "CodeRabbit", "status": "COMPLETED"}],
            reviews=[review(body="**Actionable comments posted: 0**\n\nnitpicks follow")],
        )
        result = classify(data)
        self.assertEqual(result["state"], "clean")
        self.assertEqual(result["code"], 0)
        self.assertEqual(result["actionable"], 0)

    def test_actionable_count_bounces_and_lists_only_bot_comments_at_head(self):
        data = payload(
            checks=[{"name": "CodeRabbit", "status": "COMPLETED"}],
            reviews=[review(body="Actionable comments posted: 2", url="u2")],
            comments=[
                comment(path="a.py", url="c1"),
                comment(path="human.py", login="sjors", url="c9"),
                comment(path="old.py", commit=OLD_HEAD, url="c8"),
            ],
        )
        result = classify(data)
        self.assertEqual(result["state"], "actionable")
        self.assertEqual(result["code"], MODULE.EXIT_ACTIONABLE)
        self.assertEqual(result["actionable"], 2)
        self.assertEqual(result["files"], ["a.py:12 c1"])
        self.assertEqual(result["summary"], "u2")

    def test_changes_requested_without_a_count_is_actionable(self):
        data = payload(reviews=[review(state="CHANGES_REQUESTED", body="no count here")])
        result = classify(data)
        self.assertEqual(result["state"], "actionable")
        self.assertEqual(result["changes_requested"], 1)

    def test_latest_round_at_the_same_head_supersedes_an_earlier_one(self):
        data = payload(
            checks=[{"name": "CodeRabbit", "status": "COMPLETED"}],
            reviews=[
                review(body="Actionable comments posted: 5", url="r1", at="2026-01-01T00:00:00Z"),
                review(body="Actionable comments posted: 0", url="r2", at="2026-01-02T00:00:00Z"),
            ],
        )
        result = classify(data)
        self.assertEqual(result["state"], "clean")
        self.assertEqual(result["summary"], "r2")

    def test_a_later_round_finding_new_problems_reopens_the_bounce(self):
        data = payload(
            checks=[{"name": "CodeRabbit", "status": "COMPLETED"}],
            reviews=[
                review(body="Actionable comments posted: 0", url="r1", at="2026-01-01T00:00:00Z"),
                review(body="Actionable comments posted: 3", url="r2", at="2026-01-02T00:00:00Z"),
            ],
        )
        self.assertEqual(classify(data)["actionable"], 3)

    def test_unordered_timestamps_still_pick_the_latest(self):
        data = payload(
            checks=[{"name": "CodeRabbit", "status": "COMPLETED"}],
            reviews=[
                review(body="Actionable comments posted: 4", url="late", at="2026-01-09T00:00:00Z"),
                review(body="Actionable comments posted: 0", url="early", at="2026-01-02T00:00:00Z"),
            ],
        )
        result = classify(data)
        self.assertEqual(result["state"], "actionable")
        self.assertEqual(result["summary"], "late")

    def test_latest_unrecognized_round_does_not_reuse_an_older_count(self):
        data = payload(
            checks=[{"name": "CodeRabbit", "status": "COMPLETED"}],
            reviews=[
                review(body="Actionable comments posted: 0", url="r1", at="2026-01-01T00:00:00Z"),
                review(body="review still processing", url="r2", at="2026-01-02T00:00:00Z"),
            ],
        )
        self.assertEqual(classify(data)["state"], "pending")


class SlugMatchingTest(unittest.TestCase):
    def test_short_slug_does_not_match_unrelated_checks(self):
        data = payload(checks=[{"name": "test", "status": "IN_PROGRESS"}])
        self.assertEqual(classify(data, bots="ai")["state"], "absent")

    def test_another_bot_works_by_configuration_alone(self):
        data = payload(
            checks=[{"name": "Greptile Review", "status": "COMPLETED"}],
            reviews=[review(login="greptile-apps[bot]", state="CHANGES_REQUESTED", body="fix it")],
        )
        result = classify(data, bots="greptile-apps")
        self.assertEqual(result["state"], "actionable")

    def test_bot_without_an_adapter_reports_state_only(self):
        """No count parser: a COMMENTED round is a wait, not a silent pass."""
        data = payload(
            checks=[{"name": "Greptile Review", "status": "COMPLETED"}],
            reviews=[review(login="greptile-apps[bot]", body="Actionable comments posted: 2")],
        )
        result = classify(data, bots="greptile-apps")
        self.assertEqual(result["state"], "pending")

    def test_adapter_is_reused_for_a_slug_variant(self):
        data = payload(
            checks=[{"name": "CodeRabbit", "status": "COMPLETED"}],
            reviews=[review(login="coderabbit[bot]", body="Actionable comments posted: 1")],
        )
        result = classify(data, bots="coderabbit")
        self.assertEqual(result["state"], "actionable")
        self.assertEqual(result["actionable"], 1)

    def test_multiple_bots_are_configured_together(self):
        data = payload(
            checks=[{"name": "CodeRabbit", "status": "COMPLETED"}],
            reviews=[review(body="Actionable comments posted: 0")],
        )
        self.assertEqual(classify(data, bots="coderabbitai, greptile-apps")["state"], "clean")


class DeclineTest(unittest.TestCase):
    def test_limit_notice_with_no_review_is_declined(self):
        data = payload(checks=[{"name": "CodeRabbit", "status": "COMPLETED"}],
                       notices=[notice()])
        result = classify(data)
        self.assertEqual(result["state"], "declined")
        self.assertEqual(result["code"], MODULE.EXIT_DECLINED)

    def test_reopen_instant_is_relative_to_when_the_notice_was_posted(self):
        data = payload(notices=[notice()])
        # Posted 11:00 + 48m = 11:48, already past at NOW=12:00.
        self.assertIn("reopened", classify(data)["detail"])
        self.assertIn("2026-07-30T11:48:00", classify(data)["wait"])

    def test_a_live_window_says_retry_after_not_reopened(self):
        data = payload(notices=[notice(at="2026-07-30T11:59:00Z")])
        result = classify(data)
        self.assertIn("retry after", result["detail"])
        self.assertNotIn("reopened", result["detail"])

    def test_hours_are_converted_to_minutes(self):
        data = payload(notices=[notice(body="Rate limited. Try again in 2 hours.",
                                      at="2026-07-30T11:59:00Z")])
        result = classify(data)
        self.assertEqual(result["state"], "declined")
        self.assertIn("2026-07-30T13:59:00", result["wait"])

    def test_no_parseable_figure_is_declined_with_an_unknown_wait(self):
        """An unparsed deadline must read as re-check, never as a reopened window."""
        data = payload(notices=[notice(body="Your review limit is currently reached.")])
        result = classify(data)
        self.assertEqual(result["state"], "declined")
        self.assertEqual(result["wait"], "UNKNOWN")
        self.assertIn("re-check", result["detail"])
        self.assertNotIn("reopened", result["detail"])

    def test_reworded_notices_still_parse(self):
        """The match is deliberately loose: wording, order, and markup all vary."""
        variants = [
            "**Review limit reached.** Your next included review will be available in: 30 minutes",
            "Fair Usage Limits Policy — next review in 30 minutes.",
            "Rate limited; 30 minute cooldown remains before the next review.",
            "Quota reached. In 30 minutes your next review becomes available.",
        ]
        for body in variants:
            with self.subTest(body=body):
                result = classify(payload(notices=[notice(body=body)]))
                self.assertEqual(result["state"], "declined")
                self.assertIn("2026-07-30T11:30:00", result["wait"])

    def test_a_duration_without_a_refusal_indicator_is_not_a_decline(self):
        data = payload(notices=[notice(body="I will re-review in 30 minutes if you push.")])
        self.assertEqual(classify(data)["state"], "absent")

    def test_a_declining_review_body_is_not_counted_as_a_review_round(self):
        data = payload(checks=[{"name": "CodeRabbit", "status": "COMPLETED"}],
                       reviews=[review(body=LIMIT_BODY, at=POSTED)])
        self.assertEqual(classify(data)["state"], "declined")

    def test_an_unconfigured_bots_notice_is_invisible(self):
        data = payload(notices=[notice(login="greptile-apps[bot]")])
        self.assertEqual(classify(data)["state"], "absent")

    def test_the_newest_notice_sets_the_window(self):
        data = payload(notices=[
            notice(body="Rate limited, retry in 5 minutes.", at="2026-07-30T09:00:00Z"),
            notice(body="Rate limited, retry in 90 minutes.", at="2026-07-30T11:30:00Z"),
        ])
        self.assertIn("2026-07-30T13:00:00", classify(data)["wait"])


class EvidenceBeatsNoticeTest(unittest.TestCase):
    """A refusal notice lives in comment history forever; a real review outranks it."""

    def test_a_review_at_head_beats_an_old_limit_notice(self):
        data = payload(
            checks=[{"name": "CodeRabbit", "status": "COMPLETED"}],
            reviews=[review(body="Actionable comments posted: 0", at="2026-07-30T11:50:00Z")],
            notices=[notice(at="2026-07-30T09:00:00Z")],
        )
        result = classify(data)
        self.assertEqual(result["state"], "clean")
        self.assertEqual(result["code"], 0)

    def test_an_actionable_review_at_head_beats_an_old_limit_notice(self):
        data = payload(
            checks=[{"name": "CodeRabbit", "status": "COMPLETED"}],
            reviews=[review(body="Actionable comments posted: 3", at="2026-07-30T11:50:00Z")],
            notices=[notice(at="2026-07-30T09:00:00Z")],
        )
        result = classify(data)
        self.assertEqual(result["state"], "actionable")
        self.assertEqual(result["actionable"], 3)

    def test_a_decline_from_an_earlier_commit_does_not_mask_the_head_review(self):
        data = payload(
            checks=[{"name": "CodeRabbit", "status": "COMPLETED"}],
            reviews=[
                review(body=LIMIT_BODY, commit=OLD_HEAD, at="2026-07-30T09:00:00Z"),
                review(body="Actionable comments posted: 0", at="2026-07-30T11:50:00Z"),
            ],
        )
        self.assertEqual(classify(data)["state"], "clean")

    def test_a_review_at_an_older_head_only_is_stale_not_declined(self):
        data = payload(
            checks=[{"name": "CodeRabbit", "status": "COMPLETED"}],
            reviews=[review(body="Actionable comments posted: 3", commit=OLD_HEAD)],
            notices=[notice(at="2026-07-30T09:00:00Z")],
        )
        result = classify(data)
        self.assertEqual(result["state"], "stale")
        self.assertEqual(result["code"], MODULE.EXIT_STALE)

    def test_a_running_check_still_wins_over_a_limit_notice(self):
        data = payload(checks=[{"name": "CodeRabbit", "status": "IN_PROGRESS"}],
                       notices=[notice()])
        result = classify(data)
        self.assertEqual(result["state"], "pending")
        self.assertEqual(result["code"], MODULE.EXIT_WAITING)

    def test_no_notice_keeps_the_existing_pending_case(self):
        data = payload(checks=[{"name": "CodeRabbit", "status": "COMPLETED"}])
        result = classify(data)
        self.assertEqual(result["state"], "pending")
        self.assertIn("no review posted yet", result["detail"])


class MalformedTest(unittest.TestCase):
    def test_non_object_payload_raises(self):
        with self.assertRaises(ValueError):
            classify([1, 2, 3])

    def test_non_array_reviews_raise(self):
        with self.assertRaises(ValueError):
            classify({"checks": [], "reviews": {"login": CODERABBIT}, "comments": []})

    def test_non_array_notices_raise(self):
        with self.assertRaises(ValueError):
            classify({"checks": [], "reviews": [], "comments": [], "notices": {"a": 1}})


class CliTest(unittest.TestCase):
    def test_exit_codes_and_rendering(self):
        result = run_cli(payload(
            checks=[{"name": "CodeRabbit", "status": "COMPLETED"}],
            reviews=[review(body="Actionable comments posted: 1", url="u1")],
            comments=[comment(url="c1")],
        ))
        self.assertEqual(result.returncode, MODULE.EXIT_ACTIONABLE)
        self.assertIn("BOT_REVIEW actionable", result.stdout)
        self.assertIn("COMMENT a.py:12 c1", result.stdout)

    def test_declined_exits_thirteen_and_renders_the_wait(self):
        result = run_cli(payload(checks=[{"name": "CodeRabbit", "status": "COMPLETED"}],
                                notices=[notice()]))
        self.assertEqual(result.returncode, MODULE.EXIT_DECLINED)
        self.assertIn("BOT_REVIEW declined", result.stdout)
        self.assertIn("wait=2026-07-30T11:48:00", result.stdout)

    def test_malformed_json_is_unknown_never_clean(self):
        result = run_cli(None, raw="notjson")
        self.assertEqual(result.returncode, MODULE.EXIT_UNKNOWN)
        self.assertNotIn("clean", result.stdout)

    def test_env_configures_bots_without_a_flag(self):
        result = run_cli(
            payload(checks=[{"name": "Greptile", "status": "IN_PROGRESS"}]),
            env_extra={"PR_REVIEW_BOTS": "greptile"},
        )
        self.assertEqual(result.returncode, MODULE.EXIT_WAITING)

    def test_default_bots_apply_with_no_env(self):
        result = run_cli(payload(checks=[{"name": "CodeRabbit", "status": "IN_PROGRESS"}]))
        self.assertEqual(result.returncode, MODULE.EXIT_WAITING)
        self.assertIn("bots=coderabbitai", result.stdout)

    def test_bots_subcommand_lists_adapters(self):
        env = os.environ.copy()
        env["PR_REVIEW_BOTS"] = "coderabbitai,greptile-apps"
        result = subprocess.run([sys.executable, PROBE, "bots"], capture_output=True,
                                text=True, env=env, check=False)
        self.assertEqual(result.returncode, 0)
        self.assertIn("Actionable comments posted", result.stdout)
        self.assertIn("no adapter", result.stdout)


class FetchTest(unittest.TestCase):
    def test_fetch_slurps_and_flattens_all_rest_pages(self):
        original = MODULE.gh_json
        calls = []

        def fake_gh_json(*args):
            calls.append(args)
            if args[0] == "pr":
                return {"headRefOid": HEAD, "statusCheckRollup": []}
            return [[{"user": {"login": "coderabbitai[bot]"}}], []]

        MODULE.gh_json = fake_gh_json
        try:
            result = MODULE.fetch("owner/repo", "7")
        finally:
            MODULE.gh_json = original

        paginated = [call for call in calls if call[0] == "api"]
        self.assertEqual(len(paginated), 3)
        self.assertTrue(all("--paginate" in call and "--slurp" in call for call in paginated))
        self.assertEqual(len(result["reviews"]), 1)


if __name__ == "__main__":
    unittest.main()
