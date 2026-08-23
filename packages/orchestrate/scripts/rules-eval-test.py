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

# A rules file that DOES deny an orchestrator anchor must still not block the
# role: presence proves nothing about who wrote it (astro-plan-78v0). The cases
# above only prove today's rules files happen to omit those keys.
_ANCHOR_RULES = os.path.join(HERE, "_anchor_deny.rules.json")
with open(_ANCHOR_RULES, "w") as fh:
    json.dump(
        {
            "agent": "scribe",
            "authority": {"deny_metadata": ["worktree", "branch", "lease_token", "output_ref"]},
        },
        fh,
    )
try:
    run(
        "denying an orchestrator anchor does not block",
        "allow",
        bead(
            status="closed",
            labels=["agent:scribe"],
            metadata={"branch": "orc/run-1", "worktree": "/tmp/wt", "lease_token": "l1"},
        ),
        agent_type="scribe",
        rules_file=_ANCHOR_RULES,
    )
    run(
        "a denied non-anchor key still blocks",
        "block",
        bead(
            status="closed",
            labels=["agent:scribe"],
            metadata={"worktree": "/tmp/wt", "output_ref": "/tmp/somewhere"},
        ),
        agent_type="scribe",
        rules_file=_ANCHOR_RULES,
    )
finally:
    os.unlink(_ANCHOR_RULES)

for _key in ("branch", "worktree", "lease_token", "actor", "artifacts_dir", "runtime_handle"):
    if _key in MODULE.ORCHESTRATOR_ANCHORS:
        passed += 1
        print(f"  ok   spawn-brief anchor {_key} is exempt")
    else:
        failed += 1
        print(f"  FAIL spawn-brief anchor {_key} is not exempt")


# deny_metadata compares against the claim-time snapshot: the shepherd stamps
# metadata.pr on a node the specialist then re-claims for a review round, and
# presence alone made every later exit unreachable (astro-plan-indxl).
def _pr_node(baseline: dict | None, pr: str = "https://x/pull/1"):
    metadata = {
        "execution_kind": "git",
        "branch": "node-pr",
        "push": "abc123",
        "pr": pr,
    }
    if baseline is not None:
        metadata[MODULE.CLAIM_BASELINE_KEY] = json.dumps(baseline)
    return bead(
        id="tpr",
        status="in_progress",
        labels=["orc-node", "agent:reviewer"],
        metadata=metadata,
        comments=[{"text": "BRIEF do the thing"}, {"text": "REPORTED done, verified"}],
    )


run(
    "denied key unchanged since the claim does not block",
    "allow",
    _pr_node({"pr": "https://x/pull/1", "branch": "node-pr"}),
)
run(
    "the claiming role changing a denied key still blocks",
    "block",
    _pr_node({"pr": "https://x/pull/0", "branch": "node-pr"}),
)
run(
    "the claiming role introducing a denied key still blocks",
    "block",
    _pr_node({"branch": "node-pr"}),
)
run(
    "no snapshot falls back to presence",
    "block",
    _pr_node(None),
)

print("=== linked comment hydration ===")


def _hydrate(bead_payload):
    """Run hydrate_comments against a stub bd exposing one link of each edge type."""

    def stub_bd_json(*args):
        if args[0] == "comments":
            if args[1] == "node-1":
                return [{"text": "ASSIGN node-1"}]
            if args[1] == "msg-1":
                return [{"text": "REPORTED node-1 self-sent"}]
            return [{"text": "REVIEW node-1 verdict:approve"}]
        return {
            "id": "node-1",
            "dependencies": [
                {"id": "wisp-1", "dependency_type": "relates-to"},
                {"id": "msg-1", "dependency_type": "replies-to"},
            ],
            "dependents": None,
        }

    MODULE.bd_json = stub_bd_json
    try:
        MODULE.hydrate_comments(bead_payload)
    finally:
        MODULE.bd_json = original_bd_json
    return bead_payload


for _name, _kind in (
    ("an ordinary node bead", {}),
    ("an execution_kind resource", {"execution_kind": "review"}),
):
    _hydrated = _hydrate(bead(id="node-1", metadata=dict(_kind)))
    if MODULE._linked_comment_verbs(_hydrated) == ["REVIEW"]:
        passed += 1
        print(f"  ok   relates-to comments hydrate for {_name}, replies-to excluded")
    else:
        failed += 1
        print(f"  FAIL linked comments hydrate for {_name} -> {_hydrated.get('linked_comments')!r}")

_hydrated = _hydrate(bead(id="node-1", ephemeral=True))
if MODULE._linked_comment_verbs(_hydrated) == ["REPORTED", "REVIEW"]:
    passed += 1
    print("  ok   a wisp still hydrates its replies-to thread")
else:
    failed += 1
    print(f"  FAIL wisp replies-to hydration -> {_hydrated.get('linked_comments')!r}")

print("=== hydration and claim-baseline compose ===")

_REVIEW_BASELINE = {"pr": "https://x/pull/1", "branch": "node-1"}


def _reclaimed_review_node(pr: str):
    """A reviewer-claimed orc-node whose exit needs both behaviours at once.

    The verdict lives on a relates-to wisp, reachable only once hydration
    covers non-wisp beads, and metadata.pr was stamped by the shepherd before
    the claim, so it must match the baseline instead of counting as a write.
    """
    return _hydrate(
        bead(
            id="node-1",
            status="in_progress",
            labels=["orc-node", "agent:reviewer"],
            metadata={
                "execution_kind": "review",
                "branch": "node-1",
                "pr": pr,
                MODULE.CLAIM_BASELINE_KEY: json.dumps(_REVIEW_BASELINE),
            },
        )
    )


run(
    "node hydrates its verdict and keeps stamped pr",
    "allow",
    _reclaimed_review_node("https://x/pull/1"),
    agent_type="reviewer",
    rules_file=REVIEWER,
)
run(
    "the same node blocks when it rewrote pr",
    "block",
    _reclaimed_review_node("https://x/pull/2"),
    agent_type="reviewer",
    rules_file=REVIEWER,
)

print()
print(f"rules-eval conformance: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
