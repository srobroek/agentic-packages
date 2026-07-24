"""Deterministic pytest suite for the conformance engine.

All tests are LLM-free. They build synthetic agent files + fixtures under
tmp_path and point the engine's discovery/fixture functions at those roots.
No network calls.

Run:
  uv run --with pytest --with pyyaml pytest -q \
    packages/agent-conformance/scripts/test_conformance.py
"""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

# Make conformance.py importable without installing the package.
sys.path.insert(0, str(Path(__file__).parent))
import conformance  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers for building fake repo trees
# ---------------------------------------------------------------------------


def make_agent(
    root: Path,
    package: str,
    name: str,
    body: str,
    frontmatter: str = "",
) -> Path:
    """Write a minimal agent file at packages/<package>/.apm/agents/<name>.agent.md."""
    d = root / "packages" / package / ".apm" / "agents"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{name}.agent.md"
    if frontmatter:
        path.write_text(f"---\n{frontmatter}\n---\n{body}")
    else:
        path.write_text(body)
    return path


def make_case(
    root: Path,
    agent_name: str,
    slug: str,
    data: dict,
) -> Path:
    """Write fixtures/<agent>/<slug>.yaml under the agent-conformance package."""
    d = root / "packages" / "agent-conformance" / "fixtures" / agent_name
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{slug}.yaml"
    p.write_text(yaml.dump(data))
    return p


def make_skips(root: Path, skips: list[dict]) -> Path:
    d = root / "packages" / "agent-conformance" / "fixtures"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "skips.yaml"
    p.write_text(yaml.dump({"skips": skips}))
    return p


def make_manifest(out_dir: Path, cases: list[dict], skips: list | None = None) -> Path:
    manifest = {"run_id": out_dir.name, "cases": cases, "skips": skips or []}
    p = out_dir / "manifest.json"
    p.write_text(json.dumps(manifest))
    return p


# ---------------------------------------------------------------------------
# Contract derivation tests
# ---------------------------------------------------------------------------


class TestDeriveFirstLine:
    """first_line_pattern derivation from ## Output section."""

    def _contract(self, body: str) -> dict:
        agent = {"name": "test", "model": None, "effort": None, "tools": None, "body": body}
        return conformance.derive_contract(agent)

    def test_l1_verdict_line(self):
        body = "## Output\nL1 VERDICT: APPROVE|CHANGES|ESCALATE — one sentence why.\nCAP 100w.\n"
        c = self._contract(body)
        assert c["first_line_pattern"] is not None
        import re
        assert re.search(c["first_line_pattern"], "VERDICT: APPROVE — looks good")

    def test_l1_verdict_reject_wrong_verb(self):
        body = "## Output\nL1 VERDICT: APPROVE|CHANGES|ESCALATE — one sentence why.\nCAP 100w.\n"
        c = self._contract(body)
        import re
        assert not re.search(c["first_line_pattern"], "verdict: approve")

    def test_structured_line(self):
        """LINT-GUARD style: first content line with a CAPS_ENUM."""
        body = (
            "## Output\n"
            "LINT-GUARD <node> verdict=PASS|WARN|BLOCK items=<N>\n"
            "CAP 90 words clean, 180 words with findings.\n"
        )
        c = self._contract(body)
        assert c["first_line_pattern"] is not None
        import re
        assert re.search(c["first_line_pattern"], "LINT-GUARD n42 verdict=PASS items=3")

    def test_no_output_section(self):
        body = "Some body without output section.\n"
        c = self._contract(body)
        assert c["first_line_pattern"] is None

    def test_prose_cap_only(self):
        """≤ N words style produces None for first_line."""
        body = "## Output\nAnswer queries in ≤ 100 words.\nNever reprint.\n"
        c = self._contract(body)
        assert c["first_line_pattern"] is None

    def test_caps_derivation_dual(self):
        body = "## Output\nL1 VERDICT: PASS|FAIL\nCAP 100w clean · 180w with findings.\n"
        c = self._contract(body)
        assert c["caps"]["clean"] == 100
        assert c["caps"]["findings"] == 180
        assert not c["caps"]["uncapped"]

    def test_caps_derivation_prose_le(self):
        """≤ N words form."""
        body = "## Output\nAnswer in ≤ 100 words.\n"
        c = self._contract(body)
        assert c["caps"]["clean"] == 100
        assert c["caps"]["findings"] == 100

    def test_caps_derivation_dual_comma_style(self):
        """CAP 90 words clean, 180 words with findings."""
        body = "## Output\nCAP 90 words clean, 180 words with findings.\n"
        c = self._contract(body)
        assert c["caps"]["clean"] == 90
        assert c["caps"]["findings"] == 180

    def test_caps_derivation_uncapped(self):
        body = "## Output\nCAP uncapped.\n"
        c = self._contract(body)
        assert c["caps"]["uncapped"] is True

    def test_caps_none_when_absent(self):
        body = "## Output\nSome prose output.\n"
        c = self._contract(body)
        assert c["caps"]["clean"] is None
        assert c["caps"]["findings"] is None
        assert not c["caps"]["uncapped"]

    def test_no_reprint_true(self):
        body = "## Output\nL1 FOO|BAR\nMUST Never reprint code or diffs.\n"
        c = self._contract(body)
        assert c["no_reprint"] is True

    def test_no_reprint_false(self):
        body = "## Output\nL1 FOO|BAR\nCAP 100w.\n"
        c = self._contract(body)
        assert c["no_reprint"] is False


