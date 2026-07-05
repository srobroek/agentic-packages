#!/usr/bin/env python3
"""orchestrate: lint an inter-agent message body against the comms grammar
(stdlib-only).

Validates a SendMessage `message` body against the fixed 11-verb protocol
(RULE was removed; APPROVE is the orch->gatekeeper merge handoff):

    ASSIGN BLOCKED REPORTED REVIEW FIX CONFLICT APPROVE MERGED ASK ADVICE DISMISS

Rules:
    - line 1 MUST be exactly `VERB <node-id>` (two tokens, nothing else).
    - every other non-blank line MUST be a labeled `field: value` fact; more
      than 2 consecutive non-labeled lines is a prose smell and rejected.
    - each verb has a minimum required field set (checked case-insensitively
      on the label):
        ASSIGN    title, scope, base, store
        BLOCKED   kind(design|debug), need
        REPORTED  branch, commits, verify
        REVIEW    verdict(approve|changes)
        FIX       items
        CONFLICT  with, files
        APPROVE   branch
        MERGED    sha, base
        ASK       question
        ADVICE    answer
        DISMISS   (none)

Usage:
    msg-lint.py [--file PATH]        # reads stdin if --file omitted
Exit codes: 0 clean, 1 one-or-more violations (one line each on stdout), 2 usage error.
"""
from __future__ import annotations

import argparse
import re
import sys

VERBS = {
    "ASSIGN", "BLOCKED", "REPORTED", "REVIEW", "FIX", "CONFLICT",
    "APPROVE", "MERGED", "ASK", "ADVICE", "DISMISS",
}

REQUIRED_FIELDS: dict[str, set[str]] = {
    "ASSIGN": {"title", "scope", "base", "store"},
    "BLOCKED": {"kind", "need"},
    "REPORTED": {"branch", "commits", "verify"},
    "REVIEW": {"verdict"},
    "FIX": {"items"},
    "CONFLICT": {"with", "files"},
    "APPROVE": {"branch"},
    "MERGED": {"sha", "base"},
    "ASK": {"question"},
    "ADVICE": {"answer"},
    "DISMISS": set(),
}

ENUM_FIELDS = {
    "kind": {"design", "debug"},
    "verdict": {"approve", "changes"},
}

LINE1_RE = re.compile(r"^(\S+)\s+(\S+)\s*$")
FIELD_RE = re.compile(r"^\s*([A-Za-z][\w-]*)\s*:\s*(.*)$")

MAX_PROSE_RUN = 2  # more than this many consecutive non-labeled lines = smell


def lint(body: str) -> list[str]:
    violations: list[str] = []
    lines = body.splitlines()

    idx = 0
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    if idx >= len(lines):
        return ["line 1: empty message body"]

    line1 = lines[idx]
    m = LINE1_RE.match(line1)
    if not m:
        return [f"line 1: expected 'VERB <node-id>', got {line1!r}"]
    verb = m.group(1)

    known_verb = verb in VERBS
    if not known_verb:
        violations.append(f"line 1: unknown verb {verb!r} (one of {sorted(VERBS)})")

    fields: dict[str, str] = {}
    run = 0
    run_start = 0
    for lineno, line in enumerate(lines[idx + 1:], start=idx + 2):
        if not line.strip():
            run = 0
            continue
        fm = FIELD_RE.match(line)
        if fm:
            fields[fm.group(1).lower()] = fm.group(2).strip()
            run = 0
        else:
            if run == 0:
                run_start = lineno
            run += 1
            if run > MAX_PROSE_RUN:
                violations.append(
                    f"line {run_start}: more than {MAX_PROSE_RUN} consecutive "
                    "non-labeled lines (prose smell)"
                )
                run = 0  # one violation per prose block, not one per line

    if known_verb:
        required = REQUIRED_FIELDS[verb]
        for f in sorted(required - fields.keys()):
            violations.append(f"missing field: {f}")
        for f, allowed in ENUM_FIELDS.items():
            if f in required and f in fields:
                val = fields[f].strip().lower()
                if val not in allowed:
                    violations.append(f"field {f}={fields[f]!r} must be one of {sorted(allowed)}")

    return violations


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="msg-lint.py", description=__doc__)
    p.add_argument("--file")
    args = p.parse_args(argv)

    text = sys.stdin.read() if not args.file else open(args.file, encoding="utf-8").read()
    violations = lint(text)
    for v in violations:
        print(v)
    sys.exit(1 if violations else 0)


if __name__ == "__main__":
    main()
