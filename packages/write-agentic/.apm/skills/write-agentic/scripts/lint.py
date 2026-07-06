#!/usr/bin/env python3
"""Lint agentic assets (skills, steering, agents) against the write-agentic
format contract. stdlib only.

Usage: lint.py <file> [<file>...]
Exit: 0 clean, 1 any ERROR (WARNs alone stay 0).

Kind detection: SKILL.md -> skill · *.agent.md / agents/*.md -> agent ·
*.instructions.md -> pointer · *.context.md -> context.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Hedges that make a rule subjective. Only flagged on normative lines (sigil
# or bullet lines), not in prose sections like OUTPUT examples.
HEDGES = re.compile(
    r"\b(when (practical|appropriate|possible|needed|available)|consider|"
    r"generally|usually|normally|if necessary|as needed|try to|ideally|"
    r"where possible|genuinely|materially|substantial(ly)?|reasonabl[ye]|"
    r"clearly|obvious(ly)?|large enough|significant(ly)?)\b",
    re.I,
)
MODEL_NAMES = re.compile(r"\b(opus|sonnet|haiku|fable|gpt-\d)\b", re.I)
SIGIL_LINE = re.compile(r"^\s*[!~?−-]\s+\S")
LEGEND = re.compile(r"^LEGEND:")
CAPS_ENUM = re.compile(r"\b[A-Z][A-Z-]{2,}(\|[A-Z][A-Z-]{2,})+\b")
FRONTMATTER_KEY = re.compile(r"^(\w[\w-]*):", re.M)


def words(s: str) -> int:
    return len(s.split())


def detect_kind(path: Path) -> str:
    n = path.name
    if n.startswith("template-"):
        return "template"  # meta-documents with placeholders: skip
    if n == "SKILL.md":
        return "skill"
    if n.endswith(".agent.md") or path.parent.name == "agents":
        return "agent"
    if n.endswith(".instructions.md"):
        return "pointer"
    if n.endswith(".context.md"):
        return "context"
    return "unknown"


def split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm: dict[str, str] = {}
    key = None
    for line in parts[1].splitlines():
        m = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            fm[key] = val
        elif key and line.startswith(" "):
            fm[key] += " " + line.strip()
    return fm, parts[2]


def lint(path: Path) -> list[tuple[str, str, str]]:
    """Return [(severity, code, message)]."""
    out: list[tuple[str, str, str]] = []
    err = lambda c, m: out.append(("ERROR", c, m))
    warn = lambda c, m: out.append(("WARN", c, m))

    text = path.read_text(encoding="utf-8")
    kind = detect_kind(path)
    if kind == "template":
        return out
    fm, body = split_frontmatter(text)
    lines = body.splitlines()

    # E1 frontmatter description
    if kind in ("skill", "agent", "pointer"):
        desc = fm.get("description", "")
        if not desc:
            err("E1", "missing frontmatter description")
        else:
            cap = 15 if kind == "pointer" else 25
            if words(desc) > cap:
                err("E1", f"description {words(desc)}w > {cap}w cap for {kind}")

    # E2 hedges on normative lines
    for i, ln in enumerate(lines, 1):
        if SIGIL_LINE.match(ln) or re.match(r"^\s*[-*]\s+\S", ln):
            m = HEDGES.search(ln)
            if m:
                err("E2", f"line {i}: hedge '{m.group(0)}' — replace with an observable condition")

    # E3 model names outside routing steering
    if "subagent-routing" not in str(path) and kind != "agent":
        for i, ln in enumerate(lines, 1):
            if ln.strip().startswith(("#", "LEGEND")):
                continue
            m = MODEL_NAMES.search(ln)
            if m:
                err("E3", f"line {i}: model name '{m.group(0)}' in prose — route via steering-subagent-routing")

    # E4 sigil use requires a legend
    has_sigils = any(SIGIL_LINE.match(l) and l.strip()[0] in "!~?−" for l in lines)
    has_legend = any(LEGEND.match(l) for l in lines)
    if has_sigils and not has_legend and kind in ("skill", "context"):
        err("E4", "sigil rules present but no LEGEND line")

    # E5 agent output contract
    if kind == "agent":
        if not re.search(r"^#+\s*Output|^OUTPUT", body, re.M):
            err("E5", "agent has no Output contract section")
        else:
            if not CAPS_ENUM.search(body):
                warn("W5", "no CAPS verdict enum (PASS|FAIL style) found in output contract")
            if not re.search(r"\bCAP\b|\b\d+\s*w(ords)?\b|≤\s*\d+", body):
                err("E5", "output contract has no word cap")
        if not re.search(r"never reprint|paths? only|path:line", body, re.I):
            warn("W5", "no no-reprint rule in output contract")

    # E6 size caps
    n_lines = len([l for l in lines if l.strip()])
    caps = {"skill": 70, "context": 60, "pointer": 10, "agent": 90}
    if kind in caps and n_lines > caps[kind]:
        warn("W6", f"{n_lines} non-empty lines > {caps[kind]} target for {kind}")

    # E7 pointer shape
    if kind == "pointer":
        if "applyTo" not in fm:
            err("E7", "pointer missing applyTo glob")
        if not re.search(r"\]\(\.\./context/.*\.context\.md\)", body):
            err("E7", "pointer does not link a ../context/*.context.md file")

    # E8 relative links resolve
    for m in re.finditer(r"\]\((?!https?://)([^)#]+)\)", body):
        target = (path.parent / m.group(1)).resolve()
        if not target.exists():
            err("E8", f"broken link: {m.group(1)}")

    # W9 duplicate rule lines (same normalized text twice)
    seen: dict[str, int] = {}
    for i, ln in enumerate(lines, 1):
        key = re.sub(r"\W+", " ", ln.lower()).strip()
        if len(key) > 30 and (SIGIL_LINE.match(ln) or ln.strip().startswith("-")):
            if key in seen:
                warn("W9", f"line {i} duplicates line {seen[key]}")
            else:
                seen[key] = i

    return out


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    worst = 0
    for arg in argv:
        path = Path(arg)
        if not path.is_file():
            print(f"{arg}: not a file")
            worst = 1
            continue
        kind = detect_kind(path)
        findings = lint(path)
        if not findings:
            print(f"{arg} [{kind}]: OK")
            continue
        for sev, code, msg in findings:
            print(f"{arg} [{kind}] {sev} {code}: {msg}")
            if sev == "ERROR":
                worst = 1
    return worst


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
