#!/usr/bin/env python3
"""orchestrate: forensic run ledger (JSONL, stdlib-only).

Append-only audit trail for a multi-agent run. The script owns the write path so
agents never hand-format timestamps or sequence numbers, and reads are
deterministic filters rather than grep. Designed so a run can be reproduced and
debugged in hindsight: every step records its input brief, output report, result,
issues, and anything unexpected, plus durable git anchors.

Store layout (shared, outside every worktree):
    <store>/ledger.jsonl
    <store>/artifacts/<seq>-input.md
    <store>/artifacts/<seq>-output.md

`--store` MUST be an absolute path (same rule as graph.py) -- a relative path
would resolve against the caller's cwd, often a worktree, silently creating an
orphan store instead of sharing the run's real one.

The script stamps ts (UTC), run_id, seq; warns (does not die) on an event
outside the canonical vocabulary; writes any --input-file/--output-file into
artifacts/ and records the *_ref; then flock-appends one JSON line. Prefer
--input-file/--output-file for real briefs/reports -- the file's full text
always becomes the artifact of record. Plain --input/--output text is for
short inline notes only: anything over 200 chars is still written whole to the
artifact, but the in-row `input`/`output` field is truncated to its first 200
chars so full payloads stop round-tripping through every query.

Add:
    ledger.py --store D add --event reported --actor coder-t3 --role coder \
        --model sonnet --node t3 --state in_review \
        --branch coder/t3 --worktree /path/to/wt --commit a1b2c3d \
        --pushed origin/coder/t3 \
        --input-file brief.md --output-file report.md \
        --result "green" --issue "..." --unexpected "..." --ref reviewer-t3

Read (deterministic, no grep):
    ledger.py --store D query [--node t3] [--actor A] [--event E] [--state S]
              [--since SEQ] [--fields a,b,c] [--json|--table]
    ledger.py --store D timeline --node t3
    ledger.py --store D replay --node t3          # brief->output->result chain + artifacts
    ledger.py --store D summary [--json]
    ledger.py --store D issues [--json]           # every issues[]+unexpected[]
    ledger.py --store D agents [--json]           # per-actor activity
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

# Canonical event vocabulary: the 11 message verbs, lowercased, plus two
# ledger-only bookkeeping events. Unknown events are a warning, not a die --
# one truncated/misnamed event should never break the whole run's audit trail.
EVENTS = {
    "assign", "blocked", "advice", "reported", "review", "fix", "conflict",
    "approve", "merged", "dismiss", "ask", "failed", "note",
}

INLINE_LIMIT = 200


def _ledger_path(store: str) -> str:
    return os.path.join(store, "ledger.jsonl")


def _die(msg: str, code: int = 2) -> None:
    print(f"ledger.py: {msg}", file=sys.stderr)
    sys.exit(code)


def _read_all(store: str) -> list[dict]:
    """Read every ledger row, skipping (not raising on) unparsable lines --
    one truncated/garbage trailing line must never break every read command.
    Emits a single stderr warning with the count if any were skipped."""
    path = _ledger_path(store)
    if not os.path.exists(path):
        return []
    rows = []
    bad = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                bad += 1
    if bad:
        print(f"ledger.py: warning: skipped {bad} unparsable ledger line(s)", file=sys.stderr)
    return rows


def _next_seq(rows: list[dict]) -> int:
    return (max((r.get("seq", 0) for r in rows), default=0)) + 1


def _run_id(store: str, rows: list[dict], override: str | None) -> str:
    if override:
        return override
    for r in rows:
        if r.get("run_id"):
            return r["run_id"]
    # fall back to the graph's run_id if present, else the store dir name
    gpath = os.path.join(store, "graph.json")
    if os.path.exists(gpath):
        try:
            with open(gpath, encoding="utf-8") as fh:
                rid = json.load(fh).get("run_id")
                if rid:
                    return rid
        except (OSError, ValueError):
            pass
    return os.path.basename(os.path.normpath(store))


def _write_artifact(store: str, seq: int, kind: str, text: str | None, path: str | None) -> str | None:
    if not text and not path:
        return None
    if path:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    art_dir = os.path.join(store, "artifacts")
    os.makedirs(art_dir, exist_ok=True)
    name = f"{seq:04d}-{kind}.md"
    with open(os.path.join(art_dir, name), "w", encoding="utf-8") as fh:
        fh.write(text or "")
    return os.path.join("artifacts", name)


def _row_text(value: str | None, file_path: str | None) -> str | None:
    """The in-row summary for input/output: a file placeholder when a file was
    given, else the inline text capped at INLINE_LIMIT chars. The full text
    always lives in the artifact (see _write_artifact / *_ref)."""
    if file_path:
        return f"(file:{os.path.basename(file_path)})"
    if value is None:
        return None
    return value[:INLINE_LIMIT]


def cmd_add(args) -> None:
    import fcntl

    if args.event not in EVENTS:
        print(f"ledger.py: warning: unknown event {args.event!r}; canonical: {sorted(EVENTS)}",
              file=sys.stderr)
    os.makedirs(args.store, exist_ok=True)
    lock_path = os.path.join(args.store, ".ledger.lock")
    with open(lock_path, "w", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        rows = _read_all(args.store)
        seq = _next_seq(rows)
        run_id = _run_id(args.store, rows, args.run_id)
        input_ref = _write_artifact(args.store, seq, "input", args.input, args.input_file)
        output_ref = _write_artifact(args.store, seq, "output", args.output, args.output_file)
        rec = {
            "ts": datetime.datetime.now(datetime.timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "run_id": run_id,
            "seq": seq,
            "event": args.event,
            "actor": args.actor,
            "role": args.role,
            "model": args.model,
            "effort": args.effort,
            "parent": args.parent,
            "node": args.node,
            "state": args.state,
            "base": args.base,
            "branch": args.branch,
            "commits": args.commit or [],
            "pushed": args.pushed,
            "pr": args.pr,
            "merge_sha": args.merge_sha,
            "worktree": args.worktree,
            "input": _row_text(args.input, args.input_file),
            "input_ref": input_ref,
            "output": _row_text(args.output, args.output_file),
            "output_ref": output_ref,
            "result": args.result,
            "issues": args.issue or [],
            "unexpected": args.unexpected or [],
            "refs": args.ref or [],
            "artifacts": args.artifact or [],
        }
        with open(_ledger_path(args.store), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
    print(f"seq={seq} {args.event} {args.node or ''} {args.actor or ''}")


def _filter(rows, args):
    def keep(r):
        if args.node and r.get("node") != args.node:
            return False
        if args.actor and r.get("actor") != args.actor:
            return False
        if args.event and r.get("event") != args.event:
            return False
        if args.state and r.get("state") != args.state:
            return False
        if args.since is not None and r.get("seq", 0) < args.since:
            return False
        return True

    return [r for r in rows if keep(r)]


def _project(rows, fields):
    if not fields:
        return rows
    keys = [f.strip() for f in fields.split(",") if f.strip()]
    return [{k: r.get(k) for k in keys} for r in rows]


def _emit(rows, as_json):
    if as_json:
        print(json.dumps(rows, indent=2))
        return
    for r in rows:
        print(f"{r.get('seq','?'):>4} {r.get('ts','')} {r.get('event',''):<9} "
              f"{str(r.get('node') or '-'):<6} {str(r.get('actor') or '-'):<14} "
              f"{r.get('result') or r.get('input') or ''}")


def cmd_query(args) -> None:
    rows = _filter(_read_all(args.store), args)
    _emit(_project(rows, args.fields), args.json)


def cmd_timeline(args) -> None:
    args.actor = args.event = args.state = None
    args.since = None
    rows = sorted(_filter(_read_all(args.store), args), key=lambda r: r.get("seq", 0))
    _emit(rows, args.json)


def cmd_replay(args) -> None:
    rows = sorted(
        [r for r in _read_all(args.store) if r.get("node") == args.node],
        key=lambda r: r.get("seq", 0),
    )
    if not rows:
        _die(f"no ledger entries for node {args.node}", 3)
    for r in rows:
        print(f"── seq {r['seq']} · {r['event']} · {r.get('actor','-')} "
              f"({r.get('model','-')}) · state={r.get('state','-')}")
        for label, key in (("input", "input"), ("output", "output"),
                           ("result", "result")):
            if r.get(key):
                print(f"   {label}: {r[key]}")
        for k in ("issues", "unexpected"):
            for item in r.get(k) or []:
                print(f"   {k[:-1] if k.endswith('s') else k}: {item}")
        for k in ("commits", "pushed", "pr", "merge_sha", "worktree"):
            if r.get(k):
                print(f"   {k}: {r[k]}")
        for ref in ("input_ref", "output_ref"):
            if r.get(ref):
                print(f"   {ref}: {os.path.join(args.store, r[ref])}")


def cmd_summary(args) -> None:
    rows = _read_all(args.store)
    by_node: dict[str, dict] = {}
    for r in rows:
        n = r.get("node")
        if not n:
            continue
        cur = by_node.setdefault(n, {"node": n, "events": 0, "state": None, "issues": 0})
        cur["events"] += 1
        if r.get("state"):
            cur["state"] = r["state"]
        cur["issues"] += len(r.get("issues") or []) + len(r.get("unexpected") or [])
    out = sorted(by_node.values(), key=lambda x: x["node"])
    if args.json:
        print(json.dumps({"events": len(rows), "nodes": out}, indent=2))
    else:
        print(f"events: {len(rows)}  nodes: {len(out)}")
        for n in out:
            state = n["state"] or "-"
            print(f"  {n['node']:<8} state={state:<16} events={n['events']} issues={n['issues']}")


def cmd_issues(args) -> None:
    rows = _read_all(args.store)
    found = []
    for r in rows:
        for kind in ("issues", "unexpected"):
            for item in r.get(kind) or []:
                found.append({"seq": r["seq"], "node": r.get("node"),
                              "actor": r.get("actor"), "kind": kind, "text": item})
    if args.json:
        print(json.dumps(found, indent=2))
    else:
        for f in found:
            print(f"{f['seq']:>4} {f['kind']:<10} {str(f['node'] or '-'):<6} {f['text']}")


def cmd_agents(args) -> None:
    rows = _read_all(args.store)
    by_actor: dict[str, dict] = {}
    for r in rows:
        a = r.get("actor")
        if not a:
            continue
        cur = by_actor.setdefault(a, {"actor": a, "role": r.get("role"),
                                      "model": r.get("model"), "events": 0})
        cur["events"] += 1
    out = sorted(by_actor.values(), key=lambda x: x["actor"])
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        for a in out:
            print(f"  {a['actor']:<16} {str(a['role'] or '-'):<10} "
                  f"{str(a['model'] or '-'):<8} events={a['events']}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ledger.py", description=__doc__)
    p.add_argument("--store", required=True, help="shared store dir (holds ledger.jsonl); must be absolute")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add")
    for opt in ("--event", "--actor", "--role", "--model", "--effort", "--parent",
                "--node", "--state", "--base", "--branch", "--worktree", "--pushed",
                "--pr", "--input", "--output", "--result", "--run-id"):
        a.add_argument(opt, required=(opt == "--event"),
                       dest="run_id" if opt == "--run-id" else None)
    a.add_argument("--merge-sha", dest="merge_sha")
    a.add_argument("--input-file", dest="input_file")
    a.add_argument("--output-file", dest="output_file")
    for opt in ("--commit", "--issue", "--unexpected", "--ref", "--artifact"):
        a.add_argument(opt, action="append")
    a.set_defaults(fn=cmd_add)

    def add_read(name, fn, extra=True):
        s = sub.add_parser(name)
        s.add_argument("--json", action="store_true")
        if extra:
            for opt in ("--node", "--actor", "--event", "--state", "--fields"):
                s.add_argument(opt)
            s.add_argument("--since", type=int)
        s.set_defaults(fn=fn)
        return s

    add_read("query", cmd_query)

    t = sub.add_parser("timeline")
    t.add_argument("--node", required=True)
    t.add_argument("--json", action="store_true")
    t.set_defaults(fn=cmd_timeline)

    r = sub.add_parser("replay")
    r.add_argument("--node", required=True)
    r.set_defaults(fn=cmd_replay)

    add_read("summary", cmd_summary, extra=False)
    add_read("issues", cmd_issues, extra=False)
    add_read("agents", cmd_agents, extra=False)
    return p


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    if not os.path.isabs(args.store):
        _die(f"--store must be an absolute path (got {args.store!r})")
    args.fn(args)


if __name__ == "__main__":
    main()
