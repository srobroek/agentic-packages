#!/usr/bin/env python3
"""Adversarial tests for the SpecKit DAG authoring builder (build_nodes.py).

Run with: ``uv run --with pytest pytest`` (CI uses ``-q``).

Two responsibilities are proven here:

1. The build-time VALIDATOR rejects the four classes of authoring error named
   in the locked spec, each of which must raise / exit non-zero:
     - a dangling edge (target node id does not exist)
     - two ``default`` edges out of one node
     - a ``conditional`` edge with no note (the predicate)
     - an accidental cycle in the primary (default/mandatory) backbone
   For each, both ``Graph.validate()`` (returns the error string) and
   ``Graph.build()`` (raises ``BuildError``) are exercised, because the CLI
   surfaces validation failures by letting ``build()`` raise -> exit code 2.

2. The ``--check`` STALENESS GATE: ``build_nodes.py --check`` exits 0 when the
   committed ``nodes.json`` matches the builder output, and exits 1 after a
   deliberate hand-edit (then restores the file). This is the CI drift gate.

The validator deliberately tolerates the INTENDED DAG structure: conditional
and optional edges may form loops/back-edges (the real graph has several), so
the cycle/reachability checks run only over the default/mandatory backbone. The
cycle test therefore builds its cycle out of ``default`` edges.

Stdlib + pytest only. Imports the builder by file path so the hyphenless module
name ``build_nodes`` resolves regardless of the runner's cwd.
"""
import importlib.util
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD_NODES_PY = os.path.join(HERE, "build_nodes.py")
NODES_JSON = os.path.join(HERE, "nodes.json")


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_nodes", BUILD_NODES_PY)
    mod = importlib.util.module_from_spec(spec)
    # Register before exec: build_nodes uses @dataclass, and dataclasses looks up
    # cls.__module__ in sys.modules while processing the class. A by-path import
    # that is not registered first makes that lookup return None -> AttributeError.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


bn = _load_builder()


# ---------------------------------------------------------------------------
# Helpers: minimal valid graphs to mutate into each failure mode.
# ---------------------------------------------------------------------------
def _node(g, nid):
    """Register a trivially-valid node (explicit empty soft = emits section)."""
    g.node(nid, title="/speckit." + nid, soft=[])


def _has(errors, needle):
    return any(needle in e for e in errors)


# ===========================================================================
# Rule 1: dangling edge -- a g.edge() target whose node was never created.
# g.edge() permits forward refs (target may be declared later), so existence is
# only enforced at validate()/build() time.
# ===========================================================================
def test_dangling_edge_is_reported_by_validate():
    g = bn.Graph()
    _node(g, "a")
    g.edge("a", "ghost", "default")  # 'ghost' is never created
    errors = g.validate()
    assert _has(errors, "unknown dst node 'ghost'"), errors


def test_dangling_edge_makes_build_raise():
    g = bn.Graph()
    _node(g, "a")
    g.edge("a", "ghost", "default")
    with pytest.raises(bn.BuildError):
        g.build()


def test_dangling_src_is_reported_by_validate():
    # The same check covers a dangling SOURCE (edge declared from a phantom).
    g = bn.Graph()
    _node(g, "b")
    g.edges.append(bn.Edge(src="phantom", to="b", condition="default"))
    errors = g.validate()
    assert _has(errors, "unknown src node 'phantom'"), errors


# ===========================================================================
# Rule 2: two default edges out of one node -- at most one default is allowed
# per outgoing set. g.edge() does NOT enforce this eagerly; validate() does.
# ===========================================================================
def test_two_default_edges_out_of_one_node_is_reported():
    g = bn.Graph()
    for nid in ("a", "b", "c"):
        _node(g, nid)
    g.edge("a", "b", "default")
    g.edge("a", "c", "default")  # second default out of 'a'
    errors = g.validate()
    assert _has(errors, "node 'a' has 2 default outgoing edges"), errors


