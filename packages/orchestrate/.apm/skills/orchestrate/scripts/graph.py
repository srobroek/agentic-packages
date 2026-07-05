#!/usr/bin/env python3
"""orchestrate: deterministic task-DAG engine (stdlib-only).

A per-project, runtime-mutable DAG stored as JSON. Reasoning stays in the
orchestrator; this script owns every graph mutation and lookup so agents never
hand-reason about readiness, cycles, or scope collisions.

Store layout (shared, outside every worktree):
    <store>/graph.json

`--store` MUST be an absolute path -- a relative path would resolve against
whatever directory the caller happens to be in (often a worktree), silently
creating an orphan store instead of sharing the run's real one.

Node states: pending ready working reported in_review changes_requested
             approved merged dismissed failed waiting_human

`ready` returns nodes whose deps are all `merged`/`dismissed`/`approved` AND
whose scope globs do not overlap any still-in-flight node -- this is what keeps
parallel worktree coders from colliding. Every mutating command (add-node,
add-edge, set-state, set-meta) holds one exclusive flock across its whole
load -> mutate -> save cycle, so concurrent CLI invocations never lose an
update; the write itself stays an atomic tmp+rename inside that same lock.

Usage:
    graph.py --store <dir> init [--run-id <id>]
    graph.py --store <dir> add-node <id> --scope 'a/**,b/**' [--desc ...] [--dep x --dep y]
    graph.py --store <dir> add-edge <from> <to>          # <from> must finish before <to>
    graph.py --store <dir> set-state <id> <state>
    graph.py --store <dir> set-meta <id> [--assignee A] [--branch B] [--commit C ...]
                                          # assignee/branch are last-wins; --commit
                                          # is appendable (repeat the flag to add more)
    graph.py --store <dir> impact <id>                    # transitive dependents, terse
    graph.py --store <dir> ready [--json]
    graph.py --store <dir> show <id> [--json]
    graph.py --store <dir> list [--state S[,S2,...]] [--json]
    graph.py --store <dir> validate
    graph.py --store <dir> dot                            # Graphviz export (stdout)
Exit codes: 0 ok, 2 usage/validation error, 3 not found.
"""
from __future__ import annotations

import argparse
import contextlib
import fnmatch
import json
import os
import sys
from graphlib import CycleError, TopologicalSorter

STATES = {
    "pending", "ready", "working", "reported", "in_review",
    "changes_requested", "approved", "merged", "dismissed", "failed",
    "waiting_human",
}
# A dep is "cleared" once its node reaches one of these terminal-ish states.
DONE_STATES = {"merged", "dismissed", "approved"}
# A node still competes for file scope while in any of these states.
INFLIGHT_STATES = {
    "ready", "working", "reported", "in_review", "changes_requested",
    "approved", "waiting_human",
}


def _graph_path(store: str) -> str:
    return os.path.join(store, "graph.json")


