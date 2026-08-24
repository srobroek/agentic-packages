#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Fail when a role's stated bead contract drifts from the rules file it cites.

The contract block in each agent definition used to be marked `BEGIN GENERATED`,
which was false: no script wrote it, so the marker told a reader that editing was
pointless when hand-editing was the only way it changed. Fourteen files carried
that claim and nothing verified any of them, so a block could contradict its own
rules file silently -- and one did, which is what prompted this.

Generating the prose instead was the obvious fix and it does not work. Identical
predicates produce deliberately different wording: reviewer and scribe both
require `linked.comment.verb in [...]`, but reviewer's block says "linked node"
and scribe's says "linked epic", because those are different resources. A
generator would need a hand-maintained role-to-noun mapping, which moves the drift
rather than removing it.

So the block stays hand-written and this asserts the facts a reader would act on:
every state and metadata key the rules file denies is named in the prose, and the
prose invents no denial the rules file does not contain. Wording stays free;
substance cannot drift.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

AGENTS = Path(__file__).resolve().parent.parent / ".apm" / "agents"
RULES = Path(__file__).resolve().parent.parent / ".apm" / "rules"
BLOCK = re.compile(
    r"<!-- HAND-MAINTAINED: bead contract\. Mirrors (\S+?);.*?-->(.*?)<!-- END HAND-MAINTAINED -->",
    re.DOTALL,
)


def denials(rules: dict) -> tuple[set[str], set[str]]:
    authority = rules.get("authority") or {}
    return set(authority.get("deny_states") or []), set(authority.get("deny_metadata") or [])


def main() -> int:
    failures: list[str] = []
    checked = 0

    for path in sorted(AGENTS.glob("*.agent.md")):
        match = BLOCK.search(path.read_text())
        if match is None:
            continue
        cited, prose = match.group(1), match.group(2)
        rules_path = RULES / Path(cited).name
        if not rules_path.exists():
            failures.append(f"{path.name}: cites {cited}, which does not exist")
            continue

        rules = json.loads(rules_path.read_text())
        deny_states, deny_metadata = denials(rules)
        checked += 1

        # Every denial the evaluator enforces must be visible to the agent reading
        # its own contract. A denial the prose omits is one the agent trips on
        # without warning.
        for state in sorted(deny_states):
            if state not in prose:
                failures.append(f"{path.name}: rules deny state {state!r}, prose omits it")
        for key in sorted(deny_metadata):
            if key not in prose:
                failures.append(f"{path.name}: rules deny metadata {key!r}, prose omits it")

        # And the reverse: prose that forbids more than the rules do trains an
        # agent to avoid something permitted, which is how a role starts refusing
        # legitimate work.
        for key in ("merge_sha", "output_ref", "push", "pr"):
            claimed = re.search(rf"may never (?:carry|write)[^.]*\b{key}\b", prose)
            if claimed and key not in deny_metadata:
                failures.append(f"{path.name}: prose forbids {key!r}, rules permit it")

    for line in failures:
        print(f"  FAIL {line}")
    print(f"agent contract check: {checked} contract(s), {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
