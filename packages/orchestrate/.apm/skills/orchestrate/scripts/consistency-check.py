#!/usr/bin/env python3
"""orchestrate: graph/ledger consistency check (stdlib-only).

The orchestrator's close-out go/no-go: cross-checks the DAG (graph.json)
against the forensic ledger (ledger.jsonl) so a run can't be declared done
while the two disagree.

Checks:
    - every merged/dismissed node has a matching merged/dismiss ledger event
    - every other in-flight node (ready..approved/waiting_human) has an
      assign ledger event
    - every ledger event that names a node has a matching node in the graph
      (orphan the other direction: a ledger entry for a node that never
      existed, or was removed)

Usage:
    consistency-check.py --store <dir>
Exit codes: 0 consistent, 1 inconsistencies found (one line each on stdout), 2 usage/store error.
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import graph as _graph  # noqa: E402
import ledger as _ledger  # noqa: E402


def _die(msg: str, code: int = 2) -> None:
    print(f"consistency-check.py: {msg}", file=sys.stderr)
    sys.exit(code)


def check(store: str) -> int:
    gdata = _graph._load(store)
    rows = _ledger._read_all(store)

    events_by_node: dict[str, set[str]] = {}
    for r in rows:
        n = r.get("node")
        ev = r.get("event")
        if n and ev:
            events_by_node.setdefault(n, set()).add(ev)

    problems = 0
    nodes = gdata["nodes"]
    for nid, node in nodes.items():
        state = node["state"]
        evs = events_by_node.get(nid, set())
        if state in ("merged", "dismissed"):
            want = "merged" if state == "merged" else "dismiss"
            if want not in evs:
                print(f"orphan-graph: {nid} state={state} missing {want} event")
                problems += 1
        elif state in _graph.INFLIGHT_STATES and "assign" not in evs:
            print(f"orphan-graph: {nid} state={state} missing assign event")
            problems += 1

    for nid in sorted(events_by_node):
        if nid not in nodes:
            print(f"orphan-ledger: event(s) for unknown node {nid}")
            problems += 1

    if problems:
        print(f"inconsistent: {problems} problem(s)")
        return 1
    print("consistent")
    return 0


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="consistency-check.py", description=__doc__)
    p.add_argument("--store", required=True, help="shared store dir (graph.json + ledger.jsonl); must be absolute")
    args = p.parse_args(argv)
    if not os.path.isabs(args.store):
        _die(f"--store must be an absolute path (got {args.store!r})")
    sys.exit(check(args.store))


if __name__ == "__main__":
    main()
