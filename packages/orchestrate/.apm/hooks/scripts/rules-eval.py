#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""bead-as-brief contract evaluator (spec 002-bead-as-brief).

Shared SubagentStop evaluator for the claim<->contract enforcement layer. One
script, many per-agent JSON rules files. Reads a hook payload on stdin,
resolves the bead the stopping actor claims, loads that agent's rules file,
evaluates completion checklist + authority matrix + escape + bounce, and emits
the hook decision JSON on stdout.

CONTRACT (specs/002-bead-as-brief/contracts/):
  stdin  = SubagentStop hook payload JSON (agent_type, agent_id, ...)
           OR, for the conformance suite, {"_bead": {...}, "_rules_file": ...}.
  stdout = {} (allow) | {"decision":"block","reason":"<json str>"} (block)
  exit   = 0 always. Fail OPEN on any error (constitution III).

Zero third-party dependencies: rules files are JSON, payload is JSON. uv is the
runner (PEP 723) so inline deps can be added later without touching callers.

Predicate vocabulary (closed):
  "metadata.<key>"            metadata key present and non-empty
  "label ~ <regex>"           any label matches the (anchored) regex
  "comment.verb in [A,B]"     a comment's leading token is one of A,B
  "state in [A,B]"            bd status is one of A,B
"""
from __future__ import annotations
import json
import os
import re
import subprocess
import sys

BD = os.environ.get("BD_BIN", "bd")
RULES_DIR = os.environ.get("RULES_DIR", "")


def emit_allow() -> None:
    sys.stdout.write("{}\n")
    sys.exit(0)


def emit_block(reason: dict) -> None:
    sys.stdout.write(json.dumps({"decision": "block", "reason": json.dumps(reason)}) + "\n")
    sys.exit(0)


def read_payload() -> dict:
    try:
        raw = sys.stdin.read()
    except Exception:
        emit_allow()
    if not raw.strip():
        emit_allow()
    try:
        return json.loads(raw)
    except Exception:
        emit_allow()  # malformed -> fail open


def bd_json(*args) -> object:
    """Run a bd command expecting JSON; return parsed value or None."""
    try:
        out = subprocess.run([BD, *args], capture_output=True, text=True, timeout=20)
        if out.returncode != 0 or not out.stdout.strip():
            return None
        return json.loads(out.stdout)
    except Exception:
        return None


# ---- predicate evaluation -------------------------------------------------

def _labels(bead: dict) -> list:
    return bead.get("labels") or []


def _comment_verbs(bead: dict) -> list:
    verbs = []
    for c in bead.get("comments") or []:
        text = (c.get("text") or c.get("body") or "").strip()
        if text:
            verbs.append(text.split()[0].upper())
    return verbs


def _has_metadata(bead: dict, key: str) -> bool:
    v = (bead.get("metadata") or {}).get(key)
    return v is not None and v != ""


def eval_predicate(req: str, bead: dict) -> bool:
    """Evaluate one closed-vocabulary predicate. Unknown form -> True (fail open)."""
    req = req.strip()
    if req.startswith("metadata."):
        return _has_metadata(bead, req[len("metadata."):])
    if req.startswith("label ~ "):
        pat = req[len("label ~ "):].strip().strip('"')
        try:
            rx = re.compile(pat)
        except re.error:
            return True
        return any(rx.search(lbl) for lbl in _labels(bead))
    if req.startswith("comment.verb in "):
        wanted = _bracket_list(req)
        return any(v in wanted for v in _comment_verbs(bead))
    if req.startswith("state in "):
        wanted = _bracket_list(req)
        return _status(bead) in wanted
    return True  # unknown predicate -> do not fail the node


def _bracket_list(req: str) -> set:
    m = re.search(r"\[(.*)\]", req)
    if not m:
        return set()
    return {tok.strip() for tok in m.group(1).split(",") if tok.strip()}


def _status(bead: dict) -> str:
    # Built-in bd status is the single source of truth (no metadata.state mirror).
    return bead.get("status") or bead.get("state") or ""


# ---- main -----------------------------------------------------------------

def main() -> None:
    payload = read_payload()

    agent_type = payload.get("agent_type") or payload.get("agent") or ""
    agent_id = payload.get("agent_id") or ""

    # Fixture mode: payload carries the bead inline (conformance suite).
    fixture_bead = payload.get("_bead")
    rules_file = payload.get("_rules_file") or ""

    if fixture_bead is not None:
        bead = fixture_bead
        if not agent_type:
            agent_type = (bead.get("metadata") or {}).get("execution_agent") or ""
    else:
        if not agent_type:
            emit_allow()  # nothing to enforce
        actor = agent_id or agent_type
        claimed = bd_json("list", "--assignee", actor, "--status", "in_progress", "--json")
        if not isinstance(claimed, list) or not claimed:
            emit_allow()  # no claim -> no contract
        bead = claimed[0]
        # bd show/list carry no comments; fetch separately and splice.
        cid = bead.get("id")
        if cid:
            comments = bd_json("comments", cid, "--json")
            bead["comments"] = comments if isinstance(comments, list) else []

    if not bead:
        emit_allow()

    # Locate rules file. Per-agent file wins; otherwise the generic fallback
    # (so one matcher-less SubagentStop hook covers every claiming agent —
    # the "per-agent" distinction is data, not separate hook registrations,
    # which also avoids double stop_attempts increments).
    if not rules_file:
        if not RULES_DIR:
            emit_allow()
        cand = os.path.join(RULES_DIR, f"{agent_type}.rules.json")
        if os.path.isfile(cand):
            rules_file = cand
        else:
            generic = os.path.join(RULES_DIR, "generic.rules.json")
            if os.path.isfile(generic):
                rules_file = generic
    if not rules_file or not os.path.isfile(rules_file):
        emit_allow()  # no rules at all -> fail open

    try:
        with open(rules_file) as fh:
            rules = json.load(fh)
    except Exception:
        emit_allow()

    bead_id = bead.get("id", "?")
    status = _status(bead)

    # Escape hatch first.
    escape = rules.get("escape") or {}
    if escape.get("state") and status == escape["state"]:
        req = escape.get("require", "")
        if not req or eval_predicate(req, bead):
            emit_allow()

    node_kind = (bead.get("metadata") or {}).get("execution_kind")

    # Completion checklist.
    failed = []
    for chk in rules.get("completion") or []:
        when = chk.get("when")
        if when and node_kind and when != node_kind:
            continue
        if not eval_predicate(chk.get("require", ""), bead):
            failed.append({"check": chk.get("check", "?"),
                           "detail": f"unsatisfied: {chk.get('require','')}"})

    # Authority violations.
    violations = []
    authority = rules.get("authority") or {}
    for ds in authority.get("deny_states") or []:
        if status == ds:
            violations.append({"check": "state_authority",
                               "detail": f"status={ds} set by an agent forbidden to set it"})
    for dm in authority.get("deny_metadata") or []:
        if _has_metadata(bead, dm):
            violations.append({"check": "metadata_authority",
                               "detail": f"wrote forbidden metadata.{dm}"})

    if not failed and not violations:
        emit_allow()

    # Bounce.
    attempts = int((bead.get("metadata") or {}).get("stop_attempts") or 0)
    nxt = attempts + 1
    max_attempts = int((rules.get("bounce") or {}).get("max_attempts", 3))

    if nxt >= max_attempts:
        if fixture_bead is None:
            reason = json.dumps({"bead": bead_id, "agent": agent_type, "bounce": True,
                                 "attempt": nxt, "failed_checks": failed, "violations": violations})
            subprocess.run([BD, "comment", bead_id, f"BOUNCE agent={agent_type} attempt={nxt} {reason}"],
                           capture_output=True)
            subprocess.run([BD, "update", bead_id, "--assignee", "",
                            "--metadata", '{"stop_attempts":0,"review_round":0}'], capture_output=True)
        emit_allow()  # bounce force-allows

    if fixture_bead is None:
        subprocess.run([BD, "update", bead_id, "--metadata", f'{{"stop_attempts":{nxt}}}'],
                       capture_output=True)

    emit_block({"bead": bead_id, "agent": agent_type, "attempt": nxt,
                "failed_checks": failed, "violations": violations})


if __name__ == "__main__":
    main()