# ---------------------------------------------------------------------------
# Case validation tests
# ---------------------------------------------------------------------------


class TestCaseValidation:
    def _contract(self, caps_clean=100, caps_findings=180, uncapped=False, first_line=None):
        return {
            "first_line_pattern": first_line,
            "caps": {"clean": caps_clean, "findings": caps_findings, "uncapped": uncapped},
            "no_reprint": True,
        }

    def _good_case(self, **overrides):
        base = {
            "_slug": "case-clean",
            "agent": "myagent",
            "regime": "clean",
            "prompt": "Do something",
            "assert": {"max_words": 100},
        }
        base.update(overrides)
        return base

    def test_good_case_passes(self):
        case = self._good_case()
        viol = conformance.validate_case(case, self._contract(), "myagent")
        assert viol == []

    def test_path_traversal_rejected(self):
        case = self._good_case(
            sandbox={"files": {"../escape.txt": "bad"}}
        )
        viol = conformance.validate_case(case, self._contract(), "myagent")
        assert any("traversal" in v or ".." in v for v in viol)

    def test_absolute_path_rejected(self):
        case = self._good_case(
            sandbox={"files": {"/etc/passwd": "bad"}}
        )
        viol = conformance.validate_case(case, self._contract(), "myagent")
        assert any("absolute" in v for v in viol)

    def test_bad_regex_rejected(self):
        case = self._good_case(
            **{"assert": {"max_words": 100, "first_line": "[invalid"}}
        )
        viol = conformance.validate_case(case, self._contract(), "myagent")
        assert any("invalid regex" in v for v in viol)

    def test_nested_quantifier_rejected(self):
        case = self._good_case(
            **{"assert": {"max_words": 100, "required_patterns": ["(a+)+"]}}
        )
        viol = conformance.validate_case(case, self._contract(), "myagent")
        assert any("nested quantifier" in v for v in viol)

    def test_regime_mismatch_drifts(self):
        """Case max_words doesn't match derived cap for regime."""
        case = self._good_case(
            **{"assert": {"max_words": 999}}  # derived clean=100
        )
        viol = conformance.validate_case(case, self._contract(), "myagent")
        assert any("drifts" in v for v in viol)

    def test_correct_cap_no_drift(self):
        case = self._good_case(**{"assert": {"max_words": 100}})
        viol = conformance.validate_case(case, self._contract(), "myagent")
        assert viol == []

    def test_uncapped_not_checked(self):
        """uncapped regime: max_words=uncapped doesn't fire drift."""
        contract = self._contract(uncapped=True)
        case = self._good_case(**{"assert": {"max_words": "uncapped"}})
        viol = conformance.validate_case(case, contract, "myagent")
        assert viol == []


# ---------------------------------------------------------------------------
# Coverage check tests (cmd_check integration)
# ---------------------------------------------------------------------------


