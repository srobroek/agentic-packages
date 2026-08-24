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
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = os.path.join(HERE, "rules-eval.py")
RULES = os.path.abspath(os.path.join(HERE, "..", ".apm", "rules"))
ARCH = os.path.join(RULES, "architect.rules.json")
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


def run(name, want, bead, agent_type="architect", rules_file=ARCH):
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
        comments=[{"text": "LANDED merge_sha=abc123"}],
    ),
    agent_type="shepherd",
    rules_file=SHEPHERD,
)

run(
    "shepherd exit without a disposition comment",
    "block",
    bead(
        id="t20b",
        status="closed",
        metadata={"pr": 42, "merge_sha": "abc123", "branch": "feature/demo"},
    ),
    agent_type="shepherd",
    rules_file=SHEPHERD,
)


# `bd set-state` never changes status: it writes a `state:<value>` label. Every
# deny_states value except `closed` is an operational state, so matching status
# alone left them all unreachable.
run(
    "deny_states matches a state: label",
    "block",
    bead(
        id="t23",
        status="in_progress",
        labels=["state:approved"],
        linked_comments=[{"text": "ADVICE use the indexed path"}],
    ),
    agent_type="advisor",
    rules_file=ADVISOR,
)

run(
    "an undenied state: label does not block",
    "allow",
    bead(
        id="t24",
        status="in_progress",
        labels=["state:working"],
        linked_comments=[{"text": "ADVICE use the indexed path"}],
    ),
    agent_type="advisor",
    rules_file=ADVISOR,
)

run(
    "denied status still blocks alongside an undenied state: label",
    "block",
    bead(
        id="t25",
        status="closed",
        labels=["agent:reviewer", "state:working"],
        metadata={"execution_kind": "git", "branch": "n", "push": "s"},
        comments=[{"text": "REPORTED done"}],
    ),
)

print("=== live claim resolution ===")
original_bd_json = MODULE.bd_json


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  ok   {name}")
    else:
        failed += 1
        print(f"  FAIL {name} -> {detail}")


def resolve_with(resources, payload, agent_type, assignee_resources=None):
    """Drive resolve_claimed_bead against fixture beads; returns (resolved, violations, calls)."""
    seen = []

    def fake_bd_json(*args):
        seen.append(args)
        if "--assignee" in args:
            return list(assignee_resources or [])
        return list(resources)

    MODULE.bd_json = fake_bd_json
    try:
        resolved, violations = MODULE.resolve_claimed_bead(payload, agent_type)
    finally:
        MODULE.bd_json = original_bd_json
    return resolved, violations, seen


_wt_bead = bead(
    id="t21",
    status="in_progress",
    assignee="reviewer-code",
    updated_at="2026-01-01",
    metadata={"actor": "reviewer-code", "worktree": "/x/arch-review"},
)

resolved, violations, calls = resolve_with(
    [_wt_bead],
    {
        "cwd": "/x/arch-review/packages/orchestrate",
        "agent_id": "agt_01H9xQ",
        "agent_type": "reviewer",
    },
    "reviewer",
)
check(
    "cwd inside the bead worktree resolves the active claim",
    resolved and resolved.get("id") == "t21",
    f"{resolved!r}",
)
check(
    "cwd match rejects the active claim at stop",
    any(item.get("check") == "claim_release" for item in violations),
    f"{violations!r}",
)
check(
    "live resolution includes terminal wisp resources",
    bool(calls) and "--include-infra" in calls[0] and "--all" in calls[0],
    f"{calls!r}",
)

resolved, _violations, _calls = resolve_with(
    [_wt_bead],
    {"cwd": "/x/arch-review", "agent_id": "agt_01H9xQ", "agent_type": "reviewer"},
    "reviewer",
)
check(
    "cwd equal to the worktree root resolves",
    resolved and resolved.get("id") == "t21",
    f"{resolved!r}",
)

# Proves the branch can fail: an unrelated cwd must resolve nothing at all.
resolved, violations, _calls = resolve_with(
    [_wt_bead],
    {"cwd": "/x/elsewhere/deep", "agent_id": "agt_01H9xQ", "agent_type": "reviewer"},
    "reviewer",
)
check(
    "cwd outside every worktree resolves nothing",
    resolved is None and violations == [],
    f"{resolved!r} {violations!r}",
)

# Sibling worktrees: a prefix test would resolve the shorter path.
_siblings = [
    bead(
        id="t-wt",
        status="in_progress",
        assignee="arch1",
        updated_at="2026-01-02",
        metadata={"worktree": "/x/arch-worktrunk"},
    ),
    bead(
        id="t-wt-int",
        status="in_progress",
        assignee="arch2",
        updated_at="2026-01-01",
        metadata={"worktree": "/x/arch-worktrunk-int"},
    ),
]
resolved, violations, _calls = resolve_with(
    _siblings,
    {
        "cwd": "/x/arch-worktrunk-int/pkg",
        "agent_id": "agt_01H9xQ",
        "agent_type": "architect",
    },
    "architect",
)
check(
    "sibling worktree prefix does not cross-match",
    resolved
    and resolved.get("id") == "t-wt-int"
    and [item["detail"] for item in violations] == ["active claims remain at stop: t-wt-int"],
    f"{resolved!r} {violations!r}",
)

