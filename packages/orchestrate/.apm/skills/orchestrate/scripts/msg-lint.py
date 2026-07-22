#!/usr/bin/env python3
"""orchestrate: lint an inter-agent message body against the comms grammar
(stdlib-only).

Validates a SendMessage `message` body against the fixed 12-verb protocol
(RULE was removed; APPROVE is the orch->gatekeeper integration handoff and may
carry a validated watcher dispatch or lifecycle receipt):

    ASSIGN BLOCKED REPORTED REVIEW FIX CONFLICT APPROVE MERGED ASK ADVICE DISMISS
    NO_WORK

Rules:
    - line 1 MUST be exactly `VERB <node-id>` (two tokens, nothing else).
    - every other non-blank line MUST be a labeled `field: value` fact; more
      than 2 consecutive non-labeled lines is a prose smell and rejected.
    - each verb has a minimum required field set (checked case-insensitively
      on the label):
        ASSIGN    title, scope, base, store
        BLOCKED   kind(design|debug), need
        REPORTED  verify plus branch+commit(s)/pr or output_ref
        REVIEW    verdict(approve|changes)
        FIX       items
        CONFLICT  with, files
        APPROVE   branch; watcher handoffs also require repo, base, pr, head,
                  plus dispatch or transition+lifecycle
        MERGED    sha, base
        ASK       question
        ADVICE    answer
        DISMISS   (none)
        NO_WORK   epic, queue, reason(no-compatible-work)

Usage:
    msg-lint.py [--file PATH]        # reads stdin if --file omitted
Exit codes: 0 clean, 1 one-or-more violations (one line each on stdout), 2 usage error.
"""

from __future__ import annotations

import argparse
import re
import sys

VERBS = {
    "ASSIGN",
    "BLOCKED",
    "REPORTED",
    "REVIEW",
    "FIX",
    "CONFLICT",
    "APPROVE",
    "MERGED",
    "ASK",
    "ADVICE",
    "DISMISS",
    "NO_WORK",
}

REQUIRED_FIELDS: dict[str, set[str]] = {
    "ASSIGN": {"title", "scope", "base", "store"},
    "BLOCKED": {"kind", "need"},
    "REPORTED": {"verify"},
    "REVIEW": {"verdict"},
    "FIX": {"items"},
    "CONFLICT": {"with", "files"},
    "APPROVE": {"branch"},
    "MERGED": {"sha", "base"},
    "ASK": {"question"},
    "ADVICE": {"answer"},
    "DISMISS": set(),
    "NO_WORK": {"epic", "queue", "reason"},
}

ENUM_FIELDS = {
    "kind": {"design", "debug"},
    "verdict": {"approve", "changes"},
    "reason": {"no-compatible-work"},
}

REPORTED_GIT_REFS = {"commit", "commits", "pr"}

LINE1_RE = re.compile(r"^(\S+)\s+(\S+)\s*$")
FIELD_RE = re.compile(r"^\s*([A-Za-z][\w-]*)\s*:\s*(.*)$")
REPOSITORY_RE = re.compile(r"^[^/\s]+/[^/\s]+$")
POSITIVE_INTEGER_RE = re.compile(r"^[1-9]\d*$")
HEAD_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")

