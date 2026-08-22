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
  "linked.comment.verb in [A,B]"
                               a linked durable resource has one of A,B
  "state in [A,B]"            bd status is one of A,B
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

BD = os.environ.get("BD_BIN", "bd")
RULES_DIR = os.environ.get("RULES_DIR", "")

# Metadata keys the orchestrator stamps before the claim exists, per
# spawn-brief.md "Required node metadata". `deny_metadata` is presence-based:
# beads records no per-key writer (`bd show --json` carries no metadata field
# authorship, `bd history` is squashed, and the audit trail's `field_change`
# entries cover status/assignee/priority only), so a denied anchor blocks the
# role for a write the orchestrator made. Exempt them centrally instead of
# relying on every rules author to omit them (astro-plan-78v0).
ORCHESTRATOR_ANCHORS = frozenset(
    {
        "actor",
        "artifacts_dir",
        "base_ref",
        "base_sha",
        "branch",
        "complexity_tier",
        "execution_agent",
        "execution_dispatch",
        "execution_kind",
        "execution_task_kind",
        "lease_token",
        "runtime_context",
        "runtime_handle",
        "scope",
        "worktree",
    }
)


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
        env = {
            **os.environ,
            "BD_JSON_ENVELOPE": "1",
            "BD_NO_PAGER": "1",
            "BD_NON_INTERACTIVE": "1",
        }
        out = subprocess.run(
            [BD, *args],
            capture_output=True,
            text=True,
            timeout=20,
            env=env,
        )
        if out.returncode != 0 or not out.stdout.strip():
            return None
        payload = json.loads(out.stdout)
        if isinstance(payload, dict) and "schema_version" in payload:
            return payload.get("data")
        return payload
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
            verbs.append(_leading_verb(text))
    return verbs


def _linked_comment_verbs(bead: dict) -> list:
    verbs = []
    for c in bead.get("linked_comments") or []:
        text = (c.get("text") or c.get("body") or "").strip()
        if text:
            verbs.append(_leading_verb(text))
    return verbs


def _leading_verb(text: str) -> str:
    return text.split()[0].rstrip(":").upper()


def _has_metadata(bead: dict, key: str) -> bool:
    v = (bead.get("metadata") or {}).get(key)
    return v is not None and v != ""


def _artifact_output_ref_contained(bead: dict) -> bool:
    metadata = bead.get("metadata") or {}
    output_raw = metadata.get("output_ref")
    artifacts_raw = metadata.get("artifacts_dir")
    if not isinstance(output_raw, str) or not isinstance(artifacts_raw, str):
        return False
    output = Path(output_raw)
    artifacts = Path(artifacts_raw)
    if not output.is_absolute() or not artifacts.is_absolute():
        return False
    output = output.resolve()
    artifacts = artifacts.resolve()
    try:
        relative = output.relative_to(artifacts)
    except ValueError:
        return False
    if not relative.parts:
        return False

    worktree_raw = metadata.get("worktree")
    if isinstance(worktree_raw, str) and Path(worktree_raw).is_absolute():
        try:
            output.relative_to(Path(worktree_raw).resolve())
        except ValueError:
            pass
        else:
            return False
    return True


def eval_predicate(req: str, bead: dict) -> bool:
    """Evaluate one closed-vocabulary predicate. Unknown form -> True (fail open)."""
    req = req.strip()
    if req.startswith("metadata."):
        return _has_metadata(bead, req[len("metadata.") :])
    if req.startswith("label ~ "):
        pat = req[len("label ~ ") :].strip().strip('"')
        try:
            rx = re.compile(pat)
        except re.error:
            return True
        return any(rx.search(lbl) for lbl in _labels(bead))
    if req.startswith("comment.verb in "):
        wanted = _bracket_list(req)
        return any(v in wanted for v in _comment_verbs(bead))
    if req.startswith("linked.comment.verb in "):
        wanted = _bracket_list(req)
        return any(v in wanted for v in _linked_comment_verbs(bead))
    if req == "artifact.output_ref contained":
        return _artifact_output_ref_contained(bead)
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