# One worktree, several beads: only the in_progress+assigned one is the claim.
_shared = [
    bead(
        id="t-open",
        status="open",
        assignee="",
        updated_at="2026-01-03",
        metadata={"worktree": "/x/arch-vocab"},
    ),
    bead(
        id="t-closed",
        status="closed",
        assignee="arch9",
        updated_at="2026-01-04",
        metadata={"worktree": "/x/arch-vocab"},
    ),
    bead(
        id="t-live",
        status="in_progress",
        assignee="arch9",
        updated_at="2026-01-01",
        metadata={"worktree": "/x/arch-vocab"},
    ),
]
resolved, violations, _calls = resolve_with(
    _shared,
    {"cwd": "/x/arch-vocab/src", "agent_id": "agt_01H9xQ", "agent_type": "architect"},
    "architect",
)
check(
    "shared worktree resolves the active claim only",
    resolved
    and resolved.get("id") == "t-live"
    and [item["detail"] for item in violations] == ["active claims remain at stop: t-live"],
    f"{resolved!r} {violations!r}",
)

# A relative cwd must not key a bead. The worktree is the running process's cwd so
# that resolve() on a relative payload cwd would land inside it if the guard were gone.
resolved, violations, _calls = resolve_with(
    [
        bead(
            id="t-rel",
            status="in_progress",
            assignee="arch3",
            updated_at="2026-01-01",
            metadata={"worktree": os.getcwd()},
        )
    ],
    {"cwd": ".", "agent_id": "agt_01H9xQ", "agent_type": "architect"},
    "architect",
)
check(
    "relative cwd resolves no bead by worktree",
    resolved is None and violations == [],
    f"{resolved!r} {violations!r}",
)

# Branch B: artifact nodes carry no worktree, so assignee lookup is the only path.
resolved, violations, calls = resolve_with(
    [
        bead(
            id="t-art",
            status="in_progress",
            assignee="scribe-1",
            updated_at="2026-01-01",
            metadata={},
        )
    ],
    {"cwd": "/x/nowhere", "agent_id": "scribe-1", "agent_type": "scribe"},
    "scribe",
    assignee_resources=[
        bead(
            id="t-art",
            status="in_progress",
            assignee="scribe-1",
            updated_at="2026-01-01",
            metadata={},
        )
    ],
)
check(
    "assignee fallback resolves a bead with no worktree",
    resolved
    and resolved.get("id") == "t-art"
    and any(item.get("check") == "claim_release" for item in violations)
    and any("--assignee" in call for call in calls),
    f"{resolved!r} {violations!r}",
)

