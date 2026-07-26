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
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
HOOKS = os.path.abspath(os.path.join(HERE, "..", ".apm", "hooks"))
SKILL = os.path.abspath(os.path.join(HERE, "..", ".apm", "skills", "orchestrate"))
AGENTS = os.path.abspath(os.path.join(HERE, "..", ".apm", "agents"))
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
    proc = subprocess.run(
        ["uv", "run", "--quiet", os.path.join(HERE, script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )
    try:
        return json.loads(proc.stdout or "{}"), proc
    except Exception:
        return {}, proc


def pretool_denied(output):
    return (
        output.get("hookSpecificOutput", {}).get("hookEventName") == "PreToolUse"
        and output["hookSpecificOutput"].get("permissionDecision") == "deny"
        and bool(output["hookSpecificOutput"].get("permissionDecisionReason"))
    )


print("=== contract-start.py (injector) ===")
out, _ = run_hook("contract-start.py", {"agent_id": "coder-x", "agent_type": "domain-specialist"})
check(
    "subagent with id -> injects contract",
    out.get("hookSpecificOutput", {}).get("additionalContext", "").startswith("Bead contract"),
)
out, _ = run_hook("contract-start.py", {"session_id": "s"})
check("no agent id -> no injection", out == {})

print("=== orchestrator-claim-deny.py ===")
# no run marker -> allow
out, _ = run_hook("orchestrator-claim-deny.py", {"tool_input": {"command": "bd update x --claim"}})
check("no run marker -> allow", out == {})
# run marker + bd --claim -> deny
out, _ = run_hook(
    "orchestrator-claim-deny.py",
    {"tool_input": {"command": "bd update x --claim"}},
    env={"ORCHESTRATE_RUN": "1"},
)
check("in run + bd --claim -> deny", pretool_denied(out), str(out))
# A leading cd is the normal Claude Bash shape and must not hide the claim.
out, _ = run_hook(
    "orchestrator-claim-deny.py",
    {"tool_input": {"command": "cd /tmp/project\nbd update x --claim"}},
    env={"ORCHESTRATE_RUN": "1"},
)
check("in run + multiline bd --claim -> deny", pretool_denied(out), str(out))
# Shell whitespace variants must not bypass T0 authority enforcement.
out, _ = run_hook(
    "orchestrator-claim-deny.py",
    {"tool_input": {"command": "bd\tupdate x\t--claim"}},
    env={"ORCHESTRATE_RUN": "1"},
)
check("in run + tab-separated bd --claim -> deny", pretool_denied(out), str(out))
# Actor variables may prefix a worker claim, but T0 must still be denied.
out, _ = run_hook(
    "orchestrator-claim-deny.py",
    {
        "tool_input": {
            "command": 'cd /tmp/project && BEADS_ACTOR="lead" BD_ACTOR="lead" bd update x --claim'
        }
    },
    env={"ORCHESTRATE_RUN": "1"},
)
check("in run + env-prefixed bd --claim -> deny", pretool_denied(out), str(out))
# A worker claim must carry the same stable actor in both Beads variables.
out, _ = run_hook(
    "orchestrator-claim-deny.py",
    {
        "tool_input": {
            "command": (
                'BEADS_ACTOR="claude/researcher/session-123" '
                'BD_ACTOR="claude/researcher/session-123" bd update x --claim'
            )
        }
    },
    env={"ORCHESTRATE_RUN": "1"},
)
check("in run + bound worker claim -> allow", out == {}, str(out))
out, _ = run_hook(
    "orchestrator-claim-deny.py",
    {
        "tool_input": {
            "command": (
                'ACTOR="claude/researcher/session-123"; '
                'BEADS_ACTOR="$ACTOR" BD_ACTOR="$ACTOR" bd update x --claim'
            )
        }
    },
    env={"ORCHESTRATE_RUN": "1"},
)
check("in run + resolved worker ACTOR -> allow", out == {}, str(out))
out, _ = run_hook(
    "orchestrator-claim-deny.py",
    {
        "tool_input": {
            "command": (
                'BEADS_ACTOR="claude/researcher/session-123" '
                'BD_ACTOR="claude/reviewer/session-456" bd update x --claim'
            )
        }
    },
    env={"ORCHESTRATE_RUN": "1"},
)
check("in run + mismatched worker identity -> deny", pretool_denied(out), str(out))
out, _ = run_hook(
    "orchestrator-claim-deny.py",
    {"tool_input": {"command": 'BEADS_ACTOR="root" BD_ACTOR="root" bd update x --claim'}},
    env={"ORCHESTRATE_RUN": "1"},
)
check("in run + lead identity envelope -> deny", pretool_denied(out), str(out))
out, _ = run_hook(
    "orchestrator-claim-deny.py",
    {
        "tool_input": {
            "command": ('ACTOR="lead"; BEADS_ACTOR="$ACTOR" BD_ACTOR="$ACTOR" bd update x --claim')
        }
    },
    env={"ORCHESTRATE_RUN": "1"},
)
check("in run + lead hidden behind ACTOR -> deny", pretool_denied(out), str(out))
out, _ = run_hook(
    "orchestrator-claim-deny.py",
    {
        "tool_input": {
            "command": (
                "bd update x --claim "
                "BEADS_ACTOR=claude/researcher/session-123 "
                "BD_ACTOR=claude/researcher/session-123"
            )
        }
    },
    env={"ORCHESTRATE_RUN": "1"},
)
check(
    "in run + assignment-like claim arguments -> deny",
    pretool_denied(out),
    str(out),
)
out, _ = run_hook(
    "orchestrator-claim-deny.py",
    {
        "tool_input": {
            "command": (
                'BEADS_ACTOR="claude/researcher/session-123" '
                'BD_ACTOR="claude/researcher/session-123" bd update x --claim; '
                "bd update y --claim"
            )
        }
    },
    env={"ORCHESTRATE_RUN": "1"},
)
check("in run + one unbound claim -> deny all", pretool_denied(out), str(out))
# run marker + bd update without --claim -> allow
out, _ = run_hook(
    "orchestrator-claim-deny.py",
    {"tool_input": {"command": "bd update x --status open"}},
    env={"ORCHESTRATE_RUN": "1"},
)
check("in run + bd update (no claim) -> allow", out == {})
# run marker + non-bd command -> allow
out, _ = run_hook(
    "orchestrator-claim-deny.py",
    {"tool_input": {"command": "git commit -m x"}},
    env={"ORCHESTRATE_RUN": "1"},
)
check("in run + non-bd cmd -> allow", out == {})
# --claim inside an echo string must NOT deny (word-boundary / first-word check)
out, _ = run_hook(
    "orchestrator-claim-deny.py",
    {"tool_input": {"command": "echo 'bd update x --claim'"}},
    env={"ORCHESTRATE_RUN": "1"},
)
check("--claim inside echo -> allow (not a bd invocation)", out == {})
# malformed input -> allow (fail open)
out, proc = run_hook("orchestrator-claim-deny.py", {}, env={"ORCHESTRATE_RUN": "1"})
check("malformed/empty input -> allow (fail open)", out == {})

print("=== fixture 7 activation and resource regression ===")
with tempfile.TemporaryDirectory(prefix="orchestrate-hook-smoke-") as temp_dir:
    temp = Path(temp_dir)
    marker = temp / ".orchestration" / ".active-run"
    fake_bd = temp / "bd"
    fake_bd.write_text(
        """#!/usr/bin/env python3
import json
import sys

resources = {
    "orc-run.1": {
        "id": "orc-run.1",
        "status": "open",
        "assignee": "",
        "metadata": {
            "worktree": "/tmp/research-1",
            "lease_token": "lease-1",
            "runtime_handle": "researcher-r1@session-b807e068",
            "runtime_context": "aresearcher-r1-cb8a2c084ff1c7fa",
        },
    },
    "orc-run.no-context": {
        "id": "orc-run.no-context",
        "status": "open",
        "assignee": "",
        "metadata": {
            "worktree": "/tmp/research-1",
            "lease_token": "lease-1",
            "runtime_handle": "researcher-missing-context@session-b807e068",
        },
    },
    "orc-run.no-handle": {
        "id": "orc-run.no-handle",
        "status": "open",
        "assignee": "",
        "metadata": {
            "worktree": "/tmp/research-1",
            "lease_token": "lease-1",
            "runtime_context": "aresearcher-missing-handle",
        },
    },
}
resource_id = sys.argv[2] if len(sys.argv) > 2 else ""
record = resources.get(resource_id)
if record is None:
    raise SystemExit(1)
print(json.dumps({"schema_version": 1, "data": [record], "error": None}))
""",
        encoding="utf-8",
    )
    fake_bd.chmod(0o755)
    hook_env = {
        "BD_BIN": str(fake_bd),
        "ORCHESTRATE_MARKER_FILE": str(marker),
    }

    out, _ = run_hook(
        "orchestrator-run-activate.py",
        {"prompt": "Please inspect alpha.txt", "session_id": "session-ordinary"},
        env=hook_env,
    )
    check("ordinary prompt -> no activation marker", out == {} and not marker.exists(), str(out))

    out, _ = run_hook(
        "orchestrator-run-activate.py",
        {"prompt": "/orchestrate Inspect alpha.txt", "session_id": "session-claude"},
        env=hook_env,
    )
    marker_state = json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else {}
    check(
        "/orchestrate prompt -> activation marker",
        out == {}
        and marker_state.get("run_id") == "pending"
        and marker_state.get("session_id") == "session-claude",
        str(marker_state),
    )

    wait_prompt = (
        "WAIT checkout=/tmp/research-1\n"
        "RESOURCE orc-run.1\n"
        "Do not invoke tools or start work.\n"
        "The controlling parent will release you with exactly CLAIM orc-run.1."
    )
    out, _ = run_hook(
        "orchestrator-activation-guard.py",
        {
            "tool_name": "Agent",
            "tool_input": {
                "subagent_type": "researcher",
                "prompt": wait_prompt,
            },
        },
        env=hook_env,
    )
    check("pending run marker blocks dispatch", pretool_denied(out), str(out))

    bind = subprocess.run(
        [
            "uv",
            "run",
            "--quiet",
            os.path.join(HERE, "orchestrator-run-activate.py"),
            "bind",
            "orc-run",
        ],
        capture_output=True,
        text=True,
        env={**os.environ, **hook_env},
    )
    marker_state = json.loads(marker.read_text(encoding="utf-8"))
    check(
        "run bind replaces pending marker before dispatch",
        bind.returncode == 0
        and marker_state.get("run_id") == "orc-run"
        and marker_state.get("session_id") == "session-claude",
        f"returncode={bind.returncode} stdout={bind.stdout!r} stderr={bind.stderr!r} "
        f"state={marker_state}",
    )

    marker.write_text(
        json.dumps({"schema_version": 1, "run_id": "orc-existing"}) + "\n",
        encoding="utf-8",
    )
    out, _ = run_hook(
        "orchestrator-run-activate.py",
        {"prompt": "$orchestrate Resume the run", "thread_id": "thread-codex"},
        env=hook_env,
    )
    marker_state = json.loads(marker.read_text(encoding="utf-8"))
    check(
        "$orchestrate prompt -> preserves durable run id",
        out == {}
        and marker_state.get("run_id") == "orc-existing"
        and marker_state.get("session_id") == "thread-codex",
        str(marker_state),
    )

    out, _ = run_hook(
        "orchestrator-activation-guard.py",
        {
            "tool_name": "Agent",
            "tool_input": {
                "subagent_type": "researcher",
                "prompt": (
                    "Report the exact contents and SHA-256 digest of alpha.txt "
                    "and beta.txt. Validate each result independently."
                ),
            },
        },
        env=hook_env,
    )
    check("fixture 7 task-bearing spawn -> deny", pretool_denied(out), str(out))

    out, _ = run_hook(
        "orchestrator-activation-guard.py",
        {
            "tool_name": "Agent",
            "tool_input": {
                "subagent_type": "researcher",
                "prompt": wait_prompt,
            },
        },
        env=hook_env,
    )
    check("canonical checkout WAIT on live resource -> allow", out == {}, str(out))

    out, _ = run_hook(
        "orchestrator-activation-guard.py",
        {
            "tool_name": "Agent",
            "tool_input": {
                "subagent_type": "researcher",
                "prompt": wait_prompt + "\nTask: inspect both files.",
            },
        },
        env=hook_env,
    )
    check("WAIT with appended task data -> deny", pretool_denied(out), str(out))

    # An unrecognised agent type must not skip activation. A stale workflow-*
    # agent from an older release ran a whole fixture unguarded that way: the
    # WAIT, resource, exact-CLAIM and bound-marker checks all no-opped.
    for stale_type in ("workflow-researcher", "totally-made-up"):
        out, _ = run_hook(
            "orchestrator-activation-guard.py",
            {
                "tool_name": "Agent",
                "tool_input": {"subagent_type": stale_type, "prompt": "go do the work."},
            },
            env=hook_env,
        )
        check(
            f"unrecognised agent type {stale_type} -> deny",
            pretool_denied(out),
            str(out),
        )

    for ephemeral in ("general-purpose", "Explore", "docs-guard"):
        out, _ = run_hook(
            "orchestrator-activation-guard.py",
            {
                "tool_name": "Agent",
                "tool_input": {"subagent_type": ephemeral, "prompt": "summarize the notes."},
            },
            env=hook_env,
        )
        check(f"ephemeral helper {ephemeral} -> allow", out == {}, str(out))

    out, _ = run_hook(
        "orchestrator-activation-guard.py",
        {
            "tool_name": "Agent",
            "tool_input": {
                "subagent_type": "researcher",
                "prompt": (
                    wait_prompt + "\n\nImportant execution note for when you are later released: "
                    "every Bash call must begin with cd -- /tmp/research-1."
                ),
            },
        },
        env=hook_env,
    )
    check("WAIT with appended execution mechanics -> deny", pretool_denied(out), str(out))

    out, _ = run_hook(
        "orchestrator-activation-guard.py",
        {
            "tool_name": "Agent",
            "tool_input": {
                "subagent_type": "advisor",
                "prompt": (
                    "WAIT\n"
                    "RESOURCE orc-run.1\n"
                    "Do not invoke tools or start work.\n"
                    "The controlling parent will release you with exactly "
                    "CLAIM orc-run.1."
                ),
            },
        },
        env=hook_env,
    )
    check("checkout-exempt claim-holder WAIT -> deny", pretool_denied(out), str(out))

    out, _ = run_hook(
        "orchestrator-activation-guard.py",
        {
            "tool_name": "Agent",
            "tool_input": {
                "subagent_type": "shepherd",
                "prompt": (
                    "WAIT checkout=/tmp/shepherd-integration\n"
                    "QUEUE agent:integrator\n"
                    "Do not invoke tools or start work.\n"
                    "The controlling parent will release you with exactly "
                    "CLAIM queue:agent:integrator."
                ),
            },
        },
        env=hook_env,
    )
    check("checkout-backed queue WAIT -> allow", out == {}, str(out))

    out, _ = run_hook(
        "orchestrator-activation-guard.py",
        {
            "tool_name": "SendMessage",
            "tool_input": {"target": "agent-123", "message": "CLAIM lease-smk-bgf-a"},
        },
        env=hook_env,
    )
    check("missing lease-like CLAIM resource -> deny", pretool_denied(out), str(out))

    out, _ = run_hook(
        "orchestrator-activation-guard.py",
        {
            "tool_name": "SendMessage",
            "tool_input": {"target": "agent-wrong", "message": "CLAIM orc-run.1"},
        },
        env=hook_env,
    )
    check("CLAIM with wrong routing handle -> deny", pretool_denied(out), str(out))

    out, _ = run_hook(
        "orchestrator-activation-guard.py",
        {
            "tool_name": "followup_task",
            "tool_input": {
                "target": "researcher-r1@session-b807e068",
                "message": "CLAIM orc-run.1",
            },
        },
        env=hook_env,
    )
    check("Codex followup with distinct handle and hook context -> allow", out == {}, str(out))

    out, _ = run_hook(
        "orchestrator-activation-guard.py",
        {
            "tool_name": "send_input",
            "tool_input": {
                "id": "researcher-r1@session-b807e068",
                "message": "CLAIM orc-run.1",
            },
        },
        env=hook_env,
    )
    check("Codex legacy send_input id resolves bound handle -> allow", out == {}, str(out))

    out, _ = run_hook(
        "orchestrator-activation-guard.py",
        {
            "tool_name": "multi_agent_v1send_input",
            "tool_input": {
                "target": "researcher-r1@session-b807e068",
                "message": "CLAIM orc-run.1",
            },
        },
        env=hook_env,
    )
    check("Codex v1 namespaced send_input resolves bound handle -> allow", out == {}, str(out))

    out, _ = run_hook(
        "orchestrator-activation-guard.py",
        {
            "tool_name": "send_input",
            "tool_input": {
                "id": "researcher-missing-context@session-b807e068",
                "message": "CLAIM orc-run.no-context",
            },
        },
        env=hook_env,
    )
    check("Codex send_input CLAIM without context handshake -> deny", pretool_denied(out), str(out))

    out, _ = run_hook(
        "orchestrator-activation-guard.py",
        {
            "tool_name": "SendMessage",
            "tool_input": {
                "target": "aresearcher-missing-handle",
                "message": "CLAIM orc-run.no-handle",
            },
        },
        env=hook_env,
    )
    check("CLAIM without routing handle -> deny", pretool_denied(out), str(out))

    out, _ = run_hook(
        "orchestrator-activation-guard.py",
        {
            "tool_name": "SendMessage",
            "tool_input": {
                "target": "researcher-r1@session-b807e068",
                "message": "CLAIM orc-run.1\nInspect alpha.txt.",
            },
        },
        env=hook_env,
    )
    check("CLAIM with appended task data -> deny", pretool_denied(out), str(out))

    out, _ = run_hook(
        "orchestrator-activation-guard.py",
        {
            "tool_name": "Agent",
            "tool_input": {
                "subagent_type": "researcher",
                "prompt": "CLAIM orc-run.1",
            },
        },
        env={"ORCHESTRATE_MARKER_FILE": str(temp / "inactive-marker")},
    )
    check("direct CLAIM spawn outside run -> allow", out == {}, str(out))

print("=== hook JSON configs ===")
for cfg in ("orchestrate-claude-hooks.json", "orchestrate-codex-hooks.json"):
    path = os.path.join(HOOKS, cfg)
    try:
        with open(path) as fh:
            data = json.load(fh)
        ok = True
        refs = json.dumps(data)
        for script in (
            "contract-start.py",
            "rules-eval.py",
            "orchestrator-claim-deny.py",
            "orchestrator-activation-guard.py",
            "orchestrator-run-activate.py",
        ):
            if script in refs and not os.path.isfile(os.path.join(HERE, script)):
                ok = False
        check(f"{cfg} parses + refs exist", ok)
        commands = [
            hook["command"]
            for entries in data["hooks"].values()
            for entry in entries
            for hook in entry["hooks"]
        ]
        check(
            f"{cfg} anchors scripts at project root",
            all(command.startswith('cd "${CLAUDE_PROJECT_DIR:-.}" && ') for command in commands),
            str(commands),
        )
        stop_command = data["hooks"]["SubagentStop"][0]["hooks"][0]["command"]
        check(
            f"{cfg} deploys rules through a file marker",
            'RULES_DIR="$(dirname "${PLUGIN_ROOT}/.apm/rules/generic.rules.json")"' in stop_command,
            stop_command,
        )
        pre_tool_groups = data["hooks"]["PreToolUse"]
        activation_group = next(
            (group for group in pre_tool_groups if "Agent" in group.get("matcher", "")),
            {},
        )
        expected_delivery_matchers = (
            {"Agent", "SendMessage"}
            if "claude" in cfg
            else {
                "Agent",
                "send_message",
                "followup_task",
                "send_input",
                "multi_agent_v1send_input",
            }
        )
        actual_delivery_matchers = set(activation_group.get("matcher", "").split("|"))
        check(
            f"{cfg} guards claim-holder activation",
            actual_delivery_matchers == expected_delivery_matchers
            and any(
                "orchestrator-activation-guard.py" in hook.get("command", "")
                for hook in activation_group.get("hooks", [])
            ),
            str(activation_group),
        )
        prompt_hooks = data["hooks"].get("UserPromptSubmit", [])
        check(
            f"{cfg} activates enforcement on orchestrate prompt",
            any(
                "orchestrator-run-activate.py" in hook.get("command", "")
                for group in prompt_hooks
                for hook in group.get("hooks", [])
            ),
            str(prompt_hooks),
        )
    except Exception as e:
        check(f"{cfg} parses", False, str(e))

print("=== bead-as-brief source contract ===")
with open(os.path.join(SKILL, "references", "spawn-brief.md")) as fh:
    spawn_contract = fh.read()
normalized_spawn_contract = " ".join(spawn_contract.split())
check("spawn contract has no ASSIGN payload", "ASSIGN" not in spawn_contract)
check(
    "wait bootstrap names controlling CLAIM authority",
    "controlling parent will release you with exactly CLAIM" in spawn_contract,
)
check(
    "release is exact CLAIM activation",
    "Send exactly `CLAIM {bead-or-wisp-id}`" in spawn_contract,
)
check(
    "spawn and activation are separate messages",
    "Spawn and activation are separate operations." in normalized_spawn_contract
    and "Never repair an ordering failure with a combined WAIT plus CLAIM."
    in normalized_spawn_contract,
)

with open(os.path.join(SKILL, "references", "comms-block.md")) as fh:
    comms_contract = fh.read()
check("comms contract has no ASSIGN verb", "ASSIGN" not in comms_contract)
check(
    "comms permits bounded specialist children",
    "domain specialist may spawn bounded" in comms_contract,
)

with open(os.path.join(SKILL, "references", "planning.md")) as fh:
    planning_contract = fh.read()
check(
    "planning uses execution_kind for evidence contracts",
    "`execution_kind` metadata | `git`, `artifact`, `comment`, or `external`" in planning_contract,
)
check(
    "planning gives task routing a distinct metadata field",
    "`execution_task_kind` metadata" in planning_contract,
)

checkout_start_contract = "every claude bash input starts with the literal `cd -- <checkout> &&`"
for name in (
    "domain-specialist",
    "researcher",
    "reviewer",
    "advisor",
    "scribe",
    "shepherd",
):
    path = os.path.join(AGENTS, f"{name}.agent.md")
    with open(path) as fh:
        text = fh.read()
    normalized = " ".join(text.split())
    check(f"{name} has no ASSIGN activation", "ASSIGN" not in text)
    check(f"{name} names CLAIM activation", "CLAIM {" in text or "CLAIM <" in text)
    check(
        f"{name} makes checkout startup operational",
        checkout_start_contract in normalized.lower(),
    )
    check(
        f"{name} has no checkout-exempt claim path",
        "checkout-exempt" not in normalized,
    )

check(
    "landing keeps in-run shepherd distinct from pr-shepherd dependency",
    os.path.exists(os.path.join(AGENTS, "shepherd.agent.md"))
    and os.path.exists(
        os.path.abspath(os.path.join(HERE, "..", ".apm", "rules", "shepherd.rules.json"))
    ),
)

with open(os.path.join(SKILL, "references", "roles.md")) as fh:
    roles_contract = fh.read()
check(
    "shepherd uses a dedicated integration Worktrunk checkout",
    "dedicated integration Worktrunk checkout" in roles_contract
    and "remote-side (`gh`, merge-tree probes) - no worktree" not in roles_contract,
)

with open(os.path.join(AGENTS, "domain-specialist.agent.md")) as fh:
    specialist = fh.read()
check(
    "specialist claim sets stable Beads actor",
    'BEADS_ACTOR="$ACTOR" BD_ACTOR="$ACTOR" bd update "$BEAD_ID" --claim' in specialist,
)

print()
print(f"hooks smoke test: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
