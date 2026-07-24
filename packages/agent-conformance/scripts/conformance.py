#!/usr/bin/env python3
"""Agent conformance harness — deterministic engine.

Subcommands: check | stage | assert | report
No LLM calls; stdlib + PyYAML only.

Usage (from repo root):
  uv run --with pyyaml packages/agent-conformance/scripts/conformance.py check
  uv run --with pyyaml packages/agent-conformance/scripts/conformance.py stage --all
  uv run --with pyyaml packages/agent-conformance/scripts/conformance.py assert \\
      --manifest .conformance-runs/<ts>/manifest.json --case reviewer-low/case-clean
  uv run --with pyyaml packages/agent-conformance/scripts/conformance.py report \\
      --out-dir .conformance-runs/<ts>/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import signal
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HARNESS_VERSION = "0.1.0"

# Matches verdict enum runs like PASS|FAIL|FLAKY (≥2 all-caps tokens joined by |)
# Mirrors the CAPS_ENUM regex from write-agentic/lint.py.
CAPS_ENUM = re.compile(r"\b[A-Z][A-Z-]{2,}(\|[A-Z][A-Z-]{2,})+\b")

# CAP line formats:
#   CAP 100w clean · 180w with findings
#   CAP 100 words clean, 180 words with findings
#   CAP 90 words clean, 180 words with findings
#   CAP 140w.
#   CAP uncapped
#   ≤ N words
# The second regime's noun varies across the fleet ("with findings",
# "with blockers", "with signals") — match any word so a contract like
# "CAP 60 words clean, 220 words with signals" derives 60/220, not 60/60.
_CAP_DUAL = re.compile(
    r"\bCAP\s+(\d+)\s*w(?:ords?)?\s+clean[^·\d]*[·,]\s*(\d+)\s*w(?:ords?)?\s+with\s+\w+",
    re.I,
)
_CAP_SINGLE = re.compile(r"\bCAP\s+(\d+)\s*w(?:ords?)?[.\s]", re.I)
_CAP_UNCAPPED = re.compile(r"\bCAP\s+uncapped\b", re.I)
_CAP_PROSE = re.compile(r"≤\s*(\d+)\s*w(?:ords?)?", re.I)

# Nested quantifier heuristic: (a+)+ style patterns that cause catastrophic backtracking.
# Catches (X+)+ / (X+)* / (X*)+ / (X*)*  with at least one inner quantifier.
_NESTED_QUANTIFIER = re.compile(r"\([^)]*[+*][^)]*\)[+*?]")

# High-entropy credential patterns for reply redaction (R11.3)
_CRED_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[A-Z0-9]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    # Generic long base64/hex token — 40+ chars of base64 or hex alphabet
    re.compile(r"[A-Za-z0-9+/=_-]{40,}"),
]

DEFAULT_TIMEOUT_S = 120
DEFAULT_MAX_REPLY_BYTES = 65536
DEFAULT_BUDGET_USD = 1.00
NO_REPRINT_THRESHOLD = 160  # normalized chars: verbatim run ≥ this triggers fail
PLAUSIBILITY_FLOOR_BYTES = 50
MAX_REGEX_LEN = 500
RETRIES = 2  # attempts after initial: total max = 1 + RETRIES = 3


# ---------------------------------------------------------------------------
# Repository discovery
# ---------------------------------------------------------------------------


def find_repo_root(start: Path | None = None) -> Path:
    """Walk up from start until we find the directory that contains packages/."""
    here = start or Path(__file__).resolve().parent
    for candidate in [here, *here.parents]:
        if (candidate / "packages").is_dir():
            return candidate
    raise RuntimeError(f"Could not find repo root (no packages/ dir) from {here}")


def discover_agents(repo_root: Path) -> list[dict]:
    """Return list of {name, path, package} for every *.agent.md under packages/."""
    agents = []
    for p in sorted(repo_root.glob("packages/*/.apm/agents/*.agent.md")):
        package = p.parts[p.parts.index("packages") + 1]
        agents.append({"name": p.stem.replace(".agent", ""), "path": p, "package": package})
    return agents


# ---------------------------------------------------------------------------
# Agent frontmatter + contract derivation
# ---------------------------------------------------------------------------


def parse_agent_file(path: Path) -> dict:
    """Parse frontmatter and body from an agent markdown file."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {"name": path.stem, "model": None, "effort": None, "tools": None, "body": text}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {"name": path.stem, "model": None, "effort": None, "tools": None, "body": text}
    fm = yaml.safe_load(parts[1]) or {}
    body = parts[2]
    return {
        "name": fm.get("name", path.stem),
        "model": fm.get("model"),
        "effort": fm.get("effort"),
        "tools": fm.get("tools"),
        "body": body,
    }


def derive_contract(agent: dict) -> dict:
    """Derive first_line_pattern, caps, and no_reprint from agent body.

    Returns:
      first_line_pattern: str | None
      caps: {clean: int|None, findings: int|None, uncapped: bool}
      no_reprint: bool
    """
    body = agent["body"]

    # Locate ## Output section
    output_section = ""
    m = re.search(r"^#+\s*Output\b.*$", body, re.M | re.I)
    if m:
        output_section = body[m.start():]
        # Trim at next same-or-higher-level heading
        next_h = re.search(r"^#{1,3}\s+\S", output_section[len(m.group()):], re.M)
        if next_h:
            output_section = output_section[: len(m.group()) + next_h.start()]

    first_line_pattern = _derive_first_line(output_section)
    caps = _derive_caps(output_section)
    no_reprint = bool(re.search(r"never reprint", body, re.I))

    return {"first_line_pattern": first_line_pattern, "caps": caps, "no_reprint": no_reprint}


