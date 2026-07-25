#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Conformance suite for rules-eval.py (spec 002 SC-002).

Fixture-driven: no bd/live state. Each case feeds a synthetic payload
(_bead + _rules_file) to the evaluator as a subprocess and asserts the verdict.
Exits non-zero on any failure.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = os.path.join(HERE, "rules-eval.py")
RULES = os.path.abspath(os.path.join(HERE, "..", ".apm", "rules"))
DS = os.path.join(RULES, "domain-specialist.rules.json")

passed = 0
failed = 0


def run(name, want, bead, agent_type="domain-specialist", rules_file=DS):
    global passed, failed
    payload = {"agent_type": agent_type, "_bead": bead}
    if rules_file:
        payload["_rules_file"] = rules_file
    if agent_type is None:
        payload = bead  # raw-payload cases
    proc = subprocess.run(["uv", "run", "--quiet", EVAL],
                          input=json.dumps(payload), capture_output=True, text=True,
                          env={**os.environ, "RULES_DIR": RULES})
    try:
        out = json.loads(proc.stdout or "{}")
    except Exception:
        out = {}
    verdict = "block" if out.get("decision") == "block" else "allow"
    ok = verdict == want
    if ok:
        passed += 1
        print(f"  ok   {name:<42} -> {verdict}")
    else:
        failed += 1
        print(f"  FAIL {name:<42} -> got {verdict} want {want}\n       out: {proc.stdout.strip()}")


def bead(**kw):
    b = {"labels": [], "metadata": {}, "comments": []}
    b.update(kw)
    return b


# complete git node -> allow
run("git complete", "allow", bead(id="t1", status="in_progress",
    labels=["orc-node", "agent:reviewer"],
    metadata={"execution_kind": "git", "branch": "node-t1", "push": "abc123"},
    comments=[{"text": "BRIEF do the thing"}, {"text": "REPORTED done, verified"}]))

run("git missing push", "block", bead(id="t2", status="in_progress",
    labels=["agent:reviewer"], metadata={"execution_kind": "git", "branch": "n"},
    comments=[{"text": "REPORTED done"}]))

run("git missing handoff label", "block", bead(id="t3", status="in_progress",
    labels=["orc-node"], metadata={"execution_kind": "git", "branch": "n", "push": "s"},
    comments=[{"text": "REPORTED done"}]))

run("git no reported comment", "block", bead(id="t4", status="in_progress",
    labels=["agent:reviewer"], metadata={"execution_kind": "git", "branch": "n", "push": "s"},
    comments=[{"text": "CHECKPOINT step 1"}]))

run("escape blocked+FAILED", "allow", bead(id="t5", status="blocked",
    metadata={"execution_kind": "git"},
    comments=[{"text": "FAILED repo is broken"}]))

run("blocked status no FAILED comment", "block", bead(id="t6", status="blocked",
    metadata={"execution_kind": "git"}, comments=[{"text": "CHECKPOINT partial"}]))

run("authority deny closed", "block", bead(id="t7", status="closed",
    labels=["agent:reviewer"], metadata={"execution_kind": "git", "branch": "n", "push": "s"},
    comments=[{"text": "REPORTED done"}]))

run("authority deny merge_sha", "block", bead(id="t8", status="in_progress",
    labels=["agent:reviewer"],
    metadata={"execution_kind": "git", "branch": "n", "push": "s", "merge_sha": "dead"},
    comments=[{"text": "REPORTED done"}]))

run("artifact complete", "allow", bead(id="t9", status="in_progress",
    labels=["agent:reviewer"],
    metadata={"execution_kind": "artifact", "output_ref": "/run/artifacts/r.md"},
    comments=[{"text": "REPORTED done"}]))

run("artifact missing output_ref", "block", bead(id="t10", status="in_progress",
    labels=["agent:reviewer"], metadata={"execution_kind": "artifact"},
    comments=[{"text": "REPORTED done"}]))

run("bounce at max_attempts", "allow", bead(id="t11", status="in_progress",
    metadata={"execution_kind": "git", "stop_attempts": 2},
    comments=[{"text": "CHECKPOINT stuck"}]))

run("no agent_type", "allow", {"session_id": "x"}, agent_type=None)

# unknown agent WITH a claim but no per-agent rules file -> generic.rules.json
# fallback applies (claim<->contract net) -> block on missing REPORTED.
run("unknown agent -> generic net blocks", "block", bead(id="t12", status="in_progress"),
    agent_type="totally-unknown-agent", rules_file=None)

# unknown agent that DID report -> generic net satisfied -> allow.
run("unknown agent reported -> allow", "allow",
    bead(id="t13", status="in_progress", comments=[{"text": "REPORTED did the thing"}]),
    agent_type="totally-unknown-agent", rules_file=None)

print()
print(f"rules-eval conformance: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