def test_two_default_edges_make_build_raise():
    g = bn.Graph()
    for nid in ("a", "b", "c"):
        _node(g, nid)
    g.edge("a", "b", "default")
    g.edge("a", "c", "default")
    with pytest.raises(bn.BuildError):
        g.build()


def test_one_default_plus_one_conditional_is_allowed():
    # Guard against an over-eager rule: a single default alongside a conditional
    # sibling is the common authored shape and must NOT be flagged.
    g = bn.Graph()
    for nid in ("a", "b", "c"):
        _node(g, nid)
    g.edge("a", "b", "default")
    g.edge("a", "c", "conditional", note="only sometimes")
    errors = g.validate()
    assert not _has(errors, "default outgoing edges"), errors


# ===========================================================================
# Rule 3: conditional edge with no note. The note IS the predicate, so it is
# required. This is enforced in TWO places:
#   (a) eagerly at the g.edge() call site (fail fast at authoring), and
#   (b) defensively in validate(), so an edge that bypassed the constructor
#       (hand-appended to g.edges) is still caught.
# ===========================================================================
def test_conditional_edge_without_note_raises_at_edge_call():
    g = bn.Graph()
    _node(g, "a")
    _node(g, "b")
    with pytest.raises(bn.BuildError):
        g.edge("a", "b", "conditional")  # no note


def test_conditional_edge_with_blank_note_raises_at_edge_call():
    # Whitespace-only note is treated as empty (note.strip()).
    g = bn.Graph()
    _node(g, "a")
    _node(g, "b")
    with pytest.raises(bn.BuildError):
        g.edge("a", "b", "conditional", note="   ")


def test_conditional_edge_without_note_is_caught_by_validate():
    # Bypass the constructor guard to prove validate() independently catches it.
    g = bn.Graph()
    _node(g, "a")
    _node(g, "b")
    g.edges.append(bn.Edge(src="a", to="b", condition="conditional", note=None))
    errors = g.validate()
    assert _has(errors, "conditional edge missing predicate note"), errors


def test_conditional_edge_without_note_makes_build_raise():
    g = bn.Graph()
    _node(g, "a")
    _node(g, "b")
    g.edges.append(bn.Edge(src="a", to="b", condition="conditional", note=None))
    with pytest.raises(bn.BuildError):
        g.build()


# ===========================================================================
# Rule 4: accidental cycle in the primary (default/mandatory) backbone.
# Built from default edges so it does not also trip the two-default rule
# (each node has exactly one default out).
# ===========================================================================
def test_accidental_cycle_in_primary_backbone_is_reported():
    g = bn.Graph()
    _node(g, "a")
    _node(g, "b")
    g.edge("a", "b", "default")
    g.edge("b", "a", "default")  # closes a 2-node cycle
    errors = g.validate()
    assert _has(errors, "accidental cycle"), errors


def test_accidental_cycle_makes_build_raise():
    g = bn.Graph()
    _node(g, "a")
    _node(g, "b")
    g.edge("a", "b", "default")
    g.edge("b", "a", "default")
    with pytest.raises(bn.BuildError):
        g.build()


def test_three_node_cycle_via_mandatory_is_reported():
    g = bn.Graph()
    for nid in ("a", "b", "c"):
        _node(g, nid)
    g.edge("a", "b", "default")
    g.edge("b", "c", "mandatory")
    g.edge("c", "a", "mandatory")  # closes a 3-node cycle in the backbone
    errors = g.validate()
    assert _has(errors, "accidental cycle"), errors


def test_conditional_backedge_does_not_count_as_cycle():
    # A deliberate loop expressed as a conditional/optional edge is the INTENDED
    # shape (the real DAG has several). It must not be reported as a cycle.
    g = bn.Graph()
    _node(g, "a")
    _node(g, "b")
    g.edge("a", "b", "default")
    g.edge("b", "a", "conditional", note="loop back to revise")
    errors = g.validate()
    assert not _has(errors, "accidental cycle"), errors