def _derive_first_line(section: str) -> str | None:
    """Derive a first-line regex from the Output section, or None if not derivable."""
    if not section:
        return None

    lines = section.splitlines()
    for ln in lines:
        stripped = ln.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # L1 VERDICT: APPROVE|CHANGES pattern
        m = re.match(r"^L1\s+(.+)$", stripped)
        if m:
            content = m.group(1).strip()
            return _l1_content_to_regex(content)

        # Structured line: AGENT-NAME <something> verdict=A|B
        # Detect if it contains a CAPS_ENUM (verdict-bearing structured line)
        if CAPS_ENUM.search(stripped) and not stripped.startswith("CAP") and "≤" not in stripped:
            return _structured_line_to_regex(stripped)

        # Prose cap line — not a first-line pattern
        if _CAP_DUAL.search(stripped) or _CAP_SINGLE.search(stripped) or _CAP_UNCAPPED.search(stripped):
            continue

        break  # first content line that isn't a cap line and has no clear pattern

    return None


def _l1_content_to_regex(content: str) -> str:
    """Turn 'VERDICT: APPROVE|CHANGES|ESCALATE — one sentence why.' into a regex.

    The trailing prose explanation after the last CAPS_ENUM is intentionally
    omitted — the pattern matches 'VERDICT: APPROVE <anything>' not the literal
    wording of the hint in the Output section.
    """
    result = "^"
    last = 0
    for em in CAPS_ENUM.finditer(content):
        result += re.escape(content[last : em.start()])
        opts = em.group(0).split("|")
        result += "(?:" + "|".join(re.escape(o) for o in opts) + ")"
        last = em.end()
    # Do NOT include the trailing prose — it's a hint, not part of the match.
    result = result + r"\b"
    return result


_PLACEHOLDER = re.compile(r"<[^>]+>")


def _structured_line_to_regex(line: str) -> str:
    """Turn 'LINT-GUARD <node> verdict=PASS|WARN|BLOCK items=<N>' into a regex.

    Replaces <placeholder> tokens with \\S+ before escaping, then handles
    CAPS_ENUM runs as alternation groups.
    """
    # First, replace <placeholder> tokens with a sentinel that survives re.escape
    # We'll substitute SENTINEL_i for each placeholder, then replace post-escape.
    sentinels: list[str] = []
    sentinel_base = "\x00PH"  # non-printing char prefix, safe from re.escape

    def _replace_placeholder(m: re.Match) -> str:
        idx = len(sentinels)
        sentinels.append(m.group(0))
        return f"{sentinel_base}{idx}\x00"

    line_with_sentinels = _PLACEHOLDER.sub(_replace_placeholder, line)

    result = "^"
    last = 0
    for em in CAPS_ENUM.finditer(line_with_sentinels):
        segment = line_with_sentinels[last : em.start()]
        segment_re = re.escape(segment)
        # Restore sentinels in the escaped segment
        for i in range(len(sentinels)):
            segment_re = segment_re.replace(re.escape(f"{sentinel_base}{i}\x00"), r"\S+")
        result += segment_re
        opts = em.group(0).split("|")
        result += "(?:" + "|".join(re.escape(o) for o in opts) + ")"
        last = em.end()

    tail = line_with_sentinels[last:]
    tail_re = re.escape(tail)
    for i in range(len(sentinels)):
        tail_re = tail_re.replace(re.escape(f"{sentinel_base}{i}\x00"), r"\S+")
    result += tail_re
    return result


def _derive_caps(section: str) -> dict:
    """Derive word caps from the Output section."""
    caps = {"clean": None, "findings": None, "uncapped": False}
    if not section:
        return caps

    # Search the whole section (not just first line) for CAP declarations
    m = _CAP_DUAL.search(section)
    if m:
        caps["clean"] = int(m.group(1))
        caps["findings"] = int(m.group(2))
        return caps

    m = _CAP_UNCAPPED.search(section)
    if m:
        caps["uncapped"] = True
        return caps

    m = _CAP_SINGLE.search(section)
    if m:
        # Single cap applies to both regimes (clean only contracts)
        caps["clean"] = int(m.group(1))
        caps["findings"] = int(m.group(1))
        return caps

    m = _CAP_PROSE.search(section)
    if m:
        caps["clean"] = int(m.group(1))
        caps["findings"] = int(m.group(1))
        return caps

    return caps


# ---------------------------------------------------------------------------
# Fixture loading + validation
# ---------------------------------------------------------------------------


def fixtures_dir(repo_root: Path) -> Path:
    return repo_root / "packages" / "agent-conformance" / "fixtures"


def load_skips(repo_root: Path) -> list[dict]:
    p = fixtures_dir(repo_root) / "skips.yaml"
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text()) or {}
    return data.get("skips", [])


def load_cases(repo_root: Path, agent_name: str) -> list[dict]:
    """Load all case-*.yaml for an agent."""
    d = fixtures_dir(repo_root) / agent_name
    if not d.is_dir():
        return []
    cases = []
    for p in sorted(d.glob("case-*.yaml")):
        data = yaml.safe_load(p.read_text())
        if data:
            data["_path"] = p
            data["_slug"] = p.stem
            cases.append(data)
    return cases