class TestCheckCoverage:
    def test_uncovered_agent_fails(self, tmp_path):
        make_agent(
            tmp_path, "mypkg", "my-agent",
            body="## Output\nL1 VERDICT: PASS|FAIL\nCAP 100w.\nMUST Never reprint.\n",
            frontmatter="name: my-agent\neffort: low",
        )
        make_skips(tmp_path, [])
        # No cases, no skips → should fail with violation
        args = _fake_args("check")
        viol_lines = []
        # Capture stdout
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = conformance.cmd_check(args, tmp_path)
        assert rc == 1
        output = buf.getvalue()
        assert "my-agent" in output
        assert "no cases" in output

    def test_skip_entry_satisfies_coverage(self, tmp_path):
        make_agent(
            tmp_path, "mypkg", "my-agent",
            body="## Output\nL1 VERDICT: PASS|FAIL\nCAP 100w.\nMUST Never reprint.\n",
            frontmatter="name: my-agent\neffort: low",
        )
        make_skips(tmp_path, [{"agent": "my-agent", "reason": "requires live env that is infeasible for v1"}])
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = conformance.cmd_check(args=_fake_args("check"), repo_root=tmp_path)
        assert rc == 0

    def test_stale_skip_fails(self, tmp_path):
        """Skip entry for nonexistent agent is a violation."""
        make_agent(
            tmp_path, "mypkg", "real-agent",
            body="## Output\nL1 VERDICT: PASS|FAIL\nCAP 100w.\nMUST Never reprint.\n",
            frontmatter="name: real-agent\neffort: low",
        )
        make_skips(tmp_path, [{"agent": "ghost-agent", "reason": "this agent does not exist at all"}])
        make_case(tmp_path, "real-agent", "case-clean", {
            "agent": "real-agent", "regime": "clean",
            "prompt": "hello", "assert": {"max_words": 100},
        })
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = conformance.cmd_check(args=_fake_args("check"), repo_root=tmp_path)
        assert rc == 1

    def test_stale_case_dir_fails(self, tmp_path):
        """Case directory for nonexistent agent is a violation."""
        make_agent(
            tmp_path, "mypkg", "real-agent",
            body="## Output\nL1 VERDICT: PASS|FAIL\nCAP 100w.\nMUST Never reprint.\n",
            frontmatter="name: real-agent\neffort: low",
        )
        make_skips(tmp_path, [])
        make_case(tmp_path, "real-agent", "case-clean", {
            "agent": "real-agent", "regime": "clean",
            "prompt": "hello", "assert": {"max_words": 100},
        })
        # Extra stale dir
        stale_dir = tmp_path / "packages" / "agent-conformance" / "fixtures" / "ghost-agent"
        stale_dir.mkdir(parents=True)
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = conformance.cmd_check(args=_fake_args("check"), repo_root=tmp_path)
        assert rc == 1

    def test_drift_fails_check(self, tmp_path):
        """Case max_words != derived cap triggers drift violation in check."""
        make_agent(
            tmp_path, "mypkg", "capped-agent",
            body="## Output\nL1 VERDICT: PASS|FAIL\nCAP 100w clean · 180w with findings.\nMUST Never reprint.\n",
            frontmatter="name: capped-agent\neffort: low",
        )
        make_skips(tmp_path, [])
        make_case(tmp_path, "capped-agent", "case-clean", {
            "agent": "capped-agent", "regime": "clean",
            "prompt": "hello", "assert": {"max_words": 999},  # wrong
        })
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = conformance.cmd_check(args=_fake_args("check"), repo_root=tmp_path)
        assert rc == 1


# ---------------------------------------------------------------------------
# Assertion engine tests
# ---------------------------------------------------------------------------


