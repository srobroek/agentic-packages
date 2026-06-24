#!/usr/bin/env python3
"""SpecKit DAG dispatcher (stdlib-only).

Ported from dispatcher.sh. Wired through .apm/hooks/speckit-{claude,codex}-hooks.json:
  Claude: UserPromptExpansion - PreToolUse:Skill - PostToolUse:Skill
  Codex:  UserPromptSubmit - PreToolUse - PostToolUse

Invocation (see the hook JSON): both this script AND the nodes.json data file are
referenced via ${PLUGIN_ROOT} inside the hook *command* string, because APM only
copies + path-rewrites ${PLUGIN_ROOT} refs found in `command` (never in `args`).
The hook command is therefore:

    python3 ${PLUGIN_ROOT}/scripts/dispatcher.py ${PLUGIN_ROOT}/scripts/nodes.json

with the phase passed via `args` (["pre"] or ["post"]). Because both the command
tokens and the args array arrive as argv, this script scans argv (order-
independently) for the .json path and for the pre/post phase token rather than
assuming fixed positions.

Pre  -> reads node "<id>" pre phase (came_from + preconditions), evaluates
        hard_deprecated / hard_missing / hard_exists, either blocks the
        invocation or injects the rendered body as additionalContext.
Post -> reads node "<id>" post phase (going_to + postconditions + conditional
        branching), injects the rendered body as additionalContext.

No state file. <feat> resolves via SpecKit's canonical 3-tier priority. Missing
nodes = silent no-op. All node guidance lives in the hand-authored, structured
scripts/nodes.json (single editable source); this file renders the injected
markdown from those structured fields so it stays equivalent to the old node
bodies.
"""

from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys


# ---------------------------------------------------------------------------
# argv parsing: tokens from the hook `command` string and the `args` array both
# arrive in sys.argv. Find the nodes.json path and the phase regardless of order.
# ---------------------------------------------------------------------------
def _parse_argv(argv):
    nodes_path = None
    phase = "pre"
    for arg in argv[1:]:
        if arg in ("pre", "post"):
            phase = arg
        elif arg.endswith(".json"):
            nodes_path = arg
    return phase, nodes_path


def _load_nodes(nodes_path):
    if not nodes_path or not os.path.isfile(nodes_path):
        return {}
    try:
        with open(nodes_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# Body rendering: turn a structured node phase dict back into the markdown that
# the old nodes/*.md bodies injected as additionalContext.
# ---------------------------------------------------------------------------
def _render_section(heading, bullets):
    lines = ["## " + heading]
    for b in bullets:
        lines.append("- " + b)
    return "\n".join(lines)


def render_body(phase, node):
    """Render a node phase dict to markdown (byte-faithful to the old .md)."""
    parts = ["# " + node["title"]]

    if phase == "pre":
        if "came_from" in node:
            parts.append(_render_section("Came from", node["came_from"]))
        # Preconditions: hard_missing, then hard_exists, then hard_deprecated,
        # then soft -- matching the source ordering.
        precond = []
        for tmpl in node.get("hard_missing", []):
            precond.append("HARD-MISSING: " + tmpl)
        for tmpl in node.get("hard_exists", []):
            precond.append("HARD-EXISTS: " + tmpl)
        for tmpl in node.get("hard_deprecated", []):
            precond.append("HARD-DEPRECATED: " + tmpl)
        for s in node.get("soft", []):
            # A bare "(none)" style bullet has no SOFT: prefix; everything else
            # was authored as "SOFT: ...".
            if s.startswith("(") or s == "(none)":
                precond.append(s)
            else:
                precond.append("SOFT: " + s)
        if "soft" in node:  # Preconditions section was present in source
            parts.append(_render_section("Preconditions", precond))
        if "context" in node:
            parts.append(
                _render_section("Context absorbed from steering", node["context"])
            )
    else:  # post
        if "going_to" in node:
            parts.append(_render_section("Going to", node["going_to"]))
        if "postconditions" in node:
            parts.append(_render_section("Postconditions", node["postconditions"]))
        if "context" in node:
            parts.append(
                _render_section("Context absorbed from steering", node["context"])
            )
        if "conditional" in node:
            parts.append(
                _render_section("Conditional branching", node["conditional"])
            )

    body = "\n\n".join(parts)
    return body + "\n"


# ---------------------------------------------------------------------------
# Event / command extraction.
# ---------------------------------------------------------------------------
def _resolve_command(event, payload):
    """Extract the speckit command string from the event payload."""
    if event == "UserPromptExpansion":
        return payload.get("command_name") or ""
    if event in ("PreToolUse", "PostToolUse"):
        tool_input = payload.get("tool_input") or {}
        cmd = tool_input.get("skill") or tool_input.get("command_name") or ""
        if cmd:
            return cmd
        # Codex PreToolUse/PostToolUse may not carry a skill; try the prompt.
        return _parse_speckit_slash(tool_input.get("prompt") or "")
    if event == "UserPromptSubmit":
        return _parse_speckit_slash(payload.get("prompt") or "")
    return ""


def _parse_speckit_slash(text):
    """Find the first /speckit.X token in text and strip the leading slash."""
    match = re.search(r"/speckit\.[a-z][a-z0-9.\-]*", text)
    if not match:
        return ""
    return match.group(0).lstrip("/")


def _normalize(cmd):
    """speckit-foo-bar / speckit.foo.bar -> foo-bar; dots -> hyphens.

    DAG node ids use dots as segment separators but keep intra-segment
    hyphens (agent-assign.execute). The nodes.json keys are stored already
    normalised to hyphens (agent-assign-execute), so we match by converting
    dots to hyphens here too.
    """
    raw = cmd
    if raw.startswith("speckit-"):
        raw = raw[len("speckit-"):]
    if raw.startswith("speckit."):
        raw = raw[len("speckit."):]
    if not raw:
        return ""
    return raw.replace(".", "-")


def _find_speckit_root(start):
    """Walk up from `start` to the nearest ancestor that holds a SpecKit root.

    A SpecKit root is the directory that owns `.specify/` (and `specs/`). This
    handles an agent whose cwd is a subdirectory of the project (e.g. frontend/)
    by locating the directory where feature.json and specs/ actually live.
    Returns "" when no ancestor qualifies.
    """
    if not start:
        return ""
    cur = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(cur, ".specify")) or os.path.isdir(
            os.path.join(cur, "specs")
        ):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return ""
        cur = parent