def validate_path_key(key: str) -> str | None:
    """Return error message if the sandbox file key is unsafe, else None."""
    if key.startswith("/"):
        return f"absolute path not allowed: {key!r}"
    parts = Path(key).parts
    if ".." in parts:
        return f"path traversal not allowed: {key!r}"
    return None


def validate_regex(pattern: str, context: str) -> str | None:
    """Return error message if pattern is unsafe or invalid, else None."""
    if len(pattern) > MAX_REGEX_LEN:
        return f"{context}: regex too long ({len(pattern)} > {MAX_REGEX_LEN})"
    if _NESTED_QUANTIFIER.search(pattern):
        return f"{context}: nested quantifier detected (catastrophic backtracking risk)"
    try:
        re.compile(pattern)
    except re.error as e:
        return f"{context}: invalid regex: {e}"
    return None


def validate_case(case: dict, contract: dict, agent_name: str) -> list[str]:
    """Return list of violation strings for a case dict."""
    violations = []
    slug = case.get("_slug", "?")
    prefix = f"{agent_name}/{slug}"

    def v(msg: str) -> None:
        violations.append(f"{prefix}: {msg}")

    # Required fields
    if case.get("regime") not in ("clean", "findings"):
        v(f"regime must be 'clean' or 'findings', got {case.get('regime')!r}")

    if not case.get("prompt"):
        v("prompt is required")

    assert_block = case.get("assert", {}) or {}
    if "max_words" not in assert_block:
        v("assert.max_words is required")

    # Sandbox path keys
    sandbox = case.get("sandbox", {}) or {}
    for key in (sandbox.get("files") or {}).keys():
        err = validate_path_key(key)
        if err:
            v(err)

    # Regex fields
    regex_fields = [
        ("assert.first_line", assert_block.get("first_line")),
    ]
    for pat in assert_block.get("required_patterns") or []:
        regex_fields.append(("assert.required_patterns[]", pat))
    for pat in assert_block.get("forbidden_patterns") or []:
        regex_fields.append(("assert.forbidden_patterns[]", pat))
    for art in assert_block.get("artifacts") or []:
        if isinstance(art, dict) and art.get("line_pattern"):
            regex_fields.append(("assert.artifacts[].line_pattern", art["line_pattern"]))

    for field, pattern in regex_fields:
        if pattern:
            err = validate_regex(str(pattern), f"{prefix}/{field}")
            if err:
                v(err)

    caps = contract.get("caps", {})
    regime = case.get("regime")

    # Drift: case max_words vs derived cap
    max_words = assert_block.get("max_words")
    if isinstance(max_words, int) and regime and not caps.get("uncapped"):
        derived = caps.get(regime)
        if derived is not None and max_words != derived:
            v(
                f"assert.max_words={max_words} drifts from derived contract cap "
                f"for regime={regime}: {derived}"
            )

    # Drift: contract declares a first line but the case does not assert it.
    # (Both-absent is a stderr warning in check(); asserting a line the
    # contract lacks is caught by authoring review, not derivable here.)
    case_fl = assert_block.get("first_line")
    derived_fl = contract.get("first_line_pattern")
    if derived_fl and not case_fl:
        v("assert.first_line missing but the agent contract declares a first-line format (FR-011)")

    return violations


# ---------------------------------------------------------------------------
# check subcommand
# ---------------------------------------------------------------------------


def cmd_check(args: argparse.Namespace, repo_root: Path) -> int:
    agents = discover_agents(repo_root)
    skips = load_skips(repo_root)
    skip_names = {s["agent"] for s in skips}

    violations: list[str] = []
    total_cases = 0
    total_skips = len(skips)

    # Validate skip entries
    agent_names = {a["name"] for a in agents}
    for skip in skips:
        aname = skip.get("agent", "")
        reason = skip.get("reason", "")
        if not aname:
            violations.append("SKIP: skip entry missing agent name")
        elif aname not in agent_names:
            violations.append(f"AGENT {aname}: stale skip entry (agent not found)")
        if not reason or len(reason.strip()) < 10:
            violations.append(f"AGENT {aname}: skip reason too short (< 10 chars)")

    for agent_info in agents:
        name = agent_info["name"]
        agent_data = parse_agent_file(agent_info["path"])
        contract = derive_contract(agent_data)
        cases = load_cases(repo_root, name)

        # Coverage: must have cases or skip
        if not cases and name not in skip_names:
            violations.append(f"AGENT {name}: no cases and no skip entry")
            continue

        # Both cased and skipped?
        if cases and name in skip_names:
            violations.append(f"AGENT {name}: appears in both cases and skips.yaml")

        if name in skip_names:
            continue

        total_cases += len(cases)

        # Validate each case
        for case in cases:
            case_violations = validate_case(case, contract, name)
            for cv in case_violations:
                violations.append(f"AGENT {cv}")

            # Warn when both case first_line and derived first_line_pattern absent
            assert_block = case.get("assert", {}) or {}
            case_fl = assert_block.get("first_line")
            derived_fl = contract.get("first_line_pattern")
            if not case_fl and not derived_fl:
                print(
                    f"WARN {name}/{case.get('_slug', '?')}: "
                    "no first_line in case or derived contract — skipping first-line assertion",
                    file=sys.stderr,
                )

    # Stale case directories (dir exists but no agent)
    fix_dir = fixtures_dir(repo_root)
    if fix_dir.is_dir():
        for d in fix_dir.iterdir():
            if d.is_dir() and d.name not in agent_names:
                violations.append(f"AGENT {d.name}: stale case dir (agent not found)")

    if violations:
        for v in violations:
            print(v)
        return 1

    print(f"OK: {len(agents)} agents, {total_cases} cases, {total_skips} skips")
    return 0