class TestAssertionEngine:
    def _entry(self, **kwargs) -> dict:
        """Build a minimal manifest entry for testing _run_assertions."""
        base = {
            "agent": "test-agent",
            "case": "case-clean",
            "regime": "clean",
            "sandbox_path": "",
            "reply_path": "",
            "model": None,
            "effort": None,
            "model_source": "inherited-session",
            "timeout_s": 120,
            "max_reply_bytes": 65536,
            "assert": {},
            "_fixture_content": "",
        }
        base.update(kwargs)
        return base

    def test_first_line_pass(self):
        entry = self._entry(**{"assert": {"first_line": r"^VERDICT: (APPROVE|CHANGES)\b", "max_words": 100}})
        reply = "VERDICT: APPROVE — looks good\n" + "word " * 10
        failures = conformance._run_assertions(entry, reply)
        assert not any(f["kind"] == "first_line" for f in failures)

    def test_first_line_fail(self):
        entry = self._entry(**{"assert": {"first_line": r"^VERDICT: (APPROVE|CHANGES)\b", "max_words": 100}})
        reply = "verdict: approve\n" + "word " * 10  # lowercase: won't match
        failures = conformance._run_assertions(entry, reply)
        assert any(f["kind"] == "first_line" for f in failures)

    def test_word_cap_exact_boundary_pass(self):
        """Exactly at cap: should pass."""
        entry = self._entry(**{"assert": {"max_words": 10}})
        reply = " ".join(["w"] * 10) + "\n"  # 10 words in first line (≥ 50 bytes when padded)
        # Pad to pass plausibility floor
        reply = "first non-empty line\n" + reply
        failures = conformance._run_assertions(entry, reply)
        assert not any(f["kind"] == "max_words" for f in failures)

    def test_word_cap_over_fails(self):
        """One word over cap: should fail."""
        entry = self._entry(**{"assert": {"max_words": 5}})
        reply = "one two three four five six"  # 6 words
        # Make sure it passes plausibility floor
        reply = reply + " " * 100
        failures = conformance._run_assertions(entry, reply)
        assert any(f["kind"] == "max_words" for f in failures)

    def test_no_reprint_exact_boundary_159_passes(self):
        """159-char segment: must NOT fire."""
        segment = "a" * 159
        entry = self._entry(
            _fixture_content=segment,
            **{"assert": {"no_reprint": True, "max_words": 1000}},
        )
        # Put the segment verbatim in the reply
        reply = segment + " extra words to meet length" + "x " * 20
        failures = conformance._run_assertions(entry, reply)
        assert not any(f["kind"] == "no_reprint" for f in failures)

    def test_no_reprint_160_fails(self):
        """160-char verbatim segment: must fire."""
        segment = "b" * 160
        entry = self._entry(
            _fixture_content=segment,
            **{"assert": {"no_reprint": True, "max_words": 1000}},
        )
        reply = segment + " more words " + "x " * 20
        failures = conformance._run_assertions(entry, reply)
        assert any(f["kind"] == "no_reprint" for f in failures)

    def test_no_reprint_short_fragments_do_not_fire(self):
        """Many short separate fixture fragments cited legitimately should not fire."""
        # Fixture has many short lines
        fixture = "\n".join([f"line {i}: result here" for i in range(20)])
        # Reply only cites one or two of them (each << 160 chars)
        entry = self._entry(
            _fixture_content=fixture,
            **{"assert": {"no_reprint": True, "max_words": 1000}},
        )
        reply = "line 3: result here\nline 7: result here\nSummary: two issues found.\n" + "x " * 30
        failures = conformance._run_assertions(entry, reply)
        assert not any(f["kind"] == "no_reprint" for f in failures)

    def test_required_pattern_pass(self):
        entry = self._entry(**{"assert": {"required_patterns": [r"PASS"], "max_words": 1000}})
        reply = "Result: PASS\n" + "x " * 30
        failures = conformance._run_assertions(entry, reply)
        assert not any(f["kind"] == "required_pattern" for f in failures)

    def test_required_pattern_fail(self):
        entry = self._entry(**{"assert": {"required_patterns": [r"PASS"], "max_words": 1000}})
        reply = "Result: FAIL\n" + "x " * 30
        failures = conformance._run_assertions(entry, reply)
        assert any(f["kind"] == "required_pattern" for f in failures)

    def test_forbidden_pattern_fires(self):
        entry = self._entry(**{"assert": {"forbidden_patterns": [r"^Findings"], "max_words": 1000}})
        reply = "Findings\nsome details\n" + "x " * 30
        failures = conformance._run_assertions(entry, reply)
        assert any(f["kind"] == "forbidden_pattern" for f in failures)

    def test_forbidden_pattern_absent_passes(self):
        entry = self._entry(**{"assert": {"forbidden_patterns": [r"^Findings"], "max_words": 1000}})
        reply = "Result: OK\n" + "x " * 30
        failures = conformance._run_assertions(entry, reply)
        assert not any(f["kind"] == "forbidden_pattern" for f in failures)

    def test_plausibility_floor_error(self):
        """Reply < 50 bytes triggers implausible-reply regardless of assertions."""
        entry = self._entry(**{"assert": {"max_words": 100}})
        reply = "ok"  # 2 bytes
        failures = conformance._run_assertions(entry, reply)
        assert any(f["kind"] == "implausible-reply" for f in failures)

    def test_artifact_pass(self, tmp_path):
        """Artifact assertion: file exists and line matches."""
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        (sandbox / "output.txt").write_text("VERDICT: PASS\n")
        entry = self._entry(
            sandbox_path=str(sandbox),
            **{"assert": {
                "artifacts": [{"path": "output.txt", "line_pattern": r"VERDICT: PASS"}],
                "max_words": 1000,
            }},
        )
        reply = "Done.\n" + "x " * 30
        failures = conformance._run_assertions(entry, reply)
        assert not any(f["kind"] == "artifact" for f in failures)

    def test_artifact_missing_fails(self, tmp_path):
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        entry = self._entry(
            sandbox_path=str(sandbox),
            **{"assert": {
                "artifacts": [{"path": "missing.txt", "line_pattern": r"PASS"}],
                "max_words": 1000,
            }},
        )
        reply = "Done.\n" + "x " * 30
        failures = conformance._run_assertions(entry, reply)
        assert any(f["kind"] == "artifact" for f in failures)