def _resolve_proj_root(payload):
    """Resolve the project root from the INVOKING AGENT's working directory.

    Claude/Codex hook payloads carry `cwd` -- the working directory of the
    session or subagent that triggered the hook. In a git worktree this is the
    worktree path (and `os.getcwd()` agrees, since Claude runs hooks from there).
    CLAUDE_PROJECT_DIR, by contrast, is pinned to the directory Claude Code was
    *launched* in -- typically a sibling checkout on a different feature branch.
    Preferring `cwd` keeps SpecKit feature resolution from leaking across
    worktrees; CLAUDE_PROJECT_DIR is only a last-resort fallback. We then walk up
    to the directory that owns `.specify/`/`specs/` so subdirectory cwds resolve.
    """
    cwd = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    if not isinstance(cwd, str) or not os.path.isdir(cwd):
        cwd = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return _find_speckit_root(cwd) or cwd


def _resolve_node_id(node_id, nodes):
    """Map a normalized command id to the best-matching node key.

    Exact match wins, which preserves the intentional per-subcommand nodes
    (review-run, optimize-tokens, qa-run, ...). Otherwise we strip trailing
    "-<segment>" groups until a node exists. This absorbs spec-kit's command
    naming where the invocable id carries a verb suffix or sub-namespace the
    DAG models at the parent level:

        verify.run            -> verify-run        -> verify
        verify-tasks.run      -> verify-tasks-run  -> verify-tasks
        cleanup.run           -> cleanup-run       -> cleanup
        fix-findings.run      -> fix-findings-run  -> fix-findings
        security-review.audit -> security-review-audit -> security-review

    Node existence disambiguates the hyphen's double duty (verify-tasks-run
    resolves to verify-tasks, not verify, because verify-tasks is a real node).
    Returns the resolved key, or "" when nothing matches (silent no-op).
    """
    if node_id in nodes:
        return node_id
    parts = node_id.split("-")
    while len(parts) > 1:
        parts.pop()
        candidate = "-".join(parts)
        if candidate in nodes:
            return candidate
    return ""