# ---------------------------------------------------------------------------
# stage subcommand
# ---------------------------------------------------------------------------


def resolve_agent_registry(name: str, repo_root: Path) -> bool:
    """Return True if agent is in the installed registry."""
    # Check repo-local .claude/agents/
    repo_agents = repo_root / ".claude" / "agents"
    if (repo_agents / f"{name}.md").exists():
        return True
    # Check user global ~/.claude/agents/
    home_agents = Path.home() / ".claude" / "agents"
    if (home_agents / f"{name}.md").exists():
        return True
    return False


def _sha256_hex16(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def stage_sandbox(sandbox_cfg: dict | None, sandbox_dir: Path) -> None:
    """Create sandbox dir and stage files; optionally git init."""
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    if not sandbox_cfg:
        return
    files = sandbox_cfg.get("files") or {}
    for rel_path, content in files.items():
        target = sandbox_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(content), encoding="utf-8")

    if sandbox_cfg.get("git"):
        subprocess.run(
            ["git", "-c", "user.email=conformance@test", "-c", "user.name=conformance",
             "init"],
            cwd=sandbox_dir, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-c", "user.email=conformance@test", "-c", "user.name=conformance",
             "add", "."],
            cwd=sandbox_dir, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-c", "user.email=conformance@test", "-c", "user.name=conformance",
             "commit", "-m", "fixture: initial staged files"],
            cwd=sandbox_dir, check=True, capture_output=True,
        )


def select_cases(
    args: argparse.Namespace, agents: list[dict], repo_root: Path
) -> list[tuple[dict, dict]]:
    """Return list of (agent_info, case) pairs matching the selection flags."""
    if args.all:
        selected_agents = agents
    elif getattr(args, "agent", None):
        names = set(args.agent)
        selected_agents = [a for a in agents if a["name"] in names]
    elif getattr(args, "package", None):
        pkgs = set(args.package)
        selected_agents = [a for a in agents if a["package"] in pkgs]
    else:
        selected_agents = agents  # default: all

    pairs = []
    for agent_info in selected_agents:
        cases = load_cases(repo_root, agent_info["name"])
        for case in cases:
            pairs.append((agent_info, case))
    return pairs


