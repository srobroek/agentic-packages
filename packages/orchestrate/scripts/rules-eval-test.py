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

import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = os.path.join(HERE, "rules-eval.py")
RULES = os.path.abspath(os.path.join(HERE, "..", ".apm", "rules"))
DS = os.path.join(RULES, "domain-specialist.rules.json")
ADVISOR = os.path.join(RULES, "advisor.rules.json")
RESEARCHER = os.path.join(RULES, "researcher.rules.json")
REVIEWER = os.path.join(RULES, "reviewer.rules.json")
SCRIBE = os.path.join(RULES, "scribe.rules.json")
SHEPHERD = os.path.join(RULES, "shepherd.rules.json")
SPEC = importlib.util.spec_from_file_location("rules_eval", EVAL)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

passed = 0
failed = 0


def run(name, want, bead, agent_type="domain-specialist", rules_file=DS):
    global passed, failed
    payload = {"agent_type": agent_type, "_bead": bead}
    if rules_file:
        payload["_rules_file"] = rules_file
    if agent_type is None:
        payload = bead  # raw-payload cases
    proc = subprocess.run(
        ["uv", "run", "--quiet", EVAL],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={**os.environ, "RULES_DIR": RULES},
    )
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
run(
    "git complete",
    "allow",
    bead(
        id="t1",
        status="in_progress",
        labels=["orc-node", "agent:reviewer"],
        metadata={"execution_kind": "git", "branch": "node-t1", "push": "abc123"},
        comments=[{"text": "BRIEF do the thing"}, {"text": "REPORTED done, verified"}],
    ),
)

run(
    "git missing push",
    "block",
    bead(
        id="t2",
        status="in_progress",
        labels=["agent:reviewer"],
        metadata={"execution_kind": "git", "branch": "n"},
        comments=[{"text": "REPORTED done"}],
    ),
)

run(
    "git missing handoff label",
    "block",
    bead(
        id="t3",
        status="in_progress",
        labels=["orc-node"],
        metadata={"execution_kind": "git", "branch": "n", "push": "s"},
        comments=[{"text": "REPORTED done"}],
    ),
)

run(
    "git no reported comment",
    "block",
    bead(
        id="t4",
        status="in_progress",
        labels=["agent:reviewer"],
        metadata={"execution_kind": "git", "branch": "n", "push": "s"},
        comments=[{"text": "CHECKPOINT step 1"}],
    ),
)

run(
    "escape blocked+FAILED",
    "allow",
    bead(
        id="t5",
        status="blocked",
        metadata={"execution_kind": "git"},
        comments=[{"text": "FAILED repo is broken"}],
    ),
)

run(
    "blocked status no FAILED comment",
    "block",
    bead(
        id="t6",
        status="blocked",
        metadata={"execution_kind": "git"},
        comments=[{"text": "CHECKPOINT partial"}],
    ),
)

run(
    "authority deny closed",
    "block",
    bead(
        id="t7",
        status="closed",
        labels=["agent:reviewer"],
        metadata={"execution_kind": "git", "branch": "n", "push": "s"},
        comments=[{"text": "REPORTED done"}],
    ),
)

run(
    "authority deny merge_sha",
    "block",
    bead(
        id="t8",
        status="in_progress",
        labels=["agent:reviewer"],
        metadata={"execution_kind": "git", "branch": "n", "push": "s", "merge_sha": "dead"},
        comments=[{"text": "REPORTED done"}],
    ),
)

run(
    "artifact complete",
    "allow",
    bead(
        id="t9",
        status="in_progress",
        metadata={
            "execution_kind": "artifact",
            "artifacts_dir": "/run/artifacts",
            "output_ref": "/run/artifacts/r.md",
            "worktree": "/worktrees/task-9",
        },
        comments=[{"text": "REPORTED: done"}],
    ),
)

run(
    "artifact missing output_ref",
    "block",
    bead(
        id="t10",
        status="in_progress",
        metadata={"execution_kind": "artifact", "artifacts_dir": "/run/artifacts"},
        comments=[{"text": "REPORTED done"}],
    ),
)

run(
    "artifact relative shared directory",
    "block",
    bead(
        id="t10-relative",
        status="in_progress",
        metadata={
            "execution_kind": "artifact",
            "artifacts_dir": ".orchestration/run-1/artifacts",
            "output_ref": "/worktrees/task/.orchestration/run-1/artifacts/r.md",
        },
        comments=[{"text": "REPORTED done"}],
    ),
)