def _resolve_feat(proj_root):
    """SpecKit 3-tier <feat> resolution. Returns "" if none resolve."""
    env_dir = os.environ.get("SPECIFY_FEATURE_DIRECTORY")
    if env_dir:
        feat = env_dir
        if feat.startswith("specs/"):
            feat = feat[len("specs/"):]
        return feat.rstrip("/")

    feature_json = os.path.join(proj_root, ".specify", "feature.json")
    if os.path.isfile(feature_json):
        try:
            with open(feature_json, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            feat = data.get("feature_directory") or "" if isinstance(data, dict) else ""
        except (OSError, ValueError):
            feat = ""
        if feat:
            if feat.startswith("specs/"):
                feat = feat[len("specs/"):]
            return feat.rstrip("/")

    # Tier 3: branch-name prefix lookup. Branch "001-foo" -> specs/001-foo/.
    git_dir = os.path.join(proj_root, ".git")
    if os.path.isdir(git_dir) or os.path.isfile(git_dir):
        try:
            branch = subprocess.check_output(
                ["git", "-C", proj_root, "rev-parse", "--abbrev-ref", "HEAD"],
                stderr=subprocess.DEVNULL,
            ).decode("utf-8", "replace").strip()
        except (OSError, subprocess.CalledProcessError):
            branch = ""
        if branch and os.path.isdir(os.path.join(proj_root, "specs", branch)):
            return branch
    return ""


# ---------------------------------------------------------------------------
# Hard-rule evaluation. Operates on the explicit structured arrays. First match
# wins, preserving the bash dispatcher's order: deprecated, then missing, then
# exists (which is also the order they appear within a Preconditions block).
# ---------------------------------------------------------------------------
def _subst(tmpl, feat):
    return tmpl.replace("<feat>", feat)


def _resolve_path(tmpl, feat, proj_root):
    path = _subst(tmpl, feat)
    if not os.path.isabs(path):
        path = os.path.join(proj_root, path)
    return path


def _path_present(path):
    """True when `path` exists.

    Precondition templates may carry glob metacharacters (e.g. `bug-*.md`,
    one per numbered artefact). For those, match as a wildcard instead of
    looking for a file literally named with the asterisk -- os.path.exists on
    `bug-*.md` can never match a real `bug-1.md`.
    """
    if any(ch in path for ch in "*?["):
        return bool(glob.glob(path))
    return os.path.exists(path)


def _evaluate_block(node, feat, proj_root):
    """Return a block reason string, or "" if nothing blocks."""
    for reason in node.get("hard_deprecated", []):
        # Deprecated always blocks, regardless of feat.
        return reason
    for tmpl in node.get("hard_missing", []):
        # A <feat>-scoped precondition with no resolvable feature is the most
        # out-of-order case of all: block with guidance instead of silently
        # skipping the check (the old behaviour, which let the command run and
        # fail confusingly downstream).
        if "<feat>" in tmpl and not feat:
            return (
                "No active SpecKit feature resolved (no"
                " SPECIFY_FEATURE_DIRECTORY, .specify/feature.json, or"
                " specs/<branch>/ match) -- run /speckit.specify first or"
                " switch to the feature branch"
            )
        path = _resolve_path(tmpl, feat, proj_root)
        if not _path_present(path):
            return "Required artefact missing: " + path
    for tmpl in node.get("hard_exists", []):
        if "<feat>" in tmpl and not feat:
            continue  # cannot conflict when no feature exists yet
        path = _resolve_path(tmpl, feat, proj_root)
        if _path_present(path):
            return (
                "Conflicting artefact present: " + path
                + " -- use /speckit.refine.update to amend instead of"
                + " re-running this step"
            )
    return ""


def main():
    payload_text = sys.stdin.read()
    phase, nodes_path = _parse_argv(sys.argv)

    try:
        payload = json.loads(payload_text) if payload_text.strip() else {}
    except ValueError:
        return 0
    if not isinstance(payload, dict):
        return 0

    event = payload.get("hook_event_name") or ""
    if event not in (
        "UserPromptExpansion",
        "PreToolUse",
        "PostToolUse",
        "UserPromptSubmit",
    ):
        return 0

    cmd = _resolve_command(event, payload)
    if not cmd:
        return 0

    node_id = _normalize(cmd)
    if not node_id:
        return 0

    nodes = _load_nodes(nodes_path)
    node_id = _resolve_node_id(node_id, nodes)
    if not node_id:
        return 0
    node_entry = nodes.get(node_id)
    if not isinstance(node_entry, dict):
        return 0
    node = node_entry.get(phase)
    if not isinstance(node, dict):
        return 0

    node_body = render_body(phase, node)

    proj_root = _resolve_proj_root(payload)
    feat = _resolve_feat(proj_root)

    if phase == "pre":
        block_reason = _evaluate_block(node, feat, proj_root)
        if block_reason:
            if event in ("UserPromptExpansion", "UserPromptSubmit"):
                out = {
                    "decision": "block",
                    "reason": block_reason,
                    "hookSpecificOutput": {
                        "hookEventName": event,
                        "additionalContext": node_body,
                    },
                }
            elif event == "PreToolUse":
                out = {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": block_reason,
                        "additionalContext": node_body,
                    },
                }
            else:
                # PostToolUse never reaches here (phase == "pre"), but be safe.
                out = {
                    "hookSpecificOutput": {
                        "hookEventName": event,
                        "additionalContext": node_body,
                    },
                }
            sys.stdout.write(json.dumps(out, indent=2))
            sys.stdout.write("\n")
            return 0

    # Soft injection: pre passed without block, OR post phase always.
    out = {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": node_body,
        },
    }
    sys.stdout.write(json.dumps(out, indent=2))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