def cmd_stage(args: argparse.Namespace, repo_root: Path) -> int:
    agents = discover_agents(repo_root)
    skips = load_skips(repo_root)

    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        out_dir = repo_root / ".conformance-runs" / ts

    out_dir.mkdir(parents=True, exist_ok=True)

    pairs = select_cases(args, agents, repo_root)
    if not pairs:
        print("stage: no cases matched selection", file=sys.stderr)
        return 1

    # Verify all selected agents are installed
    missing = []
    seen_agents = {ai["name"] for ai, _ in pairs}
    for name in seen_agents:
        if not resolve_agent_registry(name, repo_root):
            missing.append(name)
    if missing:
        print(
            f"stage: agents not found in installed registry: {', '.join(sorted(missing))}\n"
            "Install missing agents before staging.",
            file=sys.stderr,
        )
        return 2

    today_iso = datetime.now(UTC).strftime("%Y-%m-%d")
    manifest_entries = []
    (out_dir / "sandboxes").mkdir(exist_ok=True)
    (out_dir / "replies").mkdir(exist_ok=True)

    for agent_info, case in pairs:
        name = agent_info["name"]
        slug = case["_slug"]
        agent_data = parse_agent_file(agent_info["path"])

        # Context fingerprint: sha256[:16] of agent file bytes + harness version + date
        fp_data = agent_info["path"].read_bytes() + HARNESS_VERSION.encode() + today_iso.encode()
        context_fingerprint = _sha256_hex16(fp_data)

        sandbox_dir = out_dir / "sandboxes" / name / slug
        reply_dir = out_dir / "replies" / name
        reply_dir.mkdir(parents=True, exist_ok=True)
        stage_sandbox(case.get("sandbox"), sandbox_dir)

        model_source = "pinned" if agent_data["model"] else "inherited-session"
        assert_block = case.get("assert", {}) or {}

        entry = {
            "agent": name,
            "case": slug,
            "prompt": case.get("prompt", ""),
            "sandbox_path": str(sandbox_dir),
            "reply_path": str(reply_dir / f"{slug}-attempt1.txt"),
            "model": agent_data["model"],
            "effort": agent_data["effort"],
            "model_source": model_source,
            "timeout_s": case.get("timeout_s", DEFAULT_TIMEOUT_S),
            "budget_usd": case.get("budget_usd", DEFAULT_BUDGET_USD),
            "max_reply_bytes": case.get("max_reply_bytes", DEFAULT_MAX_REPLY_BYTES),
            "regime": case.get("regime", "clean"),
            "context_fingerprint": context_fingerprint,
            # Assertion data for assert subcommand
            "assert": {
                "first_line": assert_block.get("first_line"),
                "max_words": assert_block.get("max_words"),
                "no_reprint": assert_block.get("no_reprint", True),
                "required_patterns": assert_block.get("required_patterns") or [],
                "forbidden_patterns": assert_block.get("forbidden_patterns") or [],
                "artifacts": assert_block.get("artifacts") or [],
            },
            # Fixture content needed for no-reprint check
            "_fixture_content": _collect_fixture_content(case),
        }
        manifest_entries.append(entry)

    manifest = {
        "run_id": out_dir.name,
        "cases": manifest_entries,
        "skips": skips,
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(str(manifest_path))
    return 0


def _collect_fixture_content(case: dict) -> str:
    """Gather prompt + sandbox file contents for no-reprint checking."""
    parts = [case.get("prompt", "")]
    sandbox = case.get("sandbox", {}) or {}
    for content in (sandbox.get("files") or {}).values():
        parts.append(str(content))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# assert subcommand
# ---------------------------------------------------------------------------


def _normalize_text(text: str) -> str:
    """Collapse whitespace runs to single space for comparison."""
    return re.sub(r"\s+", " ", text).strip()


_TIMED_OUT = object()  # sentinel: distinguishes timeout from no-match


def _timed_search(pattern: str, text: str, timeout: int = 5):
    """Best-effort bounded re.search. Returns the sentinel _TIMED_OUT on timeout.

    CPython only runs signal handlers between bytecode instructions, so
    SIGALRM cannot interrupt a single catastrophic re.search mid-C-call.
    The PRIMARY defenses are upstream: check-time pattern vetting
    (_NESTED_QUANTIFIER + length bound) and the max_reply_bytes input cap.
    This alarm remains as a tripwire for multi-call assertion loops, and is
    skipped off the main thread (signal.signal raises ValueError there).
    """
    try:
        old = signal.signal(signal.SIGALRM, _raise_timeout)
    except ValueError:  # not on the main thread (e.g. pytest plugins/threads)
        return re.search(pattern, text)
    try:
        signal.alarm(timeout)
        return re.search(pattern, text)
    except TimeoutError:
        return _TIMED_OUT
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def _raise_timeout(signum: int, frame: object) -> None:
    raise TimeoutError("regex timeout")


def _check_no_reprint(reply: str, fixture_content: str) -> bool:
    """Return True (fail) if a verbatim run of ≥160 normalized chars from
    fixture appears contiguously in the reply.

    Per R4: segment fixture at line boundaries; for each contiguous segment
    ≥ threshold chars, check if it appears verbatim in the normalized reply.
    This prevents false positives from many short legitimate citations.
    """
    norm_reply = _normalize_text(reply)
    # Build segments: join consecutive non-empty lines, break on blank lines
    segments: list[str] = []
    current_lines: list[str] = []
    for line in fixture_content.splitlines():
        if line.strip():
            current_lines.append(line.strip())
        else:
            if current_lines:
                segments.append(" ".join(current_lines))
            current_lines = []
    if current_lines:
        segments.append(" ".join(current_lines))

    for segment in segments:
        norm_seg = _normalize_text(segment)
        if len(norm_seg) >= NO_REPRINT_THRESHOLD:
            if norm_seg in norm_reply:
                return True
    return False


def _redact_reply(reply: str) -> str:
    """Redact high-entropy credential-ish tokens before persisting non-PASS replies."""
    for pat in _CRED_PATTERNS:
        reply = pat.sub("[REDACTED]", reply)
    return reply


def _run_assertions(entry: dict, reply: str) -> list[dict]:
    """Run all assertions. Return list of {kind, detail} failures."""
    failures: list[dict] = []
    assert_cfg = entry.get("assert", {}) or {}

    # Plausibility floor — handled as ERROR upstream, but check here too
    # (assert subcommand is the final authority on plausibility)
    if len(reply.encode("utf-8")) < PLAUSIBILITY_FLOOR_BYTES:
        return [{"kind": "implausible-reply", "detail": f"reply {len(reply.encode())} bytes < {PLAUSIBILITY_FLOOR_BYTES}"}]

    # Byte size cap
    max_reply_bytes = entry.get("max_reply_bytes", DEFAULT_MAX_REPLY_BYTES)
    if len(reply.encode("utf-8")) > max_reply_bytes:
        failures.append({"kind": "max_reply_bytes", "detail": f"{len(reply.encode())} > {max_reply_bytes}"})

    # First line match — strip the extracted line so ^-anchored patterns
    # match replies with leading indentation or CR from CRLF endings.
    first_line_pat = assert_cfg.get("first_line")
    if first_line_pat:
        first_nonempty = next((ln.strip() for ln in reply.splitlines() if ln.strip()), "")
        m = _timed_search(first_line_pat, first_nonempty)
        if m is _TIMED_OUT:
            failures.append({"kind": "regex_timeout", "detail": "first_line pattern timed out"})
        elif m is None:
            failures.append({"kind": "first_line", "detail": "first non-empty line did not match pattern"})

    # Word cap
    max_words = assert_cfg.get("max_words")
    if max_words is not None and max_words != "uncapped":
        word_count = len(reply.split())
        if word_count > int(max_words):
            failures.append({"kind": "max_words", "detail": f"{word_count} words > {max_words}"})

    # No-reprint
    no_reprint = assert_cfg.get("no_reprint", True)
    fixture_content = entry.get("_fixture_content", "")
    if no_reprint and fixture_content:
        if _check_no_reprint(reply, fixture_content):
            failures.append({"kind": "no_reprint", "detail": "verbatim fixture segment ≥160 chars found in reply"})

    # Required patterns
    for pat in assert_cfg.get("required_patterns") or []:
        m = _timed_search(pat, reply, timeout=5)
        if m is _TIMED_OUT:
            failures.append({"kind": "regex_timeout", "detail": f"pattern timed out: {pat!r}"})
        elif m is None:
            failures.append({"kind": "required_pattern", "detail": f"pattern not found: {pat!r}"})

    # Forbidden patterns
    for pat in assert_cfg.get("forbidden_patterns") or []:
        m = _timed_search(pat, reply, timeout=5)
        if m is _TIMED_OUT:
            failures.append({"kind": "regex_timeout", "detail": f"forbidden pattern timed out: {pat!r}"})
        elif m is not None:
            failures.append({"kind": "forbidden_pattern", "detail": f"forbidden pattern found: {pat!r}"})

    # Artifacts
    sandbox_path_str = entry.get("sandbox_path", "")
    sandbox_path = Path(sandbox_path_str) if sandbox_path_str else None
    for art in assert_cfg.get("artifacts") or []:
        if not isinstance(art, dict):
            continue
        art_path_glob = art.get("path", "")
        line_pattern = art.get("line_pattern")
        if not sandbox_path:
            failures.append({"kind": "artifact", "detail": "no sandbox_path to check artifact"})
            continue
        matched = list(sandbox_path.glob(art_path_glob)) if art_path_glob else []
        if not matched:
            failures.append({"kind": "artifact", "detail": f"no files matched glob {art_path_glob!r}"})
        elif line_pattern:
            found = False
            for fp in matched:
                if fp.is_file():
                    for line in fp.read_text(encoding="utf-8", errors="replace").splitlines():
                        m = _timed_search(line_pattern, line, timeout=5)
                        if m is not None and m is not _TIMED_OUT:
                            found = True
                            break
                if found:
                    break
            if not found:
                failures.append({"kind": "artifact", "detail": f"line_pattern not matched in {art_path_glob!r}"})

    return failures


def load_manifest_entry(manifest_path: Path, case_key: str) -> dict | None:
    """Find an entry in manifest.json by 'agent/case' key."""
    data = json.loads(manifest_path.read_text())
    for entry in data.get("cases", []):
        key = f"{entry['agent']}/{entry['case']}"
        if key == case_key:
            return entry
    return None


def load_journal(out_dir: Path) -> dict[str, dict]:
    """Load journal.jsonl into {agent/case: CaseResult} dict."""
    journal_path = out_dir / "journal.jsonl"
    results: dict[str, dict] = {}
    if not journal_path.exists():
        return results
    for line in journal_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            key = f"{rec['agent']}/{rec['case']}"
            results[key] = rec
        except Exception:
            pass
    return results


def write_journal_entry(out_dir: Path, record: dict) -> None:
    """Append or update a journal entry. Update = rewrite the file replacing the key line."""
    journal_path = out_dir / "journal.jsonl"
    key = f"{record['agent']}/{record['case']}"
    existing_lines: list[str] = []
    found = False
    if journal_path.exists():
        for line in journal_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if f"{rec['agent']}/{rec['case']}" == key:
                    existing_lines.append(json.dumps(record))
                    found = True
                    continue
            except Exception:
                pass
            existing_lines.append(line)
    if not found:
        existing_lines.append(json.dumps(record))
    journal_path.write_text("\n".join(existing_lines) + "\n", encoding="utf-8")


def cmd_assert(args: argparse.Namespace, repo_root: Path) -> int:
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"assert: manifest not found: {manifest_path}", file=sys.stderr)
        return 2

    case_key = args.case  # "agent/case"
    entry = load_manifest_entry(manifest_path, case_key)
    if entry is None:
        print(f"assert: case {case_key!r} not found in manifest", file=sys.stderr)
        return 2

    out_dir = manifest_path.parent

    # Determine attempt number
    results = load_journal(out_dir)
    existing = results.get(case_key)
    if args.attempt is not None:
        attempt_n = int(args.attempt)
    else:
        attempt_n = len(existing["attempts"]) + 1 if existing else 1

    # Determine reply path for this attempt
    base_reply = Path(entry["reply_path"])
    if attempt_n == 1:
        reply_path = base_reply
    else:
        reply_path = base_reply.parent / base_reply.name.replace("attempt1", f"attempt{attempt_n}")

    # The manifest is user-supplied input; never read/write outside its own
    # run directory (a tampered reply_path could otherwise target any file).
    try:
        reply_path.resolve().relative_to(out_dir.resolve())
    except ValueError:
        print(f"assert: reply_path escapes the run directory: {reply_path}", file=sys.stderr)
        return 2

    # Read reply
    if not reply_path.exists():
        print(f"assert: reply file not found: {reply_path}", file=sys.stderr)
        return 2
    try:
        reply = reply_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        print(f"assert: cannot read reply: {e}", file=sys.stderr)
        return 2

    # Plausibility floor (R4): ERROR, not judged
    if len(reply.encode("utf-8")) < PLAUSIBILITY_FLOOR_BYTES:
        print(f"ASSERT {case_key} attempt={attempt_n} passed=false failed=implausible-reply")
        # Record as ERROR
        _record_attempt(
            out_dir, entry, existing, attempt_n, passed=False,
            failures=[{"kind": "implausible-reply", "detail": "reply too short"}],
            reply_path=str(reply_path), is_error=True,
        )
        return 2

    # Run assertions
    failures = _run_assertions(entry, reply)
    passed = len(failures) == 0

    # Redact every persisted reply in place — PASS replies also remain on
    # disk in the run dir, and a conforming reply can still echo a secret.
    redacted = _redact_reply(reply)
    if redacted != reply:
        reply_path.write_text(redacted, encoding="utf-8")

    # Determine verdict
    attempts_so_far = (existing["attempts"] if existing else [])
    total_attempts = len(attempts_so_far) + 1
    max_attempts = 1 + RETRIES

    if passed:
        verdict = "PASS" if attempt_n == 1 else "FLAKY"
    elif total_attempts >= max_attempts:
        verdict = "FAIL"
    else:
        verdict = None  # pending

    _record_attempt(
        out_dir, entry, existing, attempt_n, passed=passed,
        failures=failures, reply_path=str(reply_path) if not passed else None,
        verdict=verdict,
    )

    failed_kinds = ",".join(f["kind"] for f in failures) if failures else ""
    line = f"ASSERT {case_key} attempt={attempt_n} passed={str(passed).lower()}"
    if failed_kinds:
        line += f" failed={failed_kinds}"
    print(line)

    return 0 if passed else 1