run(
    "artifact escapes shared directory",
    "block",
    bead(
        id="t10-escape",
        status="in_progress",
        metadata={
            "execution_kind": "artifact",
            "artifacts_dir": "/run/artifacts",
            "output_ref": "/run/other/r.md",
        },
        comments=[{"text": "REPORTED done"}],
    ),
)

run(
    "artifact inside disposable worktree",
    "block",
    bead(
        id="t10-worktree",
        status="in_progress",
        metadata={
            "execution_kind": "artifact",
            "artifacts_dir": "/worktrees/task/.orchestration/run-1/artifacts",
            "output_ref": "/worktrees/task/.orchestration/run-1/artifacts/r.md",
            "worktree": "/worktrees/task",
        },
        comments=[{"text": "REPORTED done"}],
    ),
)

run(
    "bounce at max_attempts",
    "allow",
    bead(
        id="t11",
        status="in_progress",
        metadata={"execution_kind": "git", "stop_attempts": 2},
        comments=[{"text": "CHECKPOINT stuck"}],
    ),
)

run("no agent_type", "allow", {"session_id": "x"}, agent_type=None)

# unknown agent WITH a claim but no per-agent rules file -> generic.rules.json
# fallback applies (claim<->contract net) -> block on missing REPORTED.
run(
    "unknown agent -> generic net blocks",
    "block",
    bead(id="t12", status="in_progress"),
    agent_type="totally-unknown-agent",
    rules_file=None,
)

# unknown agent that DID report -> generic net satisfied -> allow.
run(
    "unknown agent reported -> allow",
    "allow",
    bead(id="t13", status="in_progress", comments=[{"text": "REPORTED did the thing"}]),
    agent_type="totally-unknown-agent",
    rules_file=None,
)

run(
    "advisor closed wisp with durable advice",
    "allow",
    bead(
        id="t14",
        status="closed",
        ephemeral=True,
        wisp_type="escalation",
        linked_comments=[{"text": "ADVICE use the indexed path"}],
    ),
    agent_type="advisor",
    rules_file=ADVISOR,
)

run(
    "reviewer closed wisp with durable verdict",
    "allow",
    bead(
        id="t15",
        status="closed",
        ephemeral=True,
        wisp_type="escalation",
        linked_comments=[{"text": "REVIEW dimension=code round=1 verdict=approve"}],
    ),
    agent_type="reviewer",
    rules_file=REVIEWER,
)

run(
    "researcher escalation with durable answer",
    "allow",
    bead(
        id="t16",
        status="closed",
        ephemeral=True,
        wisp_type="escalation",
        linked_comments=[{"text": "ADVICE primary source confirms the limit"}],
    ),
    agent_type="researcher",
    rules_file=RESEARCHER,
)

run(
    "research artifact complete",
    "allow",
    bead(
        id="t17",
        status="in_progress",
        labels=["agent:reviewer"],
        metadata={
            "execution_kind": "artifact",
            "artifacts_dir": "/run/artifacts",
            "output_ref": "/run/artifacts/r.md",
            "worktree": "/worktrees/research-17",
        },
        comments=[{"text": "REPORTED cited findings"}],
    ),
    agent_type="researcher",
    rules_file=RESEARCHER,
)

run(
    "research artifact invented handoff",
    "block",
    bead(
        id="t17-invalid-route",
        status="in_progress",
        labels=["agent:validator"],
        metadata={
            "execution_kind": "artifact",
            "artifacts_dir": "/run/artifacts",
            "output_ref": "/run/artifacts/r.md",
            "worktree": "/worktrees/research-17",
        },
        comments=[{"text": "REPORTED cited findings"}],
    ),
    agent_type="researcher",
    rules_file=RESEARCHER,
)

run(
    "scribe closed query with durable report",
    "allow",
    bead(
        id="t18",
        status="closed",
        ephemeral=True,
        wisp_type="gc_report",
        linked_comments=[{"text": "REPORTED report=/run/artifacts/final.md"}],
    ),
    agent_type="scribe",
    rules_file=SCRIBE,
)

run(
    "scribe missing durable report",
    "block",
    bead(id="t19", status="closed", ephemeral=True, wisp_type="gc_report"),
    agent_type="scribe",
    rules_file=SCRIBE,
)