# ---------------------------------------------------------------------------
# Redaction tests
# ---------------------------------------------------------------------------


class TestRedaction:
    def test_sk_token_redacted(self):
        reply = "Here is the key: sk-abcdefghijklmnopqrstuvwxyz1234567890"
        redacted = conformance._redact_reply(reply)
        assert "sk-" not in redacted
        assert "[REDACTED]" in redacted

    def test_akia_token_redacted(self):
        reply = "AWS key: AKIAIOSFODNN7EXAMPLE"
        redacted = conformance._redact_reply(reply)
        assert "AKIAIOSFODNN7EXAMPLE" not in redacted

    def test_normal_text_unchanged(self):
        reply = "Result: PASS. No findings."
        redacted = conformance._redact_reply(reply)
        assert "Result: PASS" in redacted


# ---------------------------------------------------------------------------
# Journal and report tests
# ---------------------------------------------------------------------------


class TestJournalReport:
    def _make_entry(self, agent="test-agent", case="case-clean", regime="clean"):
        return {
            "agent": agent, "case": case, "regime": regime,
            "prompt": "hello", "sandbox_path": "", "reply_path": f"replies/{agent}/{case}-attempt1.txt",
            "model": None, "effort": None, "model_source": "inherited-session",
            "timeout_s": 120, "max_reply_bytes": 65536, "budget_usd": 1.0,
            "context_fingerprint": "abc123",
            "assert": {"max_words": 100},
            "_fixture_content": "",
        }

    def test_missing_result_becomes_error(self, tmp_path):
        """Manifest case with no journal entry → ERROR missing-result in report."""
        out_dir = tmp_path / "run1"
        out_dir.mkdir()
        make_manifest(out_dir, [self._make_entry()])
        args = _fake_args("report", out_dir=str(out_dir))
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = conformance.cmd_report(args, tmp_path)
        assert rc == 2
        report = json.loads((out_dir / "report.json").read_text())
        assert report["totals"]["error"] == 1

    def test_exit_code_all_pass(self, tmp_path):
        out_dir = tmp_path / "run1"
        out_dir.mkdir()
        entry = self._make_entry()
        make_manifest(out_dir, [entry])
        # Write a passing journal entry
        record = {
            "agent": "test-agent", "case": "case-clean",
            "verdict": "PASS", "attempts": [{"n": 1, "passed": True, "failed_assertions": [],
                                              "reply_path": None, "exit_code": 0, "duration_s": None}],
            "model": None, "effort": None, "model_source": "inherited-session",
            "duration_s": None, "cost_usd": None, "context_fingerprint": "abc123",
        }
        (out_dir / "journal.jsonl").write_text(json.dumps(record) + "\n")
        args = _fake_args("report", out_dir=str(out_dir))
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = conformance.cmd_report(args, tmp_path)
        assert rc == 0

    def test_exit_code_fail(self, tmp_path):
        out_dir = tmp_path / "run1"
        out_dir.mkdir()
        entry = self._make_entry()
        make_manifest(out_dir, [entry])
        record = {
            "agent": "test-agent", "case": "case-clean",
            "verdict": "FAIL",
            "attempts": [{"n": 1, "passed": False, "failed_assertions": [{"kind": "first_line", "detail": "x"}],
                          "reply_path": "replies/test-agent/case-clean-attempt1.txt", "exit_code": 1, "duration_s": None}],
            "model": None, "effort": None, "model_source": "inherited-session",
            "duration_s": None, "cost_usd": None, "context_fingerprint": "abc123",
        }
        (out_dir / "journal.jsonl").write_text(json.dumps(record) + "\n")
        args = _fake_args("report", out_dir=str(out_dir))
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = conformance.cmd_report(args, tmp_path)
        assert rc == 1

    def test_strict_flaky_flips_flaky(self, tmp_path):
        """--strict-flaky: FLAKY counts as failure → exit 1."""
        out_dir = tmp_path / "run1"
        out_dir.mkdir()
        entry = self._make_entry()
        make_manifest(out_dir, [entry])
        record = {
            "agent": "test-agent", "case": "case-clean",
            "verdict": "FLAKY",
            "attempts": [{"n": 1, "passed": False, "failed_assertions": [], "reply_path": None, "exit_code": 1, "duration_s": None},
                         {"n": 2, "passed": True, "failed_assertions": [], "reply_path": None, "exit_code": 0, "duration_s": None}],
            "model": None, "effort": None, "model_source": "inherited-session",
            "duration_s": None, "cost_usd": None, "context_fingerprint": "abc123",
        }
        (out_dir / "journal.jsonl").write_text(json.dumps(record) + "\n")
        args = _fake_args("report", out_dir=str(out_dir), strict_flaky=True)
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = conformance.cmd_report(args, tmp_path)
        assert rc == 1

    def test_chronic_flake_promotes_on_third(self, tmp_path):
        """Three consecutive FLAKY runs → FAIL via chronic-flake promotion."""
        parent = tmp_path / ".conformance-runs"
        parent.mkdir()

        def _make_run(name: str, verdict: str) -> Path:
            d = parent / name
            d.mkdir()
            entry = {
                "agent": "flaky-agent", "case": "case-clean", "regime": "clean",
                "prompt": "x", "sandbox_path": "", "reply_path": f"replies/flaky-agent/case-clean-attempt1.txt",
                "model": None, "effort": None, "model_source": "inherited-session",
                "timeout_s": 120, "max_reply_bytes": 65536, "budget_usd": 1.0,
                "context_fingerprint": "abc",
                "assert": {"max_words": 100},
                "_fixture_content": "",
            }
            make_manifest(d, [entry])
            record = {
                "agent": "flaky-agent", "case": "case-clean",
                "verdict": verdict,
                "attempts": [],
                "model": None, "effort": None, "model_source": "inherited-session",
                "duration_s": None, "cost_usd": None, "context_fingerprint": "abc",
            }
            (d / "journal.jsonl").write_text(json.dumps(record) + "\n")
            # Write a prior report.json for sibling detection
            prior_report = {
                "run_id": name, "scope": {}, "model_overrides": None,
                "totals": {}, "cases": [record], "skips": [], "exit_code": 0,
                "meta": {},
            }
            (d / "report.json").write_text(json.dumps(prior_report))
            return d

        _make_run("run1", "FLAKY")
        _make_run("run2", "FLAKY")
        run3 = _make_run("run3", "FLAKY")

        args = _fake_args("report", out_dir=str(run3))
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = conformance.cmd_report(args, tmp_path)

        report = json.loads((run3 / "report.json").read_text())
        flaky_agent_case = next(
            (c for c in report["cases"] if c["agent"] == "flaky-agent"), None
        )
        assert flaky_agent_case is not None
        assert flaky_agent_case["verdict"] == "FAIL"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_args(subcommand: str, **kwargs) -> object:
    """Build a minimal argparse.Namespace for testing."""
    import argparse
    ns = argparse.Namespace()
    ns.subcommand = subcommand
    # Defaults
    ns.out_dir = kwargs.get("out_dir", None)
    ns.strict_flaky = kwargs.get("strict_flaky", False)
    ns.manifest = kwargs.get("manifest", None)
    ns.case = kwargs.get("case", None)
    ns.attempt = kwargs.get("attempt", None)
    ns.all = kwargs.get("all", True)
    ns.agent = kwargs.get("agent", None)
    ns.package = kwargs.get("package", None)
    return ns