def _record_attempt(
    out_dir: Path,
    entry: dict,
    existing: dict | None,
    attempt_n: int,
    passed: bool,
    failures: list[dict],
    reply_path: str | None,
    verdict: str | None = None,
    is_error: bool = False,
) -> None:
    attempt_rec = {
        "n": attempt_n,
        "passed": passed,
        "failed_assertions": failures,
        "reply_path": reply_path,
        "exit_code": 0 if passed else (2 if is_error else 1),
        "duration_s": None,
    }
    if existing:
        record = dict(existing)
        record["attempts"] = existing["attempts"] + [attempt_rec]
    else:
        record = {
            "agent": entry["agent"],
            "case": entry["case"],
            "context_fingerprint": entry.get("context_fingerprint"),
            "verdict": None,
            "attempts": [attempt_rec],
            "model": entry.get("model"),
            "effort": entry.get("effort"),
            "model_source": entry.get("model_source"),
            "duration_s": None,
            "cost_usd": None,
        }

    if verdict is not None:
        record["verdict"] = verdict

    write_journal_entry(out_dir, record)


# ---------------------------------------------------------------------------
# report subcommand
# ---------------------------------------------------------------------------


def cmd_report(args: argparse.Namespace, repo_root: Path) -> int:
    out_dir = Path(args.out_dir)
    manifest_path = out_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"report: manifest not found: {manifest_path}", file=sys.stderr)
        return 2

    manifest = json.loads(manifest_path.read_text())
    journal = load_journal(out_dir)
    strict_flaky = args.strict_flaky

    cases_out: list[dict] = []
    totals = {"pass": 0, "flaky": 0, "fail": 0, "error": 0, "skip": 0}

    # Process manifest cases
    for entry in manifest.get("cases", []):
        key = f"{entry['agent']}/{entry['case']}"
        rec = journal.get(key)
        if rec is None or rec.get("verdict") is None:
            # Missing or unfinished — ERROR
            err_rec = {
                "agent": entry["agent"],
                "case": entry["case"],
                "verdict": "ERROR",
                "attempts": [],
                "model": entry.get("model"),
                "effort": entry.get("effort"),
                "model_source": entry.get("model_source"),
                "duration_s": None,
                "cost_usd": None,
                "context_fingerprint": entry.get("context_fingerprint"),
                "_error_kind": "missing-result",
            }
            cases_out.append(err_rec)
            totals["error"] += 1
        else:
            verdict = rec["verdict"]
            # Chronic-flake promotion: check sibling runs
            if verdict == "FLAKY":
                verdict = _check_chronic_flake(entry["agent"], entry["case"], out_dir, verdict)
                rec = dict(rec)
                rec["verdict"] = verdict

            cases_out.append(rec)
            totals[verdict.lower()] += 1

    # Skips
    skips_out = manifest.get("skips", [])
    totals["skip"] = len(skips_out)

    # Exit code
    exit_code = 0
    if totals["error"] > 0:
        exit_code = 2
    elif totals["fail"] > 0:
        exit_code = 1
    elif strict_flaky and totals["flaky"] > 0:
        exit_code = 1

    run_id = manifest.get("run_id", out_dir.name)
    scope = manifest.get("scope", {"mode": "all", "filters": []})

    report = {
        "run_id": run_id,
        "scope": scope,
        "model_overrides": None,
        "totals": totals,
        "cases": cases_out,
        "skips": skips_out,
        "exit_code": exit_code,
        "meta": {
            "harness_version": HARNESS_VERSION,
            "claude_version": None,
            "concurrency": 4,
            "retries": RETRIES,
            "strict_flaky": strict_flaky,
        },
    }

    report_json_path = out_dir / "report.json"
    report_json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    report_md_path = out_dir / "report.md"
    report_md_path.write_text(_render_report_md(report), encoding="utf-8")

    print(f"report: {report_json_path}")
    return exit_code


