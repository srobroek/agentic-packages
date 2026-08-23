#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["hypothesis>=6.100"]
# ///
"""Adversarial fuzzer for the bead-as-brief enforcement engine (spec 002 N7).

Goal: BREAK the evaluator + hooks. Two layers:
  1. Property-based (hypothesis): arbitrary/garbage payloads must NEVER crash
     the scripts and must ALWAYS emit valid JSON (fail-open invariant).
  2. Hand-crafted attack vectors: authority-bypass attempts, injection, unicode,
     huge payloads, malformed rules refs, prototype-pollution-style keys — each
     must produce the SAFE verdict (block on violation, allow on fail-open),
     never a crash or a wrong allow.

Any script that crashes, hangs, emits non-JSON, or lets an authority violation
through is a finding. Findings are printed and the run exits non-zero.
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# Rules live at the package's .apm/rules directory.
RULES = os.path.abspath(os.path.join(HERE, "..", ".apm", "rules"))
EVAL = os.path.join(HERE, "rules-eval.py")
DENY = os.path.join(HERE, "orchestrator-claim-deny.py")
START = os.path.join(HERE, "contract-start.py")
DS = os.path.join(RULES, "domain-specialist.rules.json")

findings = []
runs = 0


def invoke(script, payload_str, env=None):
    """Run a hook script; return (stdout, returncode, crashed?)."""
    global runs
    runs += 1
    try:
        p = subprocess.run(
            ["uv", "run", "--quiet", script],
            input=payload_str,
            capture_output=True,
            text=True,
            timeout=45,
            env={**os.environ, "RULES_DIR": RULES, **(env or {})},
        )
        return p.stdout, p.returncode, False
    except subprocess.TimeoutExpired:
        return "", -1, True
    except Exception as e:
        return f"EXC {e}", -1, True


def must_be_valid_json_or_empty(script, out, rc, crashed, label):
    if crashed:
        findings.append(f"[{label}] CRASH/HANG on script {os.path.basename(script)}")
        return None
    if rc != 0:
        findings.append(
            f"[{label}] non-zero exit {rc} from {os.path.basename(script)}: {out[:120]}"
        )
    s = out.strip()
    if s == "":
        findings.append(
            f"[{label}] EMPTY stdout (hooks must emit JSON) from {os.path.basename(script)}"
        )
        return None
    try:
        return json.loads(s)
    except Exception:
        findings.append(f"[{label}] NON-JSON stdout from {os.path.basename(script)}: {s[:120]}")
        return None


# ---- Layer 1: property-based garbage -------------------------------------
def prop_fuzz():
    try:
        from hypothesis import HealthCheck, given, settings
        from hypothesis import strategies as st
    except Exception as e:
        findings.append(f"[setup] hypothesis import failed: {e}")
        return

    # Arbitrary JSON-ish payloads.
    json_vals = st.recursive(
        st.none()
        | st.booleans()
        | st.integers()
        | st.floats(allow_nan=True, allow_infinity=True)
        | st.text(),
        lambda children: (
            st.lists(children, max_size=5)
            | st.dictionaries(st.text(max_size=8), children, max_size=5)
        ),
        max_leaves=15,
    )

    @settings(max_examples=250, deadline=None, suppress_health_check=list(HealthCheck))
    @given(payload=st.dictionaries(st.text(max_size=12), json_vals, max_size=8))
    def evaluator_never_crashes(payload):
        out, rc, crashed = invoke(EVAL, json.dumps(payload))
        must_be_valid_json_or_empty(EVAL, out, rc, crashed, "prop-eval")

    @settings(max_examples=150, deadline=None, suppress_health_check=list(HealthCheck))
    @given(cmd=st.text(max_size=60))
    def claim_deny_never_crashes(cmd):
        out, rc, crashed = invoke(
            DENY, json.dumps({"tool_input": {"command": cmd}}), env={"ORCHESTRATE_RUN": "1"}
        )
        must_be_valid_json_or_empty(DENY, out, rc, crashed, "prop-deny")

    evaluator_never_crashes()
    claim_deny_never_crashes()


# ---- Layer 2: hand-crafted attack vectors --------------------------------
def attack_vectors():
    # A complete coder bead but trying to sneak a forbidden state.
    def bead(**kw):
        b = {"labels": [], "metadata": {}, "comments": []}
        b.update(kw)
        return b

    def ev(bead_obj, agent="builder", rf=DS):
        p = {"agent_type": agent, "_bead": bead_obj}
        if rf:
            p["_rules_file"] = rf
        out, rc, crashed = invoke(EVAL, json.dumps(p))
        return must_be_valid_json_or_empty(EVAL, out, rc, crashed, "attack")

    def is_block(v):
        return isinstance(v, dict) and v.get("decision") == "block"

    # 1. Authority bypass: closed status must ALWAYS block, even fully complete.
    v = ev(
        bead(
            id="a1",
            status="closed",
            labels=["agent:reviewer"],
            metadata={"execution_kind": "git", "branch": "b", "push": "s"},
            comments=[{"text": "REPORTED done"}],
        )
    )
    if not is_block(v):
        findings.append("[attack] closed-status authority violation NOT blocked (bypass!)")

    # 2. merge_sha written by coder must block.
    v = ev(
        bead(
            id="a2",
            status="in_progress",
            labels=["agent:reviewer"],
            metadata={"execution_kind": "git", "branch": "b", "push": "s", "merge_sha": "x"},
            comments=[{"text": "REPORTED"}],
        )
    )
    if not is_block(v):
        findings.append("[attack] merge_sha authority violation NOT blocked (bypass!)")

    # 3. Fake REPORTED via a comment that only CONTAINS the word, not leading verb.
    v = ev(
        bead(
            id="a3",
            status="in_progress",
            labels=["agent:reviewer"],
            metadata={"execution_kind": "git", "branch": "b", "push": "s"},
            comments=[{"text": "i have not REPORTED anything yet"}],
        )
    )
    if not is_block(v):
        findings.append(
            "[attack] non-leading 'REPORTED' token satisfied completion (verb-parse bypass!)"
        )

    # 4. Label injection: an evil label that merely contains agent: mid-string.
    v = ev(
        bead(
            id="a4",
            status="in_progress",
            labels=["not-an-agent:reviewer-really"],
            metadata={"execution_kind": "git", "branch": "b", "push": "s"},
            comments=[{"text": "REPORTED"}],
        )
    )
    # ^agent: is anchored, so this label should NOT satisfy handoff -> block.
    if not is_block(v):
        findings.append(
            "[attack] mid-string 'agent:' label satisfied ^agent: anchor (regex bypass!)"
        )

    # 5. Unicode / emoji in comment verb position.
    v = ev(
        bead(
            id="a5",
            status="in_progress",
            labels=["agent:reviewer"],
            metadata={"execution_kind": "git", "branch": "b", "push": "s"},
            comments=[{"text": "🚀 REPORTED done"}],
        )
    )
    # leading token is the emoji, not REPORTED -> should block.
    if not is_block(v):
        findings.append("[attack] emoji-prefixed comment satisfied REPORTED verb (should block)")

    # 6. Huge payload (100k comments) must not hang/crash.
    big = bead(
        id="a6",
        status="in_progress",
        labels=["agent:reviewer"],
        metadata={"execution_kind": "git", "branch": "b", "push": "s"},
        comments=[{"text": f"CHECKPOINT {i}"} for i in range(20000)] + [{"text": "REPORTED"}],
    )
    v = ev(big)
    if v is None:
        findings.append("[attack] huge-payload broke the evaluator")

    # 7. metadata with a null/None push must NOT count as present.
    v = ev(
        bead(
            id="a7",
            status="in_progress",
            labels=["agent:reviewer"],
            metadata={"execution_kind": "git", "branch": "b", "push": None},
            comments=[{"text": "REPORTED"}],
        )
    )
    if not is_block(v):
        findings.append("[attack] null push metadata counted as present (should block)")

    # 8. Rules-file path traversal / nonexistent -> fail open (allow), not crash.
    v = ev(bead(id="a8", status="in_progress"), rf="/nonexistent/../../etc/passwd.rules.json")
    if v is None:
        findings.append("[attack] bad rules-file path crashed instead of failing open")

    # 9. Escape hatch cannot be spoofed: blocked status but the FAILED token is mid-comment.
    v = ev(
        bead(
            id="a9",
            status="blocked",
            metadata={"execution_kind": "git"},
            comments=[{"text": "everything is fine not FAILED at all"}],
        )
    )
    if not is_block(v):
        findings.append("[attack] mid-string FAILED spoofed the escape hatch (should block)")


def main():
    if os.environ.get("FUZZ_ATTACK_ONLY"):
        print("=== hand-crafted attack vectors (property layer skipped) ===")
        attack_vectors()
        print(f"  ran {runs} attack invocations")
        if findings:
            print(f"FUZZ FINDINGS ({len(findings)}):")
            for f in findings:
                print("  -", f)
            sys.exit(1)
        print(f"fuzz(attack-only): no findings across {runs} invocations — engine held.")
        sys.exit(0)
    print("=== property-based fuzz (hypothesis) ===")
    prop_fuzz()
    print(f"  ran ~{runs} property invocations")
    print("=== hand-crafted attack vectors ===")
    before = runs
    attack_vectors()
    print(f"  ran {runs - before} attack invocations")
    print()
    if findings:
        print(f"FUZZ FINDINGS ({len(findings)}):")
        for f in findings:
            print("  -", f)
        sys.exit(1)
    print(f"fuzz: no findings across {runs} invocations — engine held.")
    sys.exit(0)


if __name__ == "__main__":
    main()
