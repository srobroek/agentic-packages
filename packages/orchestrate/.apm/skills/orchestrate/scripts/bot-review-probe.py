#!/usr/bin/env python3
"""Classify a PR review-bot round for one exact head SHA.

Self-contained on purpose: orchestrate and pr-shepherd are separate tools, so
nothing here may reach into another package's scripts at runtime. This is a copy
of pr-shepherd's probe of the same name, on the same terms as conflict-probe.sh.

Review bots (CodeRabbit, Copilot review, Greptile, ...) post findings outside
every status check the merge decision already reads, and each signals
actionability its own way. This script keeps that per-bot knowledge in one
adapter table so adding a bot is a table entry, not a parser change.

`fetch` performs the three gh reads; `classify` is pure and reads that JSON on
stdin, so every classification path is testable without a network.

Exit codes match the landing contract's vocabulary:
  0  absent  no configured bot on this PR; merge decision unchanged
  0  clean   the bot's latest round at this head reports nothing actionable
  10 pending check still running, or no review at this head yet
  11 stale   the bot reviewed an older head only
  12 actionable
  2  unknown malformed or unreadable evidence -- never treated as clean
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Any, Callable, NamedTuple

EXIT_UNKNOWN = 2
EXIT_WAITING = 10
EXIT_STALE = 11
EXIT_ACTIONABLE = 12

DEFAULT_BOTS = "coderabbitai"
# A bot slug is matched against check names and details URLs by alphanumeric
# containment in either direction ("CodeRabbit" vs "coderabbitai"). The floor
# keeps a short slug from matching unrelated checks.
MIN_SLUG_MATCH = 4


class Round(NamedTuple):
    """One bot review round at the probed head."""

    actionable: int | None  # None = the adapter found no count in this body
    changes_requested: bool
    url: str
    at: str


class Adapter(NamedTuple):
    """Per-bot knowledge: how this bot says "here is what you must fix"."""

    slug: str
    # Returns the actionable-finding count for a review body, or None when this
    # body carries no verdict the adapter recognises.
    count: Callable[[str], int | None]
    note: str


def _regex_count(pattern: str) -> Callable[[str], int | None]:
    compiled = re.compile(pattern, re.IGNORECASE)

    def read(body: str) -> int | None:
        match = compiled.search(body or "")
        return int(match.group("n")) if match else None

    return read


# CodeRabbit posts one summary review per round whose body carries
# "Actionable comments posted: N". Every fix suggestion hangs under that
# summary, so N is the actionability signal and a long nitpick-only body with
# N=0 merges.
ADAPTERS: dict[str, Adapter] = {
    "coderabbitai": Adapter(
        slug="coderabbitai",
        count=_regex_count(r"actionable comments posted:\s*(?P<n>\d+)"),
        note='CodeRabbit summary line "Actionable comments posted: N"',
    ),
}

# A bot with no adapter still gets classified: its check and review presence
# are visible, and a CHANGES_REQUESTED verdict is actionable everywhere. Only
# the count is unavailable, which reads as "no recognised verdict yet".
GENERIC_ADAPTER = Adapter(
    slug="",
    count=lambda _body: None,
    note="no adapter: review state only",
)


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def related(left: str, right: str) -> bool:
    if len(left) < MIN_SLUG_MATCH or len(right) < MIN_SLUG_MATCH:
        return False
    return left in right or right in left


def configured_slugs(raw: str | None) -> list[str]:
    source = raw if raw is not None else os.environ.get("PR_REVIEW_BOTS", DEFAULT_BOTS)
    return [part.strip().lower() for part in source.split(",") if part.strip()]


def adapter_for(slug: str) -> Adapter:
    if slug in ADAPTERS:
        return ADAPTERS[slug]
    for known, adapter in ADAPTERS.items():
        if related(normalize(slug), normalize(known)):
            return adapter
    return GENERIC_ADAPTER._replace(slug=slug)


def is_bot_check(check: dict[str, Any], slugs: list[str]) -> bool:
    name = normalize(str(check.get("name") or ""))
    url = normalize(str(check.get("detailsUrl") or ""))
    return any(
        related(name, normalize(slug)) or related(url, normalize(slug)) for slug in slugs
    )


def login_slug(login: str, slugs: list[str]) -> str | None:
    """Return the configured slug this review author is, or None."""
    actual = (login or "").lower()
    for slug in slugs:
        if actual in (slug, f"{slug}[bot]"):
            return slug
    return None


def check_state(check: dict[str, Any]) -> str:
    return str(check.get("status") or check.get("state") or "").lower()


def classify(payload: dict[str, Any], head: str, slugs: list[str]) -> dict[str, Any]:
    """Pure classification. Raises ValueError on evidence it cannot read."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    checks = payload.get("checks") or []
    reviews = payload.get("reviews") or []
    comments = payload.get("comments") or []
    if not isinstance(checks, list) or not isinstance(reviews, list) or not isinstance(comments, list):
        raise ValueError("checks, reviews, and comments must be arrays")

    bot_checks = [c for c in checks if isinstance(c, dict) and is_bot_check(c, slugs)]
    bot_reviews = []
    for review in reviews:
        if not isinstance(review, dict):
            raise ValueError("each review must be an object")
        slug = login_slug(str(review.get("login") or ""), slugs)
        if slug is not None:
            bot_reviews.append((slug, review))

    result: dict[str, Any] = {
        "head": head,
        "bots": ",".join(slugs),
        "check": ",".join(
            f"{c.get('name') or '?'}/{check_state(c) or '?'}" for c in bot_checks
        )
        or "none",
        "actionable": 0,
        "changes_requested": 0,
        "summary": "none",
        "files": [],
    }

    if not bot_checks and not bot_reviews:
        return {**result, "state": "absent", "code": 0,
                "detail": "no configured review bot on this PR"}

    # A PR check rollup always describes the current head, so a running bot
    # check needs no head comparison of its own.
    if any(state != "completed" for state in map(check_state, bot_checks)):
        return {**result, "state": "pending", "code": EXIT_WAITING,
                "detail": "bot check still running"}

    at_head = [
        (slug, review)
        for slug, review in bot_reviews
        if str(review.get("commit") or "") == head
    ]
    at_head.sort(key=lambda pair: str(pair[1].get("at") or ""))

    if not at_head:
        if not bot_reviews:
            return {**result, "state": "pending", "code": EXIT_WAITING,
                    "detail": "bot check complete, no review posted yet"}
        return {**result, "state": "stale", "code": EXIT_STALE,
                "detail": "bot reviewed an older head only"}

    rounds: list[Round] = []
    for slug, review in at_head:
        rounds.append(
            Round(
                actionable=adapter_for(slug).count(str(review.get("body") or "")),
                changes_requested=str(review.get("state") or "") == "CHANGES_REQUESTED",
                url=str(review.get("url") or ""),
                at=str(review.get("at") or ""),
            )
        )

    # A re-review at the same head supersedes the earlier one, so read the
    # LATEST round with a recognised count. Taking the maximum would let a
    # resolved round block the PR forever.
    counted = [r for r in rounds if r.actionable is not None]
    latest = counted[-1] if counted else rounds[-1]
    changes = 1 if rounds[-1].changes_requested else 0
    result["changes_requested"] = changes
    result["summary"] = latest.url or "none"
    result["files"] = sorted(
        f"{c.get('path') or '?'}:{c.get('line') or c.get('original_line') or 0} {c.get('url') or ''}".strip()
        for c in comments
        if isinstance(c, dict)
        and login_slug(str(c.get("login") or ""), slugs) is not None
        and str(c.get("commit") or "") == head
    )

    if latest.actionable is None:
        if changes:
            return {**result, "state": "actionable", "code": EXIT_ACTIONABLE,
                    "detail": "changes requested without a summary count"}
        return {**result, "state": "pending", "code": EXIT_WAITING,
                "detail": "no actionable-comment summary at head yet"}

    result["actionable"] = latest.actionable
    if changes or latest.actionable > 0:
        return {**result, "state": "actionable", "code": EXIT_ACTIONABLE,
                "detail": f"{latest.actionable} actionable comment(s)"}
    return {**result, "state": "clean", "code": 0, "detail": "0 actionable comments"}


