#!/usr/bin/env python3
"""Verification harness for dispatcher.py + nodes.json. Not shipped.

Drives the dispatcher exactly as the hook wires it: the command string supplies
`dispatcher.py <nodes.json>` and `args` supplies the phase, so both arrive in
argv. We pass them in the same order the hook does, and also test reversed order
to prove argv parsing is order-independent.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DISP = os.path.join(HERE, "dispatcher.py")
NODES = os.path.join(HERE, "nodes.json")


def run(phase, payload, env_extra=None, project_dir=None, cwd=None, reversed_args=False):
    env = dict(os.environ)
    env.pop("SPECIFY_FEATURE_DIRECTORY", None)
    if project_dir is not None:
        env["CLAUDE_PROJECT_DIR"] = project_dir
    if env_extra:
        env.update(env_extra)
    # Hook form: command tokens = [dispatcher.py, nodes.json], args = [phase].
    argv = [sys.executable, DISP, NODES, phase]
    if reversed_args:
        argv = [sys.executable, DISP, phase, NODES]
    proc = subprocess.run(
        argv,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
    )
    assert proc.returncode == 0, "nonzero exit: %r / stderr=%r" % (proc.returncode, proc.stderr)
    out = proc.stdout.strip()
    return json.loads(out) if out else None


def main():
    # nodes.json must load and contain the migrated node graph.
    data = json.load(open(NODES, encoding="utf-8"))
    phases = sum(len(v) for v in data.values())
    assert "plan" in data and "pre" in data["plan"], "plan node missing"
    assert phases == 172, "expected 172 phases, got %d" % phases
    print("T0 PASS: nodes.json loads, %d ids, %d phases" % (len(data), phases))

    noproj = tempfile.mkdtemp(prefix="speckit-noproj-")

    # T1: Claude UserPromptExpansion, plan, pre, feat unresolved -> block with
    # guidance (plan has a <feat>-scoped HARD-MISSING; an unresolvable feature is
    # blocked rather than silently skipped) while still routing the event and
    # rendering the node body as additionalContext.
    d = run("pre", {"hook_event_name": "UserPromptExpansion", "command_name": "speckit.plan"}, project_dir=noproj)
    assert d is not None and d.get("decision") == "block", "T1: must block when feat unresolved: %r" % d
    assert "No active SpecKit feature" in d["reason"], "T1 reason: %r" % d.get("reason")
    assert d["hookSpecificOutput"]["hookEventName"] == "UserPromptExpansion"
    assert d["hookSpecificOutput"]["additionalContext"].startswith("# /speckit.plan")
    print("T1 PASS: pre block-on-unresolved-feat plan, event=UserPromptExpansion")

    # T1b: argv order-independence (phase before nodes.json path).
    d = run("pre", {"hook_event_name": "UserPromptExpansion", "command_name": "speckit.plan"}, project_dir=noproj, reversed_args=True)
    assert d is not None and d["hookSpecificOutput"]["additionalContext"].startswith("# /speckit.plan")
    print("T1b PASS: argv parsing order-independent")

    # T2: post via PostToolUse Skill speckit-plan.
    d = run("post", {"hook_event_name": "PostToolUse", "tool_input": {"skill": "speckit-plan"}}, project_dir=noproj)
    assert d is not None and "decision" not in d
    assert d["hookSpecificOutput"]["additionalContext"].startswith("# /speckit.plan -- what to do next")
    print("T2 PASS: post inject plan, event=PostToolUse")

    # T3: HARD-MISSING fires when feat resolves but spec.md absent.
    proj = tempfile.mkdtemp(prefix="speckit-proj-")
    os.makedirs(os.path.join(proj, "specs", "001-demo"))
    d = run(
        "pre",
        {"hook_event_name": "UserPromptExpansion", "command_name": "speckit.plan"},
        env_extra={"SPECIFY_FEATURE_DIRECTORY": "specs/001-demo/"},
        project_dir=proj,
        cwd=proj,
    )
    assert d is not None and d["decision"] == "block", "T3: expected block, got %r" % d
    assert "spec.md" in d["reason"], "T3 reason: %r" % d["reason"]
    print("T3 PASS: HARD-MISSING block on specs/<feat>/spec.md, reason=%r" % d["reason"])

    # T3b: memory-synthesis.md is a HARD prerequisite -> plan blocks when it is
    # absent even though spec.md exists.
    open(os.path.join(proj, "specs", "001-demo", "spec.md"), "w").write("x")
    d = run(
        "pre",
        {"hook_event_name": "UserPromptExpansion", "command_name": "speckit.plan"},
        env_extra={"SPECIFY_FEATURE_DIRECTORY": "specs/001-demo/"},
        project_dir=proj,
        cwd=proj,
    )
    assert d is not None and d["decision"] == "block", "T3b: expected block, got %r" % d
    assert "memory-synthesis.md" in d["reason"], "T3b reason: %r" % d["reason"]
    print("T3b PASS: HARD-MISSING block on memory-synthesis.md, reason=%r" % d["reason"])

    # T4: HARD-EXISTS fires (spec.md + memory-synthesis.md + plan.md present) -> PreToolUse deny.
    open(os.path.join(proj, "specs", "001-demo", "memory-synthesis.md"), "w").write("x")
    open(os.path.join(proj, "specs", "001-demo", "plan.md"), "w").write("x")
    d = run(
        "pre",
        {"hook_event_name": "PreToolUse", "tool_input": {"skill": "speckit-plan"}},
        env_extra={"SPECIFY_FEATURE_DIRECTORY": "specs/001-demo"},
        project_dir=proj,
        cwd=proj,
    )
    assert d is not None, "T4: expected output"
    so = d["hookSpecificOutput"]
    assert so["hookEventName"] == "PreToolUse" and so["permissionDecision"] == "deny", "T4: %r" % d
    assert "plan.md" in so["permissionDecisionReason"]
    assert "/speckit.refine.update" in so["permissionDecisionReason"]
    print("T4 PASS: HARD-EXISTS PreToolUse deny, reason=%r" % so["permissionDecisionReason"])

    # T5: HARD-MISSING does NOT block once spec.md exists (plan.md removed).
    os.remove(os.path.join(proj, "specs", "001-demo", "plan.md"))
    d = run(
        "pre",
        {"hook_event_name": "UserPromptExpansion", "command_name": "speckit.plan"},
        env_extra={"SPECIFY_FEATURE_DIRECTORY": "specs/001-demo"},
        project_dir=proj,
        cwd=proj,
    )
    assert d is not None and "decision" not in d, "T5: must not block; %r" % d
    assert d["hookSpecificOutput"]["additionalContext"].startswith("# /speckit.plan")
    print("T5 PASS: spec present + plan absent -> soft inject, no block")

    # T6: Codex UserPromptSubmit slash parse.
    d = run("pre", {"hook_event_name": "UserPromptSubmit", "prompt": "please run /speckit.plan now"}, project_dir=noproj)
    assert d is not None and d["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert d["hookSpecificOutput"]["additionalContext"].startswith("# /speckit.plan")
    print("T6 PASS: Codex UserPromptSubmit slash-parse")

    # T7: dotted command id normalization (agent-assign.execute).
    d = run("post", {"hook_event_name": "PostToolUse", "tool_input": {"command_name": "speckit.agent-assign.execute"}}, project_dir=noproj)
    assert d is not None and d["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    print("T7 PASS: dotted-id normalization agent-assign.execute")

    # T8: HARD-DEPRECATED always blocks (implement), even without feat.
    d = run("pre", {"hook_event_name": "UserPromptExpansion", "command_name": "speckit.implement"}, project_dir=noproj)
    assert d is not None and d["decision"] == "block", "T8: implement must block: %r" % d
    assert "deprecated" in d["reason"], "T8 reason: %r" % d["reason"]
    print("T8 PASS: HARD-DEPRECATED block on implement, reason=%r" % d["reason"][:60])

    # T8b: payload `cwd` (invoking agent's worktree) wins over CLAUDE_PROJECT_DIR.
    # Launch checkout (project_dir) has specs/041-stale but no spec.md -> would
    # block on 041; the agent's actual worktree (payload cwd) resolves 001-demo
    # via its own .specify/feature.json and passes preconditions. Proves feature
    # resolution follows the invoking agent's dir, not the original launch dir.
    launch = tempfile.mkdtemp(prefix="speckit-launch-")
    os.makedirs(os.path.join(launch, "specs", "041-stale"))
    os.makedirs(os.path.join(launch, ".specify"))
    open(os.path.join(launch, ".specify", "feature.json"), "w").write(
        json.dumps({"feature_directory": "specs/041-stale"})
    )
    wt = tempfile.mkdtemp(prefix="speckit-worktree-")
    os.makedirs(os.path.join(wt, "specs", "001-demo"))
    os.makedirs(os.path.join(wt, ".specify"))
    open(os.path.join(wt, ".specify", "feature.json"), "w").write(
        json.dumps({"feature_directory": "specs/001-demo"})
    )
    open(os.path.join(wt, "specs", "001-demo", "spec.md"), "w").write("x")
    open(os.path.join(wt, "specs", "001-demo", "memory-synthesis.md"), "w").write("x")
    d = run(
        "pre",
        {
            "hook_event_name": "UserPromptExpansion",
            "command_name": "speckit.plan",
            "cwd": wt,
        },
        project_dir=launch,
    )
    assert d is not None and "decision" not in d, "T8b: must resolve worktree feat, not block on launch dir: %r" % d
    assert d["hookSpecificOutput"]["additionalContext"].startswith("# /speckit.plan")
    print("T8b PASS: payload cwd (worktree) overrides CLAUDE_PROJECT_DIR for feat resolution")

    # T9: unknown command / unrelated event -> silent no-op.
    d = run("pre", {"hook_event_name": "UserPromptExpansion", "command_name": "speckit.does-not-exist"}, project_dir=noproj)
    assert d is None, "T9: unknown node must produce no output"
    d = run("pre", {"hook_event_name": "SessionStart"}, project_dir=noproj)
    assert d is None, "T9: unrelated event must produce no output"
    print("T9 PASS: unknown node + unrelated event -> silent no-op")

    print("\nALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
