#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Smoke test for the orchestrate hook entry scripts (spec 002 N3).

Exercises contract-start.py (injector) and orchestrator-claim-deny.py (gate)
directly as subprocesses. The SubagentStop evaluator has its own conformance
suite (rules-eval-test.py). Also validates both hook JSON configs parse and
reference only existing scripts. Exits non-zero on any failure.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOOKS = os.path.abspath(os.path.join(HERE, ".."))
passed = 0
failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok   {name}")
    else:
        failed += 1
        print(f"  FAIL {name}  {detail}")


def run_hook(script, payload, env=None):
    proc = subprocess.run(["uv", "run", "--quiet", os.path.join(HERE, script)],
                          input=json.dumps(payload), capture_output=True, text=True,
                          env={**os.environ, **(env or {})})
    try:
        return json.loads(proc.stdout or "{}"), proc
    except Exception:
        return {}, proc


print("=== contract-start.py (injector) ===")
out, _ = run_hook("contract-start.py", {"agent_id": "coder-x", "agent_type": "domain-specialist"})
check("subagent with id -> injects contract",
      out.get("hookSpecificOutput", {}).get("additionalContext", "").startswith("Bead contract"))
out, _ = run_hook("contract-start.py", {"session_id": "s"})
check("no agent id -> no injection", out == {})

print("=== orchestrator-claim-deny.py ===")
# no run marker -> allow
out, _ = run_hook("orchestrator-claim-deny.py",
                  {"tool_input": {"command": "bd update x --claim"}})
check("no run marker -> allow", out == {})
# run marker + bd --claim -> deny
out, _ = run_hook("orchestrator-claim-deny.py",
                  {"tool_input": {"command": "bd update x --claim"}},
                  env={"ORCHESTRATE_RUN": "1"})
check("in run + bd --claim -> deny", out.get("decision") == "deny", str(out))
# run marker + bd update without --claim -> allow
out, _ = run_hook("orchestrator-claim-deny.py",
                  {"tool_input": {"command": "bd update x --status open"}},
                  env={"ORCHESTRATE_RUN": "1"})
check("in run + bd update (no claim) -> allow", out == {})
# run marker + non-bd command -> allow
out, _ = run_hook("orchestrator-claim-deny.py",
                  {"tool_input": {"command": "git commit -m x"}},
                  env={"ORCHESTRATE_RUN": "1"})
check("in run + non-bd cmd -> allow", out == {})
# --claim inside an echo string must NOT deny (word-boundary / first-word check)
out, _ = run_hook("orchestrator-claim-deny.py",
                  {"tool_input": {"command": "echo 'bd update x --claim'"}},
                  env={"ORCHESTRATE_RUN": "1"})
check("--claim inside echo -> allow (not a bd invocation)", out == {})
# malformed input -> allow (fail open)
out, proc = run_hook("orchestrator-claim-deny.py", {}, env={"ORCHESTRATE_RUN": "1"})
check("malformed/empty input -> allow (fail open)", out == {})

print("=== hook JSON configs ===")
for cfg in ("orchestrate-claude-hooks.json", "orchestrate-codex-hooks.json"):
    path = os.path.join(HOOKS, cfg)
    try:
        with open(path) as fh:
            data = json.load(fh)
        ok = True
        refs = json.dumps(data)
        for script in ("contract-start.py", "rules-eval.py", "orchestrator-claim-deny.py"):
            if script in refs and not os.path.isfile(os.path.join(HERE, script)):
                ok = False
        check(f"{cfg} parses + refs exist", ok)
    except Exception as e:
        check(f"{cfg} parses", False, str(e))

print()
print(f"hooks smoke test: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
