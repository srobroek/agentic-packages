#!/usr/bin/env python3
"""Deterministic slop/status-language linter for documentation. stdlib only.

Usage: slop-lint.py [--genre consumer|change|internal] <file> [<file>...]
Exit: 0 clean (WARNs alone stay 0), 1 any ERROR, 2 usage error.

Genre defaults by path when --genre is absent:
  README* / docs/**            -> consumer
  specs/** / adr / ADR / CONTRIBUTING / .specify/** -> internal
  everything else              -> consumer

Codes:
  E1 status language        (all genres)   "under construction", "WIP", "coming soon", ...
  E2 slop lexicon           (all genres)   "seamlessly", "blazingly fast", "leverage", ...
  E3 internal references    (consumer)     specs/, ADR-, constitution, "extracted from", ...
  E4 history narration      (consumer, internal)  "previously", "renamed from", ...
  W1 long prose block       (all genres)   paragraph > 80 words
  W2 emoji in heading       (all genres)
  W3 borderline hype        (all genres)   "simply", "intuitive", "just works", ...

Suppression: append `<!-- write-docs:allow E2 -->` to a line (or place it on the
line directly above) to suppress that code for that line. Fenced code blocks
are skipped entirely.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

STATUS_LANGUAGE = re.compile(
    r"\b(under construction|work[- ]in[- ]progress|WIP|coming soon|"
    r"being (specified|designed|implemented|built)|not yet (implemented|supported|available)|"
    r"will (eventually|later|soon)\b|to be (implemented|defined|determined)|TBD|TODO|"
    r"for now|at the moment|"
    r"currently(?! (running|active|open|connected|executing|loaded|mounted))|"
    r"as of (now|writing|today)|"
    r"planned( for)?|on the roadmap|in (a )?future (release|version)|stay tuned)\b",
    re.I,
)

SLOP_LEXICON = re.compile(
    r"\b(seamless(ly)?|effortless(ly)?|blazing(ly)?([- ]fast)?|cutting[- ]edge|"
    r"state[- ]of[- ]the[- ]art|game[- ]chang\w+|revolutioni[sz]\w+|supercharg\w+|"
    r"unleash\w*|empower\w*|delve\w*|elevat(e|ing) your|"
    r"robust|powerful|comprehensive|best[- ]in[- ]class|world[- ]class|"
    r"battle[- ]tested|production[- ]grade|feature[- ]rich|rich set of|"
    r"leverag(e|es|ed|ing)|elegant(ly)?|"
    r"streamlin\w+|turbocharg\w+|next[- ]generation|next[- ]gen)\b",
    re.I,
)

INTERNAL_REFS = re.compile(
    r"(\bspecs?/|\.specify/|\bADRs?\b|\bADR[- ]?\d+|\bconstitution\b|"
    r"\bdesign doc(ument)?\b|per the spec\b|as specified in\b|"
    r"extracted from\b|mirrors (the )?\w+ (package|repo)|aligned with\b)",
    re.I,
)

HISTORY_NARRATION = re.compile(
    r"\b(previously|formerly|used to (be|do|have)|has been (refactored|migrated|renamed|rewritten)|"
    r"was (refactored|migrated|renamed|rewritten|extracted)|renamed from|moved (over )?from|"
    r"we (dropped|removed|changed|switched|migrated)|no longer\b|instead of the old)\b",
    re.I,
)

BORDERLINE_HYPE = re.compile(
    r"\b(simply|just works|easy to use|easily|intuitive(ly)?|flexible|"
    r"hassle[- ]free|out of the box|plug[- ]and[- ]play)\b",
    re.I,
)

EMOJI = re.compile(
    "[\U0001f300-\U0001faff\U00002600-\U000027bf\U00002b00-\U00002bff\U0000fe0f]"
)

ALLOW = re.compile(r"<!--\s*write-docs:allow\s+([EW]\d)\s*-->")

PROSE_WORD_CAP = 80


def detect_genre(path: Path) -> str:
    s = str(path).lower()
    name = path.name.lower()
    if (
        "/specs/" in s
        or s.startswith("specs/")
        or "/.specify/" in s
        or "adr" in name
        or "/adr" in s
        or "constitution" in name
        or name.startswith("contributing")
    ):
        return "internal"
    return "consumer"


def _strip_fences(lines: list[str]) -> list[tuple[int, str]]:
    """Return (1-based line number, text) pairs outside fenced code blocks."""
    out: list[tuple[int, str]] = []
    fence = None
    for i, ln in enumerate(lines, 1):
        stripped = ln.lstrip()
        m = re.match(r"(```+|~~~+)", stripped)
        if m:
            tok = m.group(1)[0] * 3
            if fence is None:
                fence = tok
            elif stripped.startswith(fence):
                fence = None
            continue
        if fence is None:
            out.append((i, ln))
    return out


def _allowed(code: str, ln: str, prev: str) -> bool:
    for src in (ln, prev):
        m = ALLOW.search(src)
        if m and m.group(1) == code:
            return True
    return False


def _is_escaped(text: str, index: int) -> bool:
    backslashes = 0
    index -= 1
    while index >= 0 and text[index] == "\\":
        backslashes += 1
        index -= 1
    return backslashes % 2 == 1


def _strip_inline_code(line: str) -> str:
    """Mask complete, unescaped Markdown code spans without shifting text."""
    masked = list(line)
    cursor = 0
    while cursor < len(line):
        if line[cursor] != "`" or _is_escaped(line, cursor):
            cursor += 1
            continue

        opener_end = cursor
        while opener_end < len(line) and line[opener_end] == "`":
            opener_end += 1
        delimiter = line[cursor:opener_end]
        search_from = opener_end
        closer = -1
        while True:
            candidate = line.find(delimiter, search_from)
            if candidate < 0:
                break
            exact_run = (
                (candidate == 0 or line[candidate - 1] != "`")
                and (
                    candidate + len(delimiter) == len(line)
                    or line[candidate + len(delimiter)] != "`"
                )
            )
            if exact_run and not _is_escaped(line, candidate):
                closer = candidate
                break
            search_from = candidate + 1

        if closer < 0:
            cursor = opener_end
            continue
        span_end = closer + len(delimiter)
        masked[cursor:span_end] = " " * (span_end - cursor)
        cursor = span_end
    return "".join(masked)


def lint(path: Path, genre: str) -> list[tuple[str, str, int, str]]:
    """Return [(severity, code, line, message)]."""
    findings: list[tuple[str, str, int, str]] = []
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    visible = _strip_fences(lines)

    checks: list[tuple[str, str, re.Pattern, str]] = [
        ("ERROR", "E1", STATUS_LANGUAGE, "status language"),
        ("ERROR", "E2", SLOP_LEXICON, "slop lexicon"),
    ]
    if genre == "consumer":
        checks.append(("ERROR", "E3", INTERNAL_REFS, "internal reference"))
    if genre in ("consumer", "internal"):
        checks.append(("ERROR", "E4", HISTORY_NARRATION, "history narration"))
    checks.append(("WARN", "W3", BORDERLINE_HYPE, "borderline hype"))

    for idx, (lineno, ln) in enumerate(visible):
        prev = visible[idx - 1][1] if idx else ""
        prose = _strip_inline_code(ln)
        # Skip markdown link URLs for E3 would over-permit; scan whole line.
        for sev, code, pattern, label in checks:
            m = pattern.search(prose)
            if m and not _allowed(code, ln, prev):
                findings.append(
                    (sev, code, lineno, f"{label}: {m.group(0)!r}")
                )
        if ln.lstrip().startswith("#") and EMOJI.search(ln):
            if not _allowed("W2", ln, prev):
                findings.append(("WARN", "W2", lineno, "emoji in heading"))

    # W1 long prose block: consecutive non-list/non-table/non-heading lines.
    block_words, block_start = 0, 0
    prose_line = re.compile(r"^\s*(?![-*+>#|]|\d+\.\s)(\S.*)$")

    def flush() -> None:
        nonlocal block_words, block_start
        if block_words > PROSE_WORD_CAP:
            findings.append(
                (
                    "WARN",
                    "W1",
                    block_start,
                    f"prose block of {block_words} words > {PROSE_WORD_CAP} — convert to a list or table",
                )
            )
        block_words, block_start = 0, 0

    for lineno, ln in visible:
        if prose_line.match(ln):
            if block_words == 0:
                block_start = lineno
            block_words += len(ln.split())
        else:
            flush()
    flush()

    findings.sort(key=lambda f: f[2])
    return findings


def main(argv: list[str]) -> int:
    genre = None
    files: list[str] = []
    i = 0
    while i < len(argv):
        if argv[i] == "--genre":
            if i + 1 >= len(argv) or argv[i + 1] not in ("consumer", "change", "internal"):
                print("--genre requires consumer|change|internal")
                return 2
            genre = argv[i + 1]
            i += 2
        else:
            files.append(argv[i])
            i += 1
    if not files:
        print(__doc__)
        return 2

    worst = 0
    for arg in files:
        path = Path(arg)
        if not path.is_file():
            print(f"{arg}: not a file")
            worst = 1
            continue
        g = genre or detect_genre(path)
        findings = lint(path, g)
        if not findings:
            print(f"{arg} [{g}]: OK")
            continue
        for sev, code, lineno, msg in findings:
            print(f"{arg} [{g}] {sev} {code} line {lineno}: {msg}")
            if sev == "ERROR":
                worst = 1
    return worst


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