def render(result: dict[str, Any]) -> str:
    lines = [
        "BOT_REVIEW {state} bots={bots} head={head} check={check} "
        "actionable={actionable} changes_requested={changes_requested} "
        'summary={summary} detail="{detail}"'.format(**result)
    ]
    lines.extend(f"COMMENT {entry}" for entry in result["files"])
    return "\n".join(lines)


def gh_json(*args: str) -> Any:
    completed = subprocess.run(
        ["gh", *args], capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {completed.stderr.strip()}")
    return json.loads(completed.stdout or "null")


def fetch(repo: str, pr: str) -> dict[str, Any]:
    """Three reads, no classification.

    `gh pr view` omits each review's commit id, so the reviews and their inline
    comments come from REST, paginated because one bot round can exceed a page.
    """
    view = gh_json("pr", "view", pr, "--repo", repo, "--json", "headRefOid,statusCheckRollup")
    reviews = gh_json("api", "--paginate", f"repos/{repo}/pulls/{pr}/reviews")
    comments = gh_json("api", "--paginate", f"repos/{repo}/pulls/{pr}/comments")
    return {
        "head": (view or {}).get("headRefOid") or "",
        "checks": (view or {}).get("statusCheckRollup") or [],
        "reviews": [
            {
                "login": (r.get("user") or {}).get("login") or "",
                "state": r.get("state") or "",
                "body": r.get("body") or "",
                "commit": r.get("commit_id") or "",
                "url": r.get("html_url") or "",
                "at": r.get("submitted_at") or "",
            }
            for r in (reviews or [])
        ],
        "comments": [
            {
                "login": (c.get("user") or {}).get("login") or "",
                "path": c.get("path") or "",
                "line": c.get("line") or c.get("original_line") or 0,
                "commit": c.get("commit_id") or "",
                "url": c.get("html_url") or "",
            }
            for c in (comments or [])
        ],
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    fetch_cmd = sub.add_parser("fetch", help="read PR checks, reviews, and comments")
    fetch_cmd.add_argument("repo")
    fetch_cmd.add_argument("pr")
    classify_cmd = sub.add_parser("classify", help="classify fetched JSON on stdin")
    classify_cmd.add_argument("head", help="exact head SHA the round must match")
    classify_cmd.add_argument("--bots", help="comma-separated bot slugs (default $PR_REVIEW_BOTS)")
    sub.add_parser("bots", help="list configured bots and their adapters")
    args = parser.parse_args(argv)

    if args.command == "fetch":
        try:
            print(json.dumps(fetch(args.repo, args.pr)))
        except (RuntimeError, json.JSONDecodeError) as error:
            print(f"bot-review-probe: {error}", file=sys.stderr)
            return EXIT_UNKNOWN
        return 0

    if args.command == "bots":
        for slug in configured_slugs(None):
            print(f"{slug}\t{adapter_for(slug).note}")
        return 0

    try:
        payload = json.load(sys.stdin)
        result = classify(payload, args.head, configured_slugs(args.bots))
    except (ValueError, json.JSONDecodeError) as error:
        print(f"bot-review-probe: cannot classify: {error}", file=sys.stderr)
        return EXIT_UNKNOWN
    print(render(result))
    return int(result["code"])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