WATCHER_APPROVE_FIELDS = {"repo", "base", "pr", "head", "dispatch"}
WATCHER_LIFECYCLE_FIELDS = {
    "repo",
    "base",
    "pr",
    "head",
    "transition",
    "lifecycle",
}
LIFECYCLE_TRANSITIONS = {"opened", "updated", "failed", "merged", "closed"}

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
    for lineno, line in enumerate(lines[idx + 1 :], start=idx + 2):
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
                    violations.append(
                        f"field {f}={fields[f]!r} must be one of {sorted(allowed)}"
                    )

        if verb == "REPORTED":
            has_branch = bool(fields.get("branch", "").strip())
            git_refs = {
                field for field in REPORTED_GIT_REFS if fields.get(field, "").strip()
            }
            has_output_ref = bool(fields.get("output_ref", "").strip())
            has_git_evidence = has_branch or bool(git_refs)
            if has_output_ref and has_git_evidence:
                violations.append(
                    "REPORTED must not mix git evidence with non-git output_ref"
                )
            elif has_branch and not git_refs:
                violations.append(
                    "REPORTED git evidence requires commit, commits, or pr"
                )
            elif git_refs and not has_branch:
                violations.append("REPORTED git evidence requires branch")
            elif not has_branch and not git_refs and not has_output_ref:
                violations.append(
                    "REPORTED requires git evidence or non-git output_ref"
                )
            if "output_ref" in fields and not has_output_ref:
                violations.append("empty field: output_ref")

        if verb == "NO_WORK":
            for field in ("epic", "queue", "reason"):
                if field in fields and not fields[field].strip():
                    violations.append(f"empty field: {field}")

        if (
            verb == "APPROVE"
            and fields.get("source", "").strip().lower() == "release-queue-watch"
        ):
            for field in sorted(WATCHER_APPROVE_FIELDS - fields.keys()):
                violations.append(f"missing field: {field}")
            for field in sorted((WATCHER_APPROVE_FIELDS | {"branch"}) & fields.keys()):
                if not fields[field].strip():
                    violations.append(f"empty field: {field}")

            repository = fields.get("repo", "")
            pull_request = fields.get("pr", "")
            head_sha = fields.get("head", "")
            if repository and not REPOSITORY_RE.fullmatch(repository):
                violations.append("field repo must be OWNER/REPO")
            if pull_request and not POSITIVE_INTEGER_RE.fullmatch(pull_request):
                violations.append("field pr must be a positive integer")
            if head_sha and not HEAD_SHA_RE.fullmatch(head_sha):
                violations.append("field head must be a hexadecimal Git object id")
            if repository and pull_request and head_sha and fields.get("dispatch"):
                expected_dispatch = f"{repository}#{pull_request}@{head_sha}"
                if fields["dispatch"] != expected_dispatch:
                    violations.append(
                        "field dispatch must equal repo#pr@head for this handoff"
                    )

        if (
            verb == "APPROVE"
            and fields.get("source", "").strip().lower()
            == "release-queue-watch-lifecycle"
        ):
            for field in sorted(WATCHER_LIFECYCLE_FIELDS - fields.keys()):
                violations.append(f"missing field: {field}")
            for field in sorted(
                (WATCHER_LIFECYCLE_FIELDS | {"branch"}) & fields.keys()
            ):
                if not fields[field].strip():
                    violations.append(f"empty field: {field}")

            repository = fields.get("repo", "")
            pull_request = fields.get("pr", "")
            head_sha = fields.get("head", "")
            transition = fields.get("transition", "").strip().lower()
            if repository and not REPOSITORY_RE.fullmatch(repository):
                violations.append("field repo must be OWNER/REPO")
            if pull_request and not POSITIVE_INTEGER_RE.fullmatch(pull_request):
                violations.append("field pr must be a positive integer")
            if head_sha and not HEAD_SHA_RE.fullmatch(head_sha):
                violations.append("field head must be a hexadecimal Git object id")
            if transition and transition not in LIFECYCLE_TRANSITIONS:
                violations.append(
                    f"field transition={transition!r} must be one of "
                    f"{sorted(LIFECYCLE_TRANSITIONS)}"
                )

    return violations


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="msg-lint.py", description=__doc__)
    p.add_argument("--file")
    args = p.parse_args(argv)

    text = (
        sys.stdin.read() if not args.file else open(args.file, encoding="utf-8").read()
    )
    violations = lint(text)
    for v in violations:
        print(v)
    sys.exit(1 if violations else 0)


if __name__ == "__main__":
    main()