def _check_chronic_flake(agent: str, case: str, out_dir: Path, current_verdict: str) -> str:
    """Check if this agent/case has been FLAKY in >=3 consecutive most-recent runs.
    Returns 'FAIL' (with detail note) if chronic, else returns current_verdict unchanged.
    """
    if current_verdict != "FLAKY":
        return current_verdict

    parent = out_dir.parent
    if not parent.exists():
        return current_verdict

    # Sorted sibling RUN dirs only (name = run-id timestamp). A custom
    # --out-dir may live beside unrelated directories; never read those.
    run_id_re = re.compile(r"^\d{8}T\d{6}Z$")
    sibling_dirs = sorted(
        [
            d
            for d in parent.iterdir()
            if d.is_dir() and d != out_dir and run_id_re.match(d.name)
        ],
        key=lambda d: d.name,
    )
    # Include current run — check the 3 most recent (excluding current, then add current)
    recent = sibling_dirs[-2:] if len(sibling_dirs) >= 2 else sibling_dirs
    consecutive_flaky = 1  # current run is FLAKY

    for sib in reversed(recent):
        sib_report = sib / "report.json"
        if not sib_report.exists():
            break
        try:
            sib_data = json.loads(sib_report.read_text())
        except Exception:
            break
        found_verdict = None
        for c in sib_data.get("cases", []):
            if c.get("agent") == agent and c.get("case") == case:
                found_verdict = c.get("verdict")
                break
        if found_verdict == "FLAKY":
            consecutive_flaky += 1
        else:
            break

    if consecutive_flaky >= 3:
        return "FAIL"
    return current_verdict