def runtime_context(payload: dict) -> str:
    for key in ("agent_id", "subagent_id"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    if payload.get("agent_type") or payload.get("subagent_type"):
        value = payload.get("session_id")
        if isinstance(value, str) and value:
            return value
    return ""


def _resource_sort_key(issue: dict) -> tuple[str, str]:
    return (str(issue.get("updated_at") or ""), str(issue.get("id") or ""))


def _active_claim(issue: dict) -> bool:
    return issue.get("status") == "in_progress" and bool(issue.get("assignee"))


def _dedupe_resources(resources: list[dict]) -> list[dict]:
    by_id = {}
    for issue in resources:
        issue_id = issue.get("id")
        if issue_id:
            by_id[issue_id] = issue
    return list(by_id.values())


def resolve_claimed_bead(payload: dict, agent_type: str) -> tuple[dict | None, list[dict]]:
    context = runtime_context(payload)
    if context:
        resources = bd_json(
            "list",
            "--include-infra",
            "--all",
            "--json",
        )
        if isinstance(resources, list):
            matches = [
                issue
                for issue in resources
                if (issue.get("metadata") or {}).get("runtime_context") == context
            ]
            matches = _dedupe_resources(matches)
            if matches:
                active = [issue for issue in matches if _active_claim(issue)]
                selected = max(active or matches, key=_resource_sort_key)
                violations = []
                if active:
                    violations.append(
                        {
                            "check": "claim_release",
                            "detail": "active claims remain at stop: "
                            + ",".join(sorted(str(issue.get("id")) for issue in active)),
                        }
                    )
                return selected, violations

    for actor in dict.fromkeys(
        value
        for value in (
            payload.get("agent_id"),
            payload.get("subagent_id"),
            agent_type,
        )
        if isinstance(value, str) and value
    ):
        claimed = bd_json(
            "list",
            "--include-infra",
            "--assignee",
            actor,
            "--status",
            "open,in_progress,blocked",
            "--json",
        )
        if isinstance(claimed, list) and claimed:
            resources = _dedupe_resources(claimed)
            active = [issue for issue in resources if _active_claim(issue)]
            selected = max(active or resources, key=_resource_sort_key)
            violations = []
            if active:
                violations.append(
                    {
                        "check": "claim_release",
                        "detail": "active claims remain at stop: "
                        + ",".join(sorted(str(issue.get("id")) for issue in active)),
                    }
                )
            return selected, violations
    return None, []


def hydrate_comments(bead: dict) -> None:
    """Populate `comments` and `linked_comments` for predicate evaluation.

    `linked_comments` is populated for every bead, not only for ones carrying
    top-level `ephemeral`/`wisp_type`. Resource kind is also declarable through
    `metadata.execution_kind` (see `resource_kind`), and `reviewer` and `scribe`
    require `linked.comment.verb` unconditionally, so keying hydration on the
    top-level flags left those checks reading a permanently empty list -- a
    completion gate no agent could satisfy.
    """
    bead_id = bead.get("id")
    if not bead_id:
        return
    comments = bd_json("comments", bead_id, "--json")
    bead["comments"] = comments if isinstance(comments, list) else []

    shown = bd_json("show", bead_id, "--json")
    if isinstance(shown, list) and len(shown) == 1:
        shown = shown[0]
    if not isinstance(shown, dict):
        bead["linked_comments"] = []
        return

    linked_comments = []
    linked_ids = {
        link.get("id")
        for key in ("dependencies", "dependents")
        for link in (shown.get(key) or [])
        if link.get("id") and link.get("dependency_type") in {"relates-to", "replies-to"}
    }
    for linked_id in sorted(linked_ids):
        payload = bd_json("comments", linked_id, "--json")
        if isinstance(payload, list):
            linked_comments.extend(payload)
    bead["linked_comments"] = linked_comments


def resource_kind(bead: dict) -> str:
    metadata = bead.get("metadata") or {}
    return str(
        metadata.get("execution_kind")
        or bead.get("wisp_type")
        or ("wisp" if bead.get("ephemeral") else "")
    )


# ---- main -----------------------------------------------------------------


def main() -> None:
    payload = read_payload()

    agent_type = payload.get("agent_type") or payload.get("agent") or ""
    # Fixture mode: payload carries the bead inline (conformance suite).
    fixture_bead = payload.get("_bead")
    rules_file = payload.get("_rules_file") or ""

    if fixture_bead is not None:
        bead = fixture_bead
        resolution_violations = []
        if not agent_type:
            agent_type = (bead.get("metadata") or {}).get("execution_agent") or ""
    else:
        if not agent_type:
            emit_allow()  # nothing to enforce
        bead, resolution_violations = resolve_claimed_bead(payload, agent_type)
        if bead is None:
            emit_allow()  # no claim -> no contract
        hydrate_comments(bead)

    if not bead:
        emit_allow()

    # Locate rules file. Per-agent file wins; otherwise the generic fallback
    # (so one matcher-less SubagentStop hook covers every claiming agent —
    # the "per-agent" distinction is data, not separate hook registrations,
    # which also avoids double stop_attempts increments).
    if not rules_file:
        if not RULES_DIR:
            emit_allow()
        # Hardening: a RULES_DIR that is set but contains NO *.rules.json is
        # almost certainly a misconfigured deployment (wrong path), not a
        # legitimate unknown agent. Silently failing open would disable
        # enforcement invisibly — the exact trap the N7 fuzzer's own path bug
        # revealed. Warn on stderr (non-blocking; still fail open so a hook
        # never wedges an agent) so the breakage is visible.
        if not os.path.isdir(RULES_DIR) or not any(
            f.endswith(".rules.json") for f in os.listdir(RULES_DIR)
        ):
            sys.stderr.write(
                f"rules-eval: RULES_DIR={RULES_DIR!r} has no *.rules.json — "
                "contract enforcement DISABLED for this stop (misconfig?).\n"
            )
            emit_allow()
        cand = os.path.join(RULES_DIR, f"{agent_type}.rules.json")
        if os.path.isfile(cand):
            rules_file = cand
        else:
            generic = os.path.join(RULES_DIR, "generic.rules.json")
            if os.path.isfile(generic):
                rules_file = generic
    if not rules_file or not os.path.isfile(rules_file):
        emit_allow()  # no rules for this agent + no generic -> fail open

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

    node_kind = resource_kind(bead)

    # Completion checklist.
    failed = []
    for chk in rules.get("completion") or []:
        when = chk.get("when")
        if when:
            allowed_kinds = {when} if isinstance(when, str) else set(when)
            if node_kind not in allowed_kinds:
                continue
        if not eval_predicate(chk.get("require", ""), bead):
            failed.append(
                {"check": chk.get("check", "?"), "detail": f"unsatisfied: {chk.get('require', '')}"}
            )

    # Authority violations.
    violations = list(resolution_violations)
    authority = rules.get("authority") or {}
    for ds in authority.get("deny_states") or []:
        if status == ds:
            violations.append(
                {
                    "check": "state_authority",
                    "detail": f"status={ds} set by an agent forbidden to set it",
                }
            )
    for dm in authority.get("deny_metadata") or []:
        if dm in ORCHESTRATOR_ANCHORS:
            continue
        if _has_metadata(bead, dm):
            violations.append(
                {
                    "check": "metadata_authority",
                    "detail": (
                        f"metadata.{dm} is set and this role may not own it; unset it or escalate"
                    ),
                }
            )

    if not failed and not violations:
        emit_allow()

    # Bounce.
    attempts = int((bead.get("metadata") or {}).get("stop_attempts") or 0)
    nxt = attempts + 1
    max_attempts = int((rules.get("bounce") or {}).get("max_attempts", 3))

    if nxt >= max_attempts:
        if fixture_bead is None:
            reason = json.dumps(
                {
                    "bead": bead_id,
                    "agent": agent_type,
                    "bounce": True,
                    "attempt": nxt,
                    "failed_checks": failed,
                    "violations": violations,
                }
            )
            subprocess.run(
                [BD, "comment", bead_id, f"BOUNCE agent={agent_type} attempt={nxt} {reason}"],
                capture_output=True,
            )
            if status == "closed":
                subprocess.run(
                    [BD, "reopen", bead_id, "--reason", "contract bounce"],
                    capture_output=True,
                )
            subprocess.run(
                [
                    BD,
                    "update",
                    bead_id,
                    "--assignee",
                    "",
                    "--status",
                    "open",
                    "--metadata",
                    '{"stop_attempts":0,"review_round":0}',
                ],
                capture_output=True,
            )
        emit_allow()  # bounce force-allows

    if fixture_bead is None:
        subprocess.run(
            [BD, "update", bead_id, "--metadata", f'{{"stop_attempts":{nxt}}}'], capture_output=True
        )

    emit_block(
        {
            "bead": bead_id,
            "agent": agent_type,
            "attempt": nxt,
            "failed_checks": failed,
            "violations": violations,
        }
    )


if __name__ == "__main__":
    main()