# deny_metadata is presence-based (_has_metadata), so a role must not deny a key
# the orchestrator is required to stamp pre-claim: the role gets blocked at exit
# for a write it never made. spawn-brief.md requires `branch`, `worktree`, and
# `worktree` on every Worktrunk-backed node.
run(
    "scribe exit allows the orchestrator branch stamp",
    "allow",
    bead(
        status="closed",
        labels=["agent:scribe"],
        metadata={"branch": "orc/run-1", "worktree": "/tmp/wt"},
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
        metadata={"branch": "orc/run-1", "worktree": "/tmp/wt"},
        comments=[{"body": "LANDED merge_sha=abc1234"}],
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
        comments=[{"body": "LANDED merge_sha=abc1234"}],
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
            "authority": {"deny_metadata": ["worktree", "branch", "output_ref"]},
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
            metadata={"branch": "orc/run-1", "worktree": "/tmp/wt"},
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

for _key in ("branch", "worktree", "actor", "artifacts_dir", "execution_agent"):
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

print("=== read budget fits the hook timeout ===")

HOOK_MANIFESTS = [
    os.path.abspath(os.path.join(HERE, "..", rel))
    for rel in (
        "hooks/claude-hooks.json",
        "hooks/codex-hooks.json",
        ".apm/hooks/orchestrate-claude-hooks.json",
        ".apm/hooks/orchestrate-codex-hooks.json",
    )
]


def _subagent_stop_timeouts(path):
    with open(path) as fh:
        manifest = json.load(fh)
    return [
        hook["timeout"]
        for entry in manifest["hooks"].get("SubagentStop", [])
        for hook in entry["hooks"]
        if "rules-eval.py" in hook.get("command", "")
    ]


for _manifest in HOOK_MANIFESTS:
    _timeouts = _subagent_stop_timeouts(_manifest)
    # Worst case: the whole read budget, then the three-write bounce path, all
    # before the verdict is emitted.
    _worst = MODULE.BD_READ_BUDGET + 3 * MODULE.BD_WRITE_TIMEOUT
    if _timeouts and all(_worst <= t for t in _timeouts):
        passed += 1
        print(f"  ok   {_worst}s worst case fits {_timeouts} in {os.path.basename(_manifest)}")
    else:
        failed += 1
        print(f"  FAIL {_worst}s worst case vs {_timeouts} in {os.path.basename(_manifest)}")


def _stalled_bd(tmpdir):
    """A bd whose reads hang, except `show` which yields five relates-to links.

    Hydration reads one bead per link, so the call count is data-driven; only a
    shared deadline bounds it.
    """
    log = os.path.join(tmpdir, "calls.log")
    script = os.path.join(tmpdir, "bd")
    links = json.dumps(
        {
            "id": "node-1",
            "dependencies": [
                {"id": f"wisp-{n}", "dependency_type": "relates-to"} for n in range(5)
            ],
            "dependents": [],
        }
    )
    with open(script, "w") as fh:
        fh.write(
            "#!/bin/sh\n"
            f'echo "$@" >> {log}\n'
            f'if [ "$1" = show ]; then printf %s {json.dumps(links)}; exit 0; fi\n'
            "sleep 60\n"
        )
    os.chmod(script, 0o755)
    return script, log


with tempfile.TemporaryDirectory() as _tmp:
    _fake_bd, _call_log = _stalled_bd(_tmp)
    _original_bd, _original_budget, _original_per_call = (
        MODULE.BD,
        MODULE.BD_READ_BUDGET,
        MODULE.BD_READ_TIMEOUT,
    )
    MODULE.BD = _fake_bd
    MODULE.BD_READ_BUDGET = 2
    MODULE.BD_READ_TIMEOUT = 1
    MODULE._read_deadline = None
    _target = bead(id="node-1", status="in_progress", labels=["orc-node", "agent:reviewer"])
    _started = time.monotonic()
    try:
        MODULE.resolve_claimed_bead({"agent_id": "runtime-1", "agent_type": "reviewer"}, "reviewer")
        MODULE.hydrate_comments(_target)
        _elapsed = time.monotonic() - _started
        with open(_call_log) as fh:
            _stalled_calls = [line for line in fh if not line.startswith("show ")]
    finally:
        MODULE.BD = _original_bd
        MODULE.BD_READ_BUDGET = _original_budget
        MODULE.BD_READ_TIMEOUT = _original_per_call
        MODULE._read_deadline = None

    if _elapsed <= 3:
        passed += 1
        print(f"  ok   stalled bd reads stay inside the 2s budget ({_elapsed:.1f}s)")
    else:
        failed += 1
        print(f"  FAIL stalled bd reads overran the 2s budget ({_elapsed:.1f}s)")

    # resolve_claimed_bead attempts three reads and hydration two more; the
    # per-call cap alone would let all five run, for 5x the elapsed ceiling.
    if 2 <= len(_stalled_calls) < 5:
        passed += 1
        print(f"  ok   the deadline refused reads past {len(_stalled_calls)} stalled calls")
    else:
        failed += 1
        print(f"  FAIL stalled read count does not show the deadline binding -> {_stalled_calls!r}")

    if _target.get("comments") == [] and _target.get("linked_comments") == []:
        passed += 1
        print("  ok   an expired read budget yields empty hydration, not an exception")
    else:
        failed += 1
        print(f"  FAIL hydration after budget expiry -> {_target!r}")

# The bounce path runs after the reads, so an exhausted read deadline must not
# swallow the writes that advance contract state.
with tempfile.TemporaryDirectory() as _tmp:
    _write_log = os.path.join(_tmp, "writes.log")
    _writer = os.path.join(_tmp, "bd")
    with open(_writer, "w") as fh:
        fh.write(f'#!/bin/sh\necho "$@" >> {_write_log}\n')
    os.chmod(_writer, 0o755)
    _original_bd = MODULE.BD
    MODULE.BD = _writer
    MODULE._read_deadline = time.monotonic() - 1
    try:
        MODULE.bd_json("comments", "node-1", "--json")
        MODULE.bd_write("comment", "node-1", "BOUNCE")
        MODULE.bd_write("update", "node-1", "--assignee", "")
    finally:
        MODULE.BD = _original_bd
        MODULE._read_deadline = None
    with open(_write_log) as fh:
        _writes = [line.split()[0] for line in fh]
if _writes == ["comment", "update"]:
    passed += 1
    print("  ok   writes still run once the read budget is spent")
else:
    failed += 1
    print(f"  FAIL writes after read-budget expiry -> {_writes!r}")

print()
print(f"rules-eval conformance: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