def _load(store: str) -> dict:
    path = _graph_path(store)
    if not os.path.exists(path):
        _die(f"no graph at {path}; run `init` first", 3)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _atomic_write(store: str, data: dict) -> None:
    """Atomic tmp+rename write. Caller MUST already hold the store's exclusive
    lock (see `_exclusive`) -- this function does no locking of its own."""
    import tempfile

    os.makedirs(store, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=store, prefix=".graph.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, _graph_path(store))
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


@contextlib.contextmanager
def _exclusive(store: str):
    """Hold one exclusive flock over the whole store for a mutating command's
    load -> mutate -> save cycle. Without this, two concurrent CLI processes
    can both load the same pre-mutation state and each save their own view,
    silently dropping whichever update lost the race (verified: 20 concurrent
    add-node calls lost 10 nodes before this lock existed)."""
    import fcntl

    os.makedirs(store, exist_ok=True)
    lock_path = os.path.join(store, ".graph.lock")
    with open(lock_path, "w", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def _die(msg: str, code: int = 2) -> None:
    print(f"graph.py: {msg}", file=sys.stderr)
    sys.exit(code)


def _scopes_overlap(a: list[str], b: list[str]) -> bool:
    """Two scope-glob sets overlap if any glob in one matches a literal path
    prefix of a glob in the other. We compare glob-vs-glob conservatively by
    treating the non-wildcard prefix of each glob as a literal path and testing
    containment either direction."""
    for ga in a:
        pa = ga.split("*", 1)[0].rstrip("/")
        for gb in b:
            pb = gb.split("*", 1)[0].rstrip("/")
            if not pa or not pb:
                return True  # a bare '**' owns everything -> always conflicts
            if pa == pb or pa.startswith(pb + "/") or pb.startswith(pa + "/"):
                return True
            if fnmatch.fnmatch(pa, gb) or fnmatch.fnmatch(pb, ga):
                return True
    return False


def _topo(data: dict) -> TopologicalSorter:
    ts: TopologicalSorter = TopologicalSorter()
    for nid, node in data["nodes"].items():
        ts.add(nid, *node.get("deps", []))
    return ts


def cmd_init(args) -> None:
    with _exclusive(args.store):
        data = {"run_id": args.run_id or "", "nodes": {}, "edges": []}
        _atomic_write(args.store, data)
    print(f"initialized graph at {_graph_path(args.store)}")


def cmd_add_node(args) -> None:
    with _exclusive(args.store):
        data = _load(args.store)
        if args.id in data["nodes"]:
            _die(f"node {args.id} already exists")
        scope = [s.strip() for s in (args.scope or "").split(",") if s.strip()]
        if not scope:
            _die("a node needs at least one --scope glob")
        data["nodes"][args.id] = {
            "id": args.id,
            "desc": args.desc or "",
            "scope": scope,
            "deps": list(dict.fromkeys(args.dep or [])),
            "state": "pending",
            "assignee": None,
            "branch": None,
            "commits": [],
        }
        for dep in args.dep or []:
            data["edges"].append({"from": dep, "to": args.id})
        _atomic_write(args.store, data)
    print(f"added node {args.id} scope={scope} deps={data['nodes'][args.id]['deps']}")


def cmd_add_edge(args) -> None:
    with _exclusive(args.store):
        data = _load(args.store)
        for nid in (args.frm, args.to):
            if nid not in data["nodes"]:
                _die(f"unknown node {nid}", 3)
        deps = data["nodes"][args.to].setdefault("deps", [])
        if args.frm not in deps:
            deps.append(args.frm)
        data["edges"].append({"from": args.frm, "to": args.to})
        _atomic_write(args.store, data)
    print(f"added edge {args.frm} -> {args.to}")


def cmd_set_state(args) -> None:
    if args.state not in STATES:
        _die(f"invalid state {args.state}; one of {sorted(STATES)}")
    with _exclusive(args.store):
        data = _load(args.store)
        if args.id not in data["nodes"]:
            _die(f"unknown node {args.id}", 3)
        data["nodes"][args.id]["state"] = args.state
        _atomic_write(args.store, data)
    print(f"{args.id} -> {args.state}")


def cmd_set_meta(args) -> None:
    with _exclusive(args.store):
        data = _load(args.store)
        if args.id not in data["nodes"]:
            _die(f"unknown node {args.id}", 3)
        node = data["nodes"][args.id]
        if args.assignee is not None:
            node["assignee"] = args.assignee
        if args.branch is not None:
            node["branch"] = args.branch
        for c in args.commit or []:
            if c not in node["commits"]:
                node["commits"].append(c)
        _atomic_write(args.store, data)
    n = data["nodes"][args.id]
    print(f"{args.id} assignee={n['assignee']} branch={n['branch']} commits={n['commits']}")


def _ready_ids(data: dict) -> list[str]:
    nodes = data["nodes"]
    inflight_scopes = [
        n["scope"] for n in nodes.values() if n["state"] in INFLIGHT_STATES
    ]
    out = []
    for nid, node in nodes.items():
        if node["state"] != "pending":
            continue
        if any(nodes.get(d, {}).get("state") not in DONE_STATES for d in node.get("deps", [])):
            continue
        # deps cleared; ensure scope is free of anything already in flight
        if any(_scopes_overlap(node["scope"], s) for s in inflight_scopes):
            continue
        out.append(nid)
    return sorted(out)


def cmd_ready(args) -> None:
    data = _load(args.store)
    ids = _ready_ids(data)
    if args.json:
        print(json.dumps([data["nodes"][i] for i in ids], indent=2))
    else:
        for i in ids:
            n = data["nodes"][i]
            print(f"{i}\t{n['scope']}\t{n['desc']}")


def cmd_show(args) -> None:
    data = _load(args.store)
    if args.id not in data["nodes"]:
        _die(f"unknown node {args.id}", 3)
    print(json.dumps(data["nodes"][args.id], indent=2))


def cmd_list(args) -> None:
    data = _load(args.store)
    states = {s.strip() for s in (args.state or "").split(",") if s.strip()}
    rows = [n for n in data["nodes"].values() if not states or n["state"] in states]
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        for n in sorted(rows, key=lambda x: x["id"]):
            print(f"{n['id']}\t{n['state']}\t{n['scope']}\t{n['desc']}")


def cmd_impact(args) -> None:
    """Transitive dependents of <id>: everything stranded if this node fails."""
    data = _load(args.store)
    nodes = data["nodes"]
    if args.id not in nodes:
        _die(f"unknown node {args.id}", 3)
    rev: dict[str, set[str]] = {n: set() for n in nodes}
    for nid, node in nodes.items():
        for d in node.get("deps", []):
            rev.setdefault(d, set()).add(nid)
    seen: set[str] = set()
    stack = [args.id]
    while stack:
        cur = stack.pop()
        for nxt in rev.get(cur, ()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    for nid in sorted(seen):
        n = nodes[nid]
        print(f"{nid}\t{n['state']}\t{n['desc']}")


def cmd_validate(args) -> None:
    data = _load(args.store)
    nodes = data["nodes"]
    # dangling edges / deps
    for nid, node in nodes.items():
        for d in node.get("deps", []):
            if d not in nodes:
                _die(f"node {nid} depends on unknown node {d}")
    # acyclic
    try:
        _topo(data).prepare()
    except CycleError as exc:  # pragma: no cover - exercised in tests
        _die(f"cycle detected: {exc.args[1]}")
    # disjoint scopes among nodes that could ever run concurrently (no dep path)
    reach = _reachable(nodes)
    ids = list(nodes)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if b in reach[a] or a in reach[b]:
                continue  # ordered by deps, cannot be concurrent
            if _scopes_overlap(nodes[a]["scope"], nodes[b]["scope"]):
                _die(f"scope overlap between concurrent nodes {a} and {b}: "
                     f"{nodes[a]['scope']} vs {nodes[b]['scope']}")
    print(f"ok: {len(nodes)} nodes, acyclic, scopes disjoint among concurrent nodes")


def _reachable(nodes: dict) -> dict:
    """dep-reachability: reach[x] = every node that must finish before x, plus
    every node x must finish before (both directions collapsed for ordering)."""
    fwd = {n: set() for n in nodes}
    for nid, node in nodes.items():
        for d in node.get("deps", []):
            fwd[nid].add(d)
    # transitive closure
    changed = True
    while changed:
        changed = False
        for n in nodes:
            new = set(fwd[n])
            for d in list(fwd[n]):
                new |= fwd.get(d, set())
            if new != fwd[n]:
                fwd[n] = new
                changed = True
    # ancestors + descendants
    both = {n: set(fwd[n]) for n in nodes}
    for n in nodes:
        for m in nodes:
            if n in fwd[m]:
                both[n].add(m)
    return both


def cmd_dot(args) -> None:
    data = _load(args.store)
    print("digraph tasks {")
    for nid, node in data["nodes"].items():
        print(f'  "{nid}" [label="{nid}\\n{node["state"]}"];')
    for e in data["edges"]:
        print(f'  "{e["from"]}" -> "{e["to"]}";')
    print("}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="graph.py", description=__doc__)
    p.add_argument("--store", required=True, help="shared store dir (holds graph.json); must be absolute")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init")
    s.add_argument("--run-id", default="")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("add-node")
    s.add_argument("id")
    s.add_argument("--scope", required=True)
    s.add_argument("--desc", default="")
    s.add_argument("--dep", action="append")
    s.set_defaults(fn=cmd_add_node)

    s = sub.add_parser("add-edge")
    s.add_argument("frm", metavar="from")
    s.add_argument("to")
    s.set_defaults(fn=cmd_add_edge)

    s = sub.add_parser("set-state")
    s.add_argument("id")
    s.add_argument("state")
    s.set_defaults(fn=cmd_set_state)

    s = sub.add_parser("set-meta")
    s.add_argument("id")
    s.add_argument("--assignee")
    s.add_argument("--branch")
    s.add_argument("--commit", action="append", help="appendable; repeat to add more commits")
    s.set_defaults(fn=cmd_set_meta)

    s = sub.add_parser("impact")
    s.add_argument("id")
    s.set_defaults(fn=cmd_impact)

    s = sub.add_parser("ready")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_ready)

    s = sub.add_parser("show")
    s.add_argument("id")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("list")
    s.add_argument("--state", help="comma-separated multi-state filter, e.g. working,in_review")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_list)

    s = sub.add_parser("validate")
    s.set_defaults(fn=cmd_validate)

    s = sub.add_parser("dot")
    s.set_defaults(fn=cmd_dot)
    return p


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    if not os.path.isabs(args.store):
        _die(f"--store must be an absolute path (got {args.store!r})")
    args.fn(args)


if __name__ == "__main__":
    main()