def _render_report_md(report: dict) -> str:
    totals = report["totals"]
    lines = [
        f"# Conformance Report — {report['run_id']}",
        "",
        f"**pass**: {totals['pass']} | **flaky**: {totals['flaky']} | "
        f"**fail**: {totals['fail']} | **error**: {totals['error']} | "
        f"**skip**: {totals['skip']}",
        "",
        "## Results",
        "",
        "| agent | case | verdict | model(source) | words | duration | cost |",
        "|-------|------|---------|---------------|-------|----------|------|",
    ]
    for c in report.get("cases", []):
        model_src = c.get("model") or "—"
        if c.get("model_source"):
            model_src += f"({c['model_source']})"
        words_val = "—"
        dur = f"{c.get('duration_s', 0) or 0:.1f}s" if c.get("duration_s") else "—"
        cost = f"${c.get('cost_usd', 0) or 0:.4f}" if c.get("cost_usd") else "—"
        lines.append(
            f"| {c.get('agent','')} | {c.get('case','')} | {c.get('verdict','')} "
            f"| {model_src} | {words_val} | {dur} | {cost} |"
        )

    # Failures section
    failures = [c for c in report.get("cases", []) if c.get("verdict") in ("FAIL", "ERROR", "FLAKY")]
    if failures:
        lines += ["", "## Failures", ""]
        for c in failures:
            lines.append(f"### {c.get('agent')}/{c.get('case')} — {c.get('verdict')}")
            err_kind = c.get("_error_kind")
            if err_kind:
                lines.append(f"- error: {err_kind}")
            for att in c.get("attempts", []):
                if att.get("failed_assertions"):
                    lines.append(f"- attempt {att['n']}:")
                    for fa in att["failed_assertions"]:
                        lines.append(f"  - `{fa['kind']}`: {fa.get('detail', '')}")
                    if att.get("reply_path"):
                        lines.append(f"  - reply: `{att['reply_path']}`")
            lines.append("")

    # Skips section
    skips = report.get("skips", [])
    if skips:
        lines += ["## Skips", "", "| agent | reason |", "|-------|--------|"]
        for s in skips:
            lines.append(f"| {s.get('agent','')} | {s.get('reason','')} |")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Agent conformance harness — deterministic engine.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    # check
    sub.add_parser("check", help="Check coverage + contract consistency (no LLM)")

    # stage
    stage_p = sub.add_parser("stage", help="Stage sandboxes and emit run manifest")
    sel = stage_p.add_mutually_exclusive_group()
    sel.add_argument("--all", action="store_true", help="Stage all agents")
    sel.add_argument("--agent", nargs="+", action="extend", metavar="NAME", help="Stage specific agents by name (repeatable)")
    sel.add_argument("--package", nargs="+", action="extend", metavar="PKG", help="Stage agents from specific packages (repeatable)")
    stage_p.add_argument("--out-dir", metavar="PATH", help="Output directory (default: .conformance-runs/<ts>/)")

    # assert
    assert_p = sub.add_parser("assert", help="Assert one captured reply against its case")
    assert_p.add_argument("--manifest", required=True, metavar="PATH")
    assert_p.add_argument("--case", required=True, metavar="AGENT/CASE")
    assert_p.add_argument("--attempt", type=int, metavar="N", default=None)

    # report
    report_p = sub.add_parser("report", help="Assemble report from journal")
    report_p.add_argument("--out-dir", required=True, metavar="PATH")
    report_p.add_argument("--strict-flaky", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        repo_root = find_repo_root()
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if args.subcommand == "check":
        return cmd_check(args, repo_root)
    if args.subcommand == "stage":
        return cmd_stage(args, repo_root)
    if args.subcommand == "assert":
        return cmd_assert(args, repo_root)
    if args.subcommand == "report":
        return cmd_report(args, repo_root)

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
