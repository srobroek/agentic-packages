#!/usr/bin/env python3
"""Self-tests for bot-review-probe.py (stdlib unittest, no deps)."""

import importlib.util
import json
import os
import subprocess
import sys
import unittest

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


def payload(checks=None, reviews=None, comments=None):
    return {"checks": checks or [], "reviews": reviews or [], "comments": comments or []}


def classify(data, head=HEAD, bots="coderabbitai"):
    return MODULE.classify(data, head, MODULE.configured_slugs(bots))


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


class MalformedTest(unittest.TestCase):
    def test_non_object_payload_raises(self):
        with self.assertRaises(ValueError):
            classify([1, 2, 3])

    def test_non_array_reviews_raise(self):
        with self.assertRaises(ValueError):
            classify({"checks": [], "reviews": {"login": CODERABBIT}, "comments": []})


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


if __name__ == "__main__":
    unittest.main()