run(
    "in-run shepherd closed merge resource",
    "allow",
    bead(
        id="t20",
        status="closed",
        metadata={"pr": 42, "merge_sha": "abc123", "branch": "feature/demo"},
    ),
    agent_type="shepherd",
    rules_file=SHEPHERD,
)


print("=== live claim resolution ===")
original_bd_json = MODULE.bd_json
calls = []


def fake_bd_json(*args):
    calls.append(args)
    if "--assignee" in args:
        return []
    return [
        bead(
            id="t21",
            status="closed",
            assignee="reviewer-code",
            ephemeral=True,
            wisp_type="escalation",
            metadata={
                "actor": "reviewer-code",
                "runtime_context": "runtime-agent-21",
            },
        )
    ]


MODULE.bd_json = fake_bd_json
try:
    resolved, violations = MODULE.resolve_claimed_bead(
        {"agent_id": "runtime-agent-21", "agent_type": "reviewer"},
        "reviewer",
    )
finally:
    MODULE.bd_json = original_bd_json

if resolved and resolved.get("id") == "t21" and not violations:
    passed += 1
    print("  ok   runtime context resolves closed activation resource")
else:
    failed += 1
    print(
        f"  FAIL runtime context resolves closed activation resource -> {resolved!r} {violations!r}"
    )

if calls and "--include-infra" in calls[0] and "--all" in calls[0]:
    passed += 1
    print("  ok   live resolution includes terminal wisp resources")
else:
    failed += 1
    print(f"  FAIL live resolution includes terminal wisp resources -> {calls!r}")

MODULE.bd_json = lambda *_args: [
    bead(
        id="t22",
        status="in_progress",
        assignee="domain-specialist-files",
        metadata={"runtime_context": "runtime-agent-22"},
    )
]
try:
    _resolved, violations = MODULE.resolve_claimed_bead(
        {"agent_id": "runtime-agent-22", "agent_type": "domain-specialist"},
        "domain-specialist",
    )
finally:
    MODULE.bd_json = original_bd_json

if any(item.get("check") == "claim_release" for item in violations):
    passed += 1
    print("  ok   live resolution rejects active claim at stop")
else:
    failed += 1
    print(f"  FAIL live resolution rejects active claim at stop -> {violations!r}")

# deny_metadata is presence-based (_has_metadata), so a role must not deny a key
# the orchestrator is required to stamp pre-claim: the role gets blocked at exit
# for a write it never made. spawn-brief.md requires `branch`, `worktree`, and
# `lease_token` on every Worktrunk-backed node.
run(
    "scribe exit allows the orchestrator branch stamp",
    "allow",
    bead(
        status="closed",
        labels=["agent:scribe"],
        metadata={"branch": "orc/run-1", "worktree": "/tmp/wt", "lease_token": "l1"},
        linked_comments=[{"text": "REPORTED report=/run/artifacts/run-report.md"}],
    ),
    agent_type="scribe",
    rules_file=SCRIBE,
)
run(
    "shepherd exit allows the orchestrator worktree stamp",
    "allow",
    bead(
        status="closed",
        labels=["agent:integrator"],
        metadata={"branch": "orc/run-1", "worktree": "/tmp/wt", "lease_token": "l1"},
        comments=[{"body": "MERGED merge_sha=abc1234"}],
    ),
    agent_type="shepherd",
    rules_file=SHEPHERD,
)
run(
    "scribe still blocked on its own forbidden output_ref",
    "block",
    bead(
        status="closed",
        labels=["agent:scribe"],
        metadata={"branch": "orc/run-1", "output_ref": "/tmp/somewhere"},
        linked_comments=[{"text": "REPORTED report=/run/artifacts/run-report.md"}],
    ),
    agent_type="scribe",
    rules_file=SCRIBE,
)
run(
    "shepherd still blocked on its own forbidden output_ref",
    "block",
    bead(
        status="closed",
        labels=["agent:integrator"],
        metadata={"worktree": "/tmp/wt", "output_ref": "/tmp/somewhere"},
        comments=[{"body": "MERGED merge_sha=abc1234"}],
    ),
    agent_type="shepherd",
    rules_file=SHEPHERD,
)

print()
print(f"rules-eval conformance: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