# ===========================================================================
# Supporting coverage: the enum guard and the orphan rule (cheap, strengthens
# the safety net around the four named rules).
# ===========================================================================
def test_invalid_condition_raises_at_edge_call():
    g = bn.Graph()
    _node(g, "a")
    _node(g, "b")
    with pytest.raises(bn.BuildError):
        g.edge("a", "b", "sometimes")  # not in the enum


def test_orphan_node_is_reported():
    g = bn.Graph()
    _node(g, "a")
    _node(g, "b")
    g.edge("a", "b", "default")
    _node(g, "island")  # no edges, no hints, in a multi-node graph
    errors = g.validate()
    assert _has(errors, "orphan"), errors


def test_real_main_graph_validates_clean():
    # The shipped DAG must itself pass every rule (regression guard: a future
    # edit that introduces a dangling edge / dup default / bad cycle fails here
    # too, not only in --check).
    g = bn.build_main_graph()
    assert g.validate() == []


# ===========================================================================
# --check STALENESS GATE: exit 0 in sync, exit 1 after a hand-edit.
# Driven as a subprocess so it exercises the real CLI exit codes that CI keys
# off.
#
# The drift / hand-edit cases run against a TEMP COPY via `--check --out <tmp>`
# so the committed nodes.json is never mutated. This matters because nodes.json
# is the runtime-consumed compiled artefact (the dispatcher reads it): an
# interrupted in-place-mutation test would otherwise leave both the working tree
# dirty AND the live artefact broken. The "in sync" case runs the bare
# `--check` (default path) read-only -- that is the exact invocation CI runs.
# ===========================================================================
def _run_check(out=None):
    argv = [sys.executable, BUILD_NODES_PY, "--check"]
    if out is not None:
        argv += ["--out", out]
    return subprocess.run(argv, capture_output=True, text=True)


def test_check_exits_zero_when_in_sync():
    # Bare --check against the committed nodes.json (the CI invocation),
    # read-only -- no mutation of the live artefact.
    proc = _run_check()
    assert proc.returncode == 0, (
        "expected --check to pass against committed nodes.json; "
        "stdout=%r stderr=%r" % (proc.stdout, proc.stderr)
    )
    assert "in sync" in proc.stderr, proc.stderr


def test_check_exits_zero_against_fresh_copy(tmp_path):
    # A byte-identical copy of the committed artefact is also "in sync".
    copy = tmp_path / "nodes.json"
    with open(NODES_JSON, "rb") as fh:
        copy.write_bytes(fh.read())
    proc = _run_check(out=str(copy))
    assert proc.returncode == 0, proc.stderr


def test_check_exits_one_after_hand_edit(tmp_path):
    # Deliberate hand-edit to a COPY -> --check must exit 1. The committed
    # nodes.json is never touched, so an interrupted run cannot corrupt it.
    copy = tmp_path / "nodes.json"
    data = json.load(open(NODES_JSON, encoding="utf-8"))
    victim = sorted(data)[0]
    data[victim]["pre"]["title"] = "TAMPERED -- drift gate must catch this"
    with open(copy, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)

    proc = _run_check(out=str(copy))
    assert proc.returncode == 1, (
        "expected --check to detect drift; stdout=%r stderr=%r"
        % (proc.stdout, proc.stderr)
    )
    assert "DRIFT" in proc.stderr, proc.stderr


def test_check_exits_one_when_artefact_missing(tmp_path):
    # A missing/empty committed artefact is also drift (the CI gate fails if a
    # node is added in the builder but nodes.json was never regenerated).
    missing = tmp_path / "does-not-exist.json"
    proc = _run_check(out=str(missing))
    assert proc.returncode == 1, proc.stderr
    assert "DRIFT" in proc.stderr, proc.stderr


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
