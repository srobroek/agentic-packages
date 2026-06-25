#!/usr/bin/env python3
"""SpecKit DAG authoring builder (build-time, stdlib-only).

This is the AUTHORING source of truth for ``scripts/nodes.json``. It is NOT a
runtime hook. The runtime firewall is strict:

  * ``scripts/dispatcher.py`` is the RUNTIME hook. It stays stdlib-only, reads
    the COMPILED ARTIFACT ``scripts/nodes.json`` with stdlib ``json``, and never
    imports this module.
  * ``scripts/build_nodes.py`` (this file) is the AUTHORING layer. It may use
    anything in the stdlib (here: ``dataclasses`` + ``graphlib``). It compiles a
    typed in-memory DAG down to the flat, dispatcher-compatible JSON.

``nodes.json`` is GENERATED here and stays a flat keyed dict::

    {node_id: {"pre": {...}, "post": {...}}}

that the existing dispatcher ``render_body`` + gating logic consumes UNCHANGED.
The emitted ``pre`` carries (subset, only present-when-non-trivial):
``came_from, context, hard_exists, hard_missing, hard_deprecated, soft, title``;
``post`` carries ``going_to, postconditions, conditional, context, title``.

Edge model (the locked schema)
------------------------------
Edges are a SINGLE canonical store on the Graph. ``came_from`` (incoming) and
``going_to`` (outgoing) are PROJECTIONS derived at emit time, so a single
``g.edge(a, b, ...)`` auto-populates BOTH sides of the link.

Each edge carries:

  * ``condition``: one of ``default | mandatory | conditional | optional``
    (REQUIRED). Semantics:
      - ``default``: the primary forward edge among a node's siblings. At most
        one ``default`` per node's outgoing set.
      - ``mandatory``: cannot be skipped.
      - ``conditional``: taken only if a predicate holds; the predicate text
        lives in ``note``.
      - ``optional``: discretionary.
  * ``note``: free text. REQUIRED (non-empty) when ``condition == "conditional"``
    (it is the predicate); optional otherwise (renders as extra context).

``g.edge(a, b, condition, note=None)`` is a REAL, validated node->node link
(auto-bidirectional via projection). ``node.hint(text)`` is free-text navigation
prose that is NOT validated as an edge -- use it for "(direct invocation)"-style
strings whose other end is not a DAG node.

``$ref`` fragments are first-class: ``g.fragment(name, text)`` registers reusable
prose; reference it as the token ``$ref:name`` anywhere inside a node's
``context``/prose bullets, and it is expanded inline at emit time.

CLI
---
  * ``python3 build_nodes.py``          -> writes scripts/nodes.json
  * ``python3 build_nodes.py --check``  -> regenerate to a buffer, diff against
                                           the committed nodes.json, exit 1 on
                                           drift (for CI)
  * ``python3 build_nodes.py --print``  -> write generated JSON to stdout
  * ``python3 build_nodes.py --help``   -> usage

NOTE (Stage 1): this file currently defines ONLY a couple of smoke nodes so the
framework can self-test. Real DAG content is migrated in a later stage.
"""

from __future__ import annotations

import argparse
import difflib
import graphlib
import json
import os
import re
import sys
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Allowed edge conditions (the locked enum).
CONDITIONS = ("default", "mandatory", "conditional", "optional")

#: Path to the committed compiled artefact, relative to this file.
DEFAULT_NODES_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nodes.json")

#: Token used to reference a registered fragment inside prose, e.g. "$ref:warn".
_REF_RE = re.compile(r"\$ref:([A-Za-z0-9_.\-]+)")


class BuildError(Exception):
    """Raised for authoring-time misuse (bad enum, missing note, etc.)."""


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class Edge:
    """A canonical, validated node->node link.

    Stored ONCE on the graph; the per-node ``came_from`` / ``going_to`` lists
    are projections computed from the full edge list at emit time.
    """

    src: str
    to: str
    condition: str
    note: Optional[str] = None


@dataclass
class Node:
    """An authoring node. Holds only node-local data; edges live on the Graph.

    ``hints`` are free-text navigation strings (NOT validated edges) that the
    projection appends to ``came_from`` / ``going_to`` for ends that are not DAG
    nodes (e.g. "(direct invocation)", "(terminal)").
    """

    id: str
    title: str
    context: list = field(default_factory=list)
    # Post-phase "Context absorbed from steering" bullets. The dispatcher
    # renders a `context` key in BOTH the pre and post phases; a handful of
    # nodes (orchestrator review-gate prose) carry context ONLY on the post
    # side, so the builder keeps a separate post-context list.
    context_post_items: list = field(default_factory=list)
    hard_exists: list = field(default_factory=list)
    hard_missing: list = field(default_factory=list)
    hard_deprecated: list = field(default_factory=list)
    soft: list = field(default_factory=list)
    postconditions: list = field(default_factory=list)
    # Free-prose advisory branching, rendered as the post "Conditional
    # branching" section. Distinct from edges with condition="conditional".
    conditional: list = field(default_factory=list)

    # Free-text nav prose (not edges). Keyed by direction so projections can
    # interleave them with the real edge display strings.
    came_from_hints: list = field(default_factory=list)
    going_to_hints: list = field(default_factory=list)

    # Whether a "Preconditions" section should be emitted even when empty. The
    # dispatcher keys the section's presence off the "soft" field being present,
    # so the builder mirrors that: a node with any precondition data (or an
    # explicit empty soft list) emits the section.
    _emit_preconditions: bool = True

    def hint(self, text: str, direction: str = "to") -> "Node":
        """Add free-text navigation prose (NOT a validated edge).

        ``direction`` is ``"to"`` (going_to / outgoing prose, default) or
        ``"from"`` (came_from / incoming prose). Returns self for chaining.
        """
        if direction not in ("to", "from"):
            raise BuildError(
                "hint direction must be 'to' or 'from', got %r" % (direction,)
            )
        if not isinstance(text, str) or not text:
            raise BuildError("hint text must be a non-empty string")
        (self.going_to_hints if direction == "to" else self.came_from_hints).append(text)
        return self


@dataclass
class Phase:
    """A logical grouping label for nodes (authoring affordance only).

    Phases do not affect the emitted JSON; they let a future migration tag
    nodes by lifecycle phase (specify/plan/implement/...) for documentation or
    selective validation without changing the runtime artefact.
    """

    name: str
    node_ids: list = field(default_factory=list)


class Graph:
    """The authoring DAG: nodes + a single canonical edge list + fragments."""

    def __init__(self) -> None:
        self.nodes: dict = {}
        self.edges: list = []  # canonical store
        self.fragments: dict = {}
        self.phases: dict = {}

    # -- authoring API ----------------------------------------------------
    def node(
        self,
        id: str,
        *,
        title: str,
        context=None,
        context_post=None,
        hard_exists=None,
        hard_missing=None,
        hard_deprecated=None,
        soft=None,
        postconditions=None,
        conditional=None,
    ) -> Node:
        """Create and register a node. Returns the Node for chaining hints."""
        if not isinstance(id, str) or not id:
            raise BuildError("node id must be a non-empty string")
        if id in self.nodes:
            raise BuildError("duplicate node id: %r" % (id,))
        if not isinstance(title, str) or not title:
            raise BuildError("node %r: title must be a non-empty string" % (id,))
        n = Node(
            id=id,
            title=title,
            context=list(context or []),
            context_post_items=list(context_post or []),
            hard_exists=list(hard_exists or []),
            hard_missing=list(hard_missing or []),
            hard_deprecated=list(hard_deprecated or []),
            soft=list(soft if soft is not None else []),
            postconditions=list(postconditions or []),
            conditional=list(conditional or []),
            # Emit a Preconditions section whenever the node carries any precond
            # data OR a soft list was explicitly supplied (even if empty).
            _emit_preconditions=(
                soft is not None
                or bool(hard_exists)
                or bool(hard_missing)
                or bool(hard_deprecated)
            ),
        )
        self.nodes[id] = n
        return n

    def edge(self, src: str, dst: str, condition: str, note: Optional[str] = None) -> Edge:
        """Append a validated edge to the canonical store.

        Validates the condition enum and the note-required-when-conditional
        rule eagerly so authoring mistakes fail at the call site. Existence of
        ``src``/``dst`` is checked at validate()/emit() time so edges may be
        declared before the target node (forward references allowed).
        """
        if condition not in CONDITIONS:
            raise BuildError(
                "edge %s->%s: condition must be one of %s, got %r"
                % (src, dst, CONDITIONS, condition)
            )
        if condition == "conditional" and not (isinstance(note, str) and note.strip()):
            raise BuildError(
                "edge %s->%s: condition='conditional' requires a non-empty note"
                " (the predicate)" % (src, dst)
            )
        e = Edge(src=src, to=dst, condition=condition, note=note)
        self.edges.append(e)
        return e

    def fragment(self, name: str, text: str) -> None:
        """Register a reusable prose fragment referenced as ``$ref:name``."""
        if not isinstance(name, str) or not name:
            raise BuildError("fragment name must be a non-empty string")
        if name in self.fragments:
            raise BuildError("duplicate fragment: %r" % (name,))
        if not isinstance(text, str):
            raise BuildError("fragment %r: text must be a string" % (name,))
        self.fragments[name] = text

    def phase(self, name: str, node_ids=None) -> Phase:
        """Register a (purely documentary) phase grouping."""
        p = Phase(name=name, node_ids=list(node_ids or []))
        self.phases[name] = p
        return p

    # -- internals --------------------------------------------------------
    def _expand_refs(self, text: str) -> str:
        """Expand ``$ref:name`` tokens in a single prose string."""
        if not isinstance(text, str) or "$ref:" not in text:
            return text

        def _sub(m):
            name = m.group(1)
            if name not in self.fragments:
                raise BuildError("unknown $ref fragment: %r" % (name,))
            return self.fragments[name]

        return _REF_RE.sub(_sub, text)

    def _expand_list(self, items) -> list:
        return [self._expand_refs(s) for s in items]

    def _render_edge(self, e: Edge) -> str:
        """Render a canonical edge to the dispatcher's display string.

        Format:
          default      -> "/speckit.<x> (default)"  (or "(default -- <note>)")
          mandatory    -> "/speckit.<x> (mandatory)" (or "(mandatory -- <note>)")
          conditional  -> "/speckit.<x> -- <note>"   (note is the predicate)
          optional     -> "/speckit.<x>"             (or "/speckit.<x> -- <note>")

        The target node id is rendered as its slash-command form by reversing
        the dispatcher's normalization (hyphenated id -> dotted command). The
        first segment becomes the command root; we cannot perfectly recover the
        original dot/hyphen split for multi-word commands, so the canonical
        rendering uses the node's own id-to-command convention: segments are
        kept as authored. To stay faithful, callers author node ids that match
        the dispatcher's hyphenated keys; the command label is built from the
        node's stored ``title`` head when available, else from the id.
        """
        label = _command_label(e.to)
        note = (e.note or "").strip()
        if e.condition == "conditional":
            # Predicate-as-note. Always "-- <note>".
            return "%s -- %s" % (label, note)
        if e.condition == "optional":
            return "%s -- %s" % (label, note) if note else label
        # default / mandatory carry a parenthetical tag, optionally with note.
        if note:
            return "%s (%s -- %s)" % (label, e.condition, note)
        return "%s (%s)" % (label, e.condition)

    def _project(self):
        """Compute per-node came_from / going_to display lists from edges.

        Returns ``(came_from, going_to)`` dicts: node_id -> list[str]. Real
        edges render first (in edge-declaration order), then the node's free
        hints, matching the authored mix of edge strings and "(...)" prose.
        """
        came: dict = {nid: [] for nid in self.nodes}
        goes: dict = {nid: [] for nid in self.nodes}
        for e in self.edges:
            goes.setdefault(e.src, []).append(self._render_edge(e))
            came.setdefault(e.to, []).append(self._render_edge_from(e))
        # Append free-text hints after the validated edges.
        for nid, n in self.nodes.items():
            came[nid].extend(self._expand_list(n.came_from_hints))
            goes[nid].extend(self._expand_list(n.going_to_hints))
        return came, goes

    def _render_edge_from(self, e: Edge) -> str:
        """Render the incoming-side display string for came_from.

        Same display format as the outgoing side but labelling the SOURCE node.
        """
        label = _command_label(e.src)
        note = (e.note or "").strip()
        if e.condition == "conditional":
            return "%s -- %s" % (label, note)
        if e.condition == "optional":
            return "%s -- %s" % (label, note) if note else label
        if note:
            return "%s (%s -- %s)" % (label, e.condition, note)
        return "%s (%s)" % (label, e.condition)

    # -- validation -------------------------------------------------------
    def validate(self) -> list:
        """Run all build-time checks. Returns a list of error strings (empty=ok).

        Checks (stdlib only):
          1. every edge condition is in the enum (also enforced at edge() time)
          2. every conditional edge has a non-empty note
          3. at most one ``default`` edge per node's outgoing set
          4. no dangling edge: every edge src/dst is a real node
          5. no orphan node: every node reachable (BFS) from a root, where a
             root is any node with no incoming edge; isolated nodes with neither
             in- nor out-edges are reported as orphans
          6. cycle check via graphlib.TopologicalSorter -- report genuine
             accidental cycles. (The intended DAG structure -- including
             deliberate back/loop edges expressed as condition='conditional' or
             'optional' -- is tolerated: only edges on the primary spanning set,
             i.e. 'default'/'mandatory', participate in the cycle check.)
        """
        errors: list = []
        node_ids = set(self.nodes)

        # 1 + 2: per-edge validity (defensive; edge() already enforces these).
        for e in self.edges:
            if e.condition not in CONDITIONS:
                errors.append(
                    "edge %s->%s: invalid condition %r" % (e.src, e.to, e.condition)
                )
            if e.condition == "conditional" and not (
                isinstance(e.note, str) and e.note.strip()
            ):
                errors.append(
                    "edge %s->%s: conditional edge missing predicate note"
                    % (e.src, e.to)
                )

        # 4: dangling edges.
        for e in self.edges:
            if e.src not in node_ids:
                errors.append("edge %s->%s: unknown src node %r" % (e.src, e.to, e.src))
            if e.to not in node_ids:
                errors.append("edge %s->%s: unknown dst node %r" % (e.src, e.to, e.to))

        # 3: at most one default per outgoing set.
        default_count: dict = {}
        for e in self.edges:
            if e.condition == "default":
                default_count[e.src] = default_count.get(e.src, 0) + 1
        for src, c in default_count.items():
            if c > 1:
                errors.append(
                    "node %r has %d default outgoing edges (at most one allowed)"
                    % (src, c)
                )

        # Build adjacency only over edges whose endpoints exist (avoid KeyErrors
        # cascading from a dangling edge already reported above). Reachability
        # and root selection use ONLY the primary (default/mandatory) backbone:
        # conditional/optional edges are deliberate loops/back-edges, and
        # counting them as incoming would (a) suppress legitimate roots and
        # (b) let a genuine orphan masquerade as reachable via a back-edge. They
        # are excluded here for the same reason they are excluded from the cycle
        # check below.
        out_adj: dict = {nid: [] for nid in node_ids}
        in_deg: dict = {nid: 0 for nid in node_ids}
        # Track touch by an edge of ANY condition so a node that participates in
        # the DAG only via a conditional/optional link is not mistaken for a
        # fully isolated node below.
        any_degree: dict = {nid: 0 for nid in node_ids}
        for e in self.edges:
            if e.src in node_ids and e.to in node_ids:
                any_degree[e.src] += 1
                any_degree[e.to] += 1
            if (
                e.condition in ("default", "mandatory")
                and e.src in node_ids
                and e.to in node_ids
            ):
                out_adj[e.src].append(e.to)
                in_deg[e.to] += 1

        # 5: orphan / reachability via BFS from primary-backbone roots (no
        # incoming primary edge). A node reached this way is connected.
        roots = [nid for nid in node_ids if in_deg.get(nid, 0) == 0]
        reachable = set()
        dq = deque(roots)
        reachable.update(roots)
        while dq:
            cur = dq.popleft()
            for nxt in out_adj.get(cur, []):
                if nxt not in reachable:
                    reachable.add(nxt)
                    dq.append(nxt)
        single_node_graph = len(node_ids) <= 1
        for nid in node_ids:
            # A fully isolated node (no edge of any condition) is an orphan,
            # unless it is the entire graph OR it carries hint prose. ``hint()``
            # is the framework's sanctioned link to a NON-DAG end (advisory /
            # utility / "(invoke anytime)" nodes whose only navigation is free
            # prose). Such a node is intentionally standalone, not an accidental
            # orphan -- so a node with >=1 hint of either direction is exempt
            # from the orphan check. A node with neither edges NOR hints is a
            # genuine accidental orphan and is still flagged.
            n = self.nodes.get(nid)
            has_hint = bool(
                n and (n.came_from_hints or n.going_to_hints)
            )
            if (
                any_degree.get(nid, 0) == 0
                and not single_node_graph
                and not has_hint
            ):
                errors.append(
                    "node %r is an orphan: it has no edges of any condition"
                    " and no navigation hints" % (nid,)
                )
            elif any_degree.get(nid, 0) == 0 and has_hint:
                # Intentional standalone advisory/utility node; skip reachability.
                continue
            elif nid not in reachable:
                errors.append(
                    "node %r is unreachable (orphan): no path from any root"
                    " via primary (default/mandatory) edges" % (nid,)
                )

        # 6: cycle check over the primary spanning set (default/mandatory).
        # Conditional/optional edges are deliberate loops/back-edges in this DAG
        # and are excluded so the validator reports only ACCIDENTAL cycles in
        # the forward backbone.
        primary: dict = {nid: set() for nid in node_ids}
        for e in self.edges:
            if (
                e.condition in ("default", "mandatory")
                and e.src in node_ids
                and e.to in node_ids
            ):
                primary[e.to].add(e.src)  # predecessors map for TopologicalSorter
        try:
            graphlib.TopologicalSorter(primary).prepare()
        except graphlib.CycleError as exc:
            cycle = exc.args[1] if len(exc.args) > 1 else exc.args
            errors.append(
                "accidental cycle in primary (default/mandatory) edges: %s"
                % (" -> ".join(cycle) if isinstance(cycle, (list, tuple)) else cycle,)
            )

        return errors

    # -- emit -------------------------------------------------------------
    def build(self) -> dict:
        """Compile the in-memory DAG to the flat dispatcher-compatible dict.

        Raises BuildError if validation fails (callers that want the error list
        without raising should call ``validate()`` directly).
        """
        errors = self.validate()
        if errors:
            raise BuildError("validation failed:\n  - " + "\n  - ".join(errors))

        came, goes = self._project()
        out: dict = {}
        for nid, n in self.nodes.items():
            pre: dict = {}
            post: dict = {}

            # ----- pre -----
            cf = came.get(nid, [])
            if cf:
                pre["came_from"] = cf
            ctx = self._expand_list(n.context)
            if ctx:
                pre["context"] = ctx
            if n.hard_exists:
                pre["hard_exists"] = self._expand_list(n.hard_exists)
            if n.hard_missing:
                pre["hard_missing"] = self._expand_list(n.hard_missing)
            if n.hard_deprecated:
                pre["hard_deprecated"] = self._expand_list(n.hard_deprecated)
            # The dispatcher keys the "Preconditions" section off "soft" being
            # present, so emit "soft" whenever the node should render the
            # section (even as an empty list).
            if n._emit_preconditions:
                pre["soft"] = self._expand_list(n.soft)
            pre["title"] = n.title + " -- before you run this"

            # ----- post -----
            gt = goes.get(nid, [])
            if gt:
                post["going_to"] = gt
            if n.postconditions:
                post["postconditions"] = self._expand_list(n.postconditions)
            pctx = self._expand_list(n.context_post()) if hasattr(n, "context_post") else []
            if pctx:
                post["context"] = pctx
            if n.conditional:
                post["conditional"] = self._expand_list(n.conditional)
            post["title"] = n.title + " -- what to do next"

            out[nid] = {"pre": pre, "post": post}
        return out

    def emit(self, path: str) -> None:
        """Write the compiled JSON byte-stably to ``path``."""
        text = self.render()
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def render(self) -> str:
        """Return the byte-stable JSON text (sorted keys, trailing newline)."""
        data = self.build()
        return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


#: Explicit slash-command label per node id. The dispatcher normalizes a
#: slash command "speckit.foo.bar" -> the nodes.json key "foo-bar" (dots to
#: hyphens), which is lossy: "agent-assign.execute" and "agent.assign.execute"
#: both collapse to "agent-assign-execute". Display rendering needs the inverse
#: (key -> original dotted command), so every multi-word command carries an
#: explicit label here. Ids whose command label is just "/speckit." + id (the
#: single-segment commands such as analyze/plan/clarify) are intentionally
#: omitted and fall through to the default below.
COMMAND_LABELS: dict = {
    "agent-assign-assign": "/speckit.agent-assign.assign",
    "agent-assign-execute": "/speckit.agent-assign.execute",
    "agent-assign-validate": "/speckit.agent-assign.validate",
    "archive": "/speckit.archive.run",
    "bugfix-patch": "/speckit.bugfix.patch",
    "bugfix-report": "/speckit.bugfix.report",
    "bugfix-verify": "/speckit.bugfix.verify",
    "checkpoint-commit": "/speckit.checkpoint.commit",
    "conduct": "/speckit.conduct.run",
    "critique-critique-template": "/speckit.critique.critique-template",
    "critique-run": "/speckit.critique.run",
    "doctor-check": "/speckit.doctor.check",
    "fleet": "/speckit.fleet.run",
    "fleet-review": "/speckit.fleet.review",
    "github-issues-import": "/speckit.github-issues.import",
    "github-issues-link": "/speckit.github-issues.link",
    "github-issues-sync": "/speckit.github-issues.sync",
    "iterate-apply": "/speckit.iterate.apply",
    "iterate-define": "/speckit.iterate.define",
    "memory-md-audit": "/speckit.memory-md.audit",
    "memory-md-capture": "/speckit.memory-md.capture",
    "memory-md-capture-from-diff": "/speckit.memory-md.capture-from-diff",
    "memory-md-init": "/speckit.memory-md.init",
    "memory-md-init-project": "/speckit.memory-md.init-project",
    "memory-md-log-finding": "/speckit.memory-md.log-finding",
    "memory-md-plan-with-memory": "/speckit.memory-md.plan-with-memory",
    "memory-md-prepare-context": "/speckit.memory-md.prepare-context",
    "memory-md-share-lesson": "/speckit.memory-md.share-lesson",
    "memory-md-specify": "/speckit.memory-md.specify",
    "memory-md-sync-shared": "/speckit.memory-md.sync-shared",
    "memory-md-token-report": "/speckit.memory-md.token-report",
    "qa-qa-template": "/speckit.qa.qa-template",
    "qa-run": "/speckit.qa.run",
    "reconcile": "/speckit.reconcile.run",
    "refine-diff": "/speckit.refine.diff",
    "refine-propagate": "/speckit.refine.propagate",
    "refine-status": "/speckit.refine.status",
    "refine-update": "/speckit.refine.update",
    "retro-retro-template": "/speckit.retro.retro-template",
    "retro-run": "/speckit.retro.run",
    "review-code": "/speckit.review.code",
    "review-comments": "/speckit.review.comments",
    "review-errors": "/speckit.review.errors",
    "review-run": "/speckit.review.run",
    "review-simplify": "/speckit.review.simplify",
    "review-tests": "/speckit.review.tests",
    "review-types": "/speckit.review.types",
    "roadmap-write": "/speckit.roadmap.write",
    "status-show": "/speckit.status.show",
    "sync-analyze": "/speckit.sync.analyze",
    "sync-conflicts": "/speckit.sync.conflicts",
    "tinyspec-classify": "/speckit.tinyspec.classify",
    "tinyspec-implement": "/speckit.tinyspec.implement",
    "tinyspec-tinyspec": "/speckit.tinyspec.tinyspec",
    "worktree-clean": "/speckit.worktree.clean",
    "worktree-create": "/speckit.worktree.create",
    "worktree-list": "/speckit.worktree.list",
}


def _command_label(node_id: str) -> str:
    """Render a node id as its /speckit.<...> slash-command label.

    Multi-word commands (agent-assign, github-issues, memory-md, ...) and
    every command whose label is not simply "/speckit." + id carry an explicit
    entry in ``COMMAND_LABELS``. Single-segment commands (analyze, plan,
    clarify, ...) fall through to the default.
    """
    if node_id in COMMAND_LABELS:
        return COMMAND_LABELS[node_id]
    return "/speckit." + node_id


# Expose post-only context to build() via the hook it already calls. Returns
# the node's post-context bullets (empty for the common case).
def _node_context_post(self):  # noqa: ANN001
    return list(self.context_post_items)


Node.context_post = _node_context_post


# ---------------------------------------------------------------------------
# Smoke graph (Stage 1 self-test only -- NOT the real DAG content).
# ---------------------------------------------------------------------------
def build_smoke_graph() -> Graph:
    """A tiny graph that exercises every feature of the framework."""
    g = Graph()

    g.fragment("warn", "Re-run is idempotent; safe to repeat.")

    g.node(
        "alpha",
        title="/speckit.alpha",
        context=["Entry point. $ref:warn"],
        soft=[],
        postconditions=["`specs/<feat>/alpha.md`"],
    ).hint("(project bootstrap entry)", direction="from")

    g.node(
        "beta",
        title="/speckit.beta",
        context=["Middle step."],
        hard_missing=["specs/<feat>/alpha.md"],
        soft=["confirm the alpha artefact looks right"],
        postconditions=["`specs/<feat>/beta.md`"],
        conditional=["If alpha was trivial, beta is a no-op."],
    )

    g.node(
        "gamma",
        title="/speckit.gamma",
        hard_missing=["specs/<feat>/beta.md"],
        soft=[],
    ).hint("(terminal -- feature shipped)", direction="to")

    # Real validated edges (auto-bidirectional via projection).
    g.edge("alpha", "beta", "default")
    g.edge("beta", "gamma", "default")
    g.edge("alpha", "gamma", "conditional", note="if beta is skipped for a trivial change")
    g.edge("beta", "alpha", "optional", note="loop back to revise alpha")

    g.phase("setup", ["alpha"])
    g.phase("ship", ["beta", "gamma"])
    return g


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _read_committed(path: str) -> str:
    if not os.path.isfile(path):
        return ""
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def cmd_write(g: Graph, path: str) -> int:
    g.emit(path)
    sys.stderr.write("wrote %s (%d nodes)\n" % (path, len(g.nodes)))
    return 0


def cmd_check(g: Graph, path: str) -> int:
    generated = g.render()
    committed = _read_committed(path)
    if generated == committed:
        sys.stderr.write("nodes.json is in sync\n")
        return 0
    diff = difflib.unified_diff(
        committed.splitlines(keepends=True),
        generated.splitlines(keepends=True),
        fromfile=path + " (committed)",
        tofile="build_nodes.py --print (generated)",
    )
    sys.stderr.write("DRIFT: committed nodes.json does not match the builder output\n")
    sys.stderr.writelines(diff)
    if not committed:
        sys.stderr.write("\n(committed file missing or empty: %s)\n" % (path,))
    return 1


def cmd_validate(g: Graph) -> int:
    errors = g.validate()
    if not errors:
        sys.stderr.write("validation passed (%d nodes, %d edges)\n" % (len(g.nodes), len(g.edges)))
        return 0
    sys.stderr.write("validation FAILED:\n")
    for e in errors:
        sys.stderr.write("  - " + e + "\n")
    return 1


def build_main_graph() -> Graph:
    """Return the migrated SpecKit DAG (Stage 2).

    Authored from the committed scripts/nodes.json content. The 17 cut node
    families (brownfield.*, diagram.*, onboard.*, optimize.*) are NOT authored;
    edges that targeted them are re-pointed onto the surviving workflow.
    """
    g = Graph()

    # -- shared fragments -------------------------------------------------
    # The orchestrator stay-alive review-gate prose appeared verbatim ~10x
    # across review-*, fix-findings, conduct, and agent-assign.execute. It is
    # registered once and referenced via $ref so a single edit propagates.
    g.fragment(
        "stay-alive",
        "If spawned as a sub-agent, stay alive after reporting findings and"
        " wait for the orchestrator's review -- do not end your turn; it may"
        " SendMessage to ask you to clarify or reassess a finding.",
    )
    g.fragment(
        "stay-alive-spawn",
        "Spawn the review subagent with an explicit stay-alive instruction:"
        " 'report your findings and wait for my review -- do not end your turn;"
        " I may SendMessage to clarify findings.' Triage the findings before"
        " routing to fix-findings.",
    )

    # ======================================================================
    # Phase: bootstrap / memory init
    # ======================================================================
    g.node(
        "memory-md-init",
        title="/speckit.memory-md.init",
        context=[
            "Idempotent. Re-running this command no-ops if `docs/memory/INDEX.md` already exists.",
            "Invoked once per project after `specify init` + extension install. Subsequent feature cycles use `/speckit.memory-md.plan-with-memory`.",
        ],
        soft=["(none; this is the entry point that creates docs/memory/)"],
        postconditions=[
            "`docs/memory/INDEX.md`",
            "`docs/memory/{ARCHITECTURE,BUGS,DECISIONS,WORKLOG,PROJECT_CONTEXT}.md`",
            "`.specify/memory/{constitution,architecture_constitution,DECISIONS,BUGS}.md` (templates)",
        ],
        conditional=[
            "If `constitution.md` already exists, skip `/speckit.constitution` and go directly to `/speckit.specify`.",
        ],
    ).hint("(project bootstrap, once -- see project-setup SKILL.md step 10)", direction="from") \
     .hint("(return to bootstrap workflow)")

    g.node(
        "memory-md-init-project",
        title="/speckit.memory-md.init-project",
        context=[
            "Profiles the project (language/framework) so /speckit.memory-md.share-lesson and /speckit.memory-md.sync-shared route lessons to the right cross-project channels in the global shared memory (~/.spec-kit/shared-memory.sqlite). Optional but required before using the shared-lesson commands.",
        ],
        soft=["docs/memory/INDEX.md"],
        postconditions=[
            "project tech-stack profile recorded (language + optional framework) used to scope cross-project shared-memory sync channels",
        ],
        conditional=[
            "One-time per project. Re-running refreshes the detected language/framework profile; harmless if unchanged.",
        ],
    ).hint("(return to bootstrap workflow -- then /speckit.constitution or /speckit.specify)")

    g.node(
        "constitution",
        title="/speckit.constitution",
        context=[
            "The constitution is the durable charter for this project. Light edits only after first feature; major rewrites should be rare and noted in DECISIONS.md.",
        ],
        soft=["`.specify/memory/constitution.md` (template will exist; you're filling it in)"],
        postconditions=["`.specify/memory/constitution.md` (filled in)"],
        conditional=[
            "If you started here from an existing project, confirm `.specify/memory/architecture_constitution.md` and `.specify/memory/DECISIONS.md` reflect reality before specifying features.",
        ],
    ).hint("(project bootstrap)", direction="from")

    g.node(
        "memory-md-specify",
        title="/speckit.memory-md.specify",
        context=[
            "Runs on the before_specify hook: prepares and synthesises relevant project memory into specs/<feat>/memory-synthesis.md so the spec is written with prior decisions/lessons in view. Mandatory hook in memory-md (optional: false).",
            "Reads from the SQLite memory cache; if the index is missing run /speckit.memory-md.init first.",
        ],
        hard_missing=["docs/memory/INDEX.md"],
        soft=[".specify/memory/constitution.md"],
        postconditions=[
            "specs/<feat>/memory-synthesis.md (<=900 words, the synthesised memory context for this spec)",
        ],
    ).hint("(project bootstrap, before the first /speckit.specify)", direction="from")

    # ======================================================================
    # Phase: specify / clarify / plan
    # ======================================================================
    g.node(
        "specify",
        title="/speckit.specify",
        context=[
            "For minimal scope, prefer `/speckit.tinyspec.classify` -- heavier `/speckit.specify` is overkill for trivial work. For a bug, `/speckit.bugfix.report` is the right entry.",
            "If re-entered from `/speckit.refine.status` or `/speckit.iterate.apply`, walk briefly through every downstream stage to assess impact rather than restarting from scratch.",
        ],
        soft=["`.specify/memory/constitution.md`"],
        postconditions=["`specs/<feat>/spec.md`"],
        conditional=[
            "If the spec is one paragraph long, consider rerouting to `/speckit.tinyspec.classify`.",
            "If this is a bug rather than a feature, exit to `/speckit.bugfix.report`.",
        ],
    ).hint("(project bootstrap)", direction="from")

    g.node(
        "clarify",
        title="/speckit.clarify",
        context=[
            "Use clarification to resolve ambiguities the spec author left open. Skip if the spec is already unambiguous.",
        ],
        hard_missing=["specs/<feat>/spec.md"],
        soft=[],
        postconditions=["`specs/<feat>/clarifications.md`"],
        conditional=[
            "If memory-md is installed but `docs/memory/INDEX.md` is missing, run `/speckit.memory-md.init` first.",
        ],
    )

    g.node(
        "memory-md-plan-with-memory",
        title="/speckit.memory-md.plan-with-memory",
        context=[
            "Selectively indexes durable memory (decisions, bugs, architecture) and synthesises it into a short artefact the planner reads. memory-md is installed by default; skip only if it was deliberately removed.",
        ],
        hard_missing=["docs/memory/INDEX.md", "specs/<feat>/spec.md"],
        soft=[],
        postconditions=["`specs/<feat>/memory-synthesis.md`"],
        conditional=[
            "If `memory-synthesis.md` is empty or just boilerplate, the planner can ignore it; don't bend the plan around an empty synthesis.",
        ],
    )

    g.node(
        "plan",
        title="/speckit.plan",
        context=[
            "Full SpecKit projects keep `.specify/` workflow assets separate from durable project docs in `docs/`.",
            "`memory-synthesis.md` is a HARD prerequisite for planning. If it is missing, STOP and run `/speckit.memory-md.plan-with-memory` first -- do not plan without synthesised memory.",
            "If `plan.md` already exists, use `/speckit.refine.update` to amend rather than re-planning from scratch.",
        ],
        hard_exists=["specs/<feat>/plan.md"],
        hard_missing=["specs/<feat>/spec.md", "specs/<feat>/memory-synthesis.md"],
        soft=["specs/<feat>/clarifications.md"],
        postconditions=["`specs/<feat>/plan.md`"],
    )

    g.node(
        "tasks",
        title="/speckit.tasks",
        context=[
            "Decomposes the plan into discrete, testable tasks. If `tasks.md` already exists, you're either iterating (use iterate) or refining (use refine.update) -- don't re-author tasks from scratch.",
        ],
        hard_exists=["specs/<feat>/tasks.md"],
        hard_missing=["specs/<feat>/plan.md"],
        soft=[],
        postconditions=["`specs/<feat>/tasks.md`"],
    )

    # ======================================================================
    # Phase: pre-impl review (checklist / critique / security-review / analyze)
    # ======================================================================
    g.node(
        "checklist",
        title="/speckit.checklist",
        context=[
            "Requirements-quality gate (matches upstream spec-kit ordering): validates requirements completeness, clarity, and consistency against the full spec + plan + tasks before the critique/security-review pass.",
        ],
        hard_missing=["specs/<feat>/spec.md", "specs/<feat>/plan.md", "specs/<feat>/tasks.md"],
        soft=["specs/<feat>/clarifications.md"],
        postconditions=["`specs/<feat>/checklist.md`"],
    )

    g.node(
        "critique-run",
        title="/speckit.critique.run",
        context=[
            "Dual-lens review (product strategy + engineering risk). Findings should be triaged into plan-edits vs. defer-to-tasks before moving on. Runs in parallel with `/speckit.security-review`.",
        ],
        hard_missing=["specs/<feat>/plan.md", "specs/<feat>/tasks.md"],
        soft=[],
        postconditions=["`specs/<feat>/critique-report.md`"],
    )

    g.node(
        "critique-critique-template",
        title="/speckit.critique.critique-template",
        context=["Internal template helper. Don't call from a feature cycle."],
        soft=["(none)"],
    ).hint("(utility -- not invoked directly in the main flow)", direction="from") \
     .hint("(utility -- not invoked directly)")

    g.node(
        "security-review",
        title="/speckit.security-review",
        context=[
            "Dedicated security audit. In pre-impl, reviews plan and tasks for security risks. In post-impl, reviews the actual code diff. Run the /security-review skill as a subagent. In pre-impl, runs in parallel with /speckit.critique.run. In post-impl, runs in parallel with /speckit.code-review.",
            "$ref:stay-alive-spawn",
        ],
        soft=["implementation diff present (post-impl path)"],
        postconditions=["`specs/<feat>/security-review-report.md`"],
    )

    g.node(
        "analyze",
        title="/speckit.analyze",
        context=[
            "Surfaces risks, missing tasks, and over-broad tasks. Output feeds taskstoissues for issue tracking.",
        ],
        hard_missing=["specs/<feat>/tasks.md"],
        soft=[],
        postconditions=["`specs/<feat>/analysis.md`"],
    )

    g.node(
        "taskstoissues",
        title="/speckit.taskstoissues",
        context=[
            "Turns tasks into trackable GitHub issues. Keeps the issue map next to the spec for traceability.",
        ],
        hard_missing=["specs/<feat>/tasks.md"],
        soft=["gh CLI authenticated for the project repo"],
        postconditions=["gh issues created + `specs/<feat>/issue-map.md`"],
    )

    g.node(
        "checkpoint-commit",
        title="/speckit.checkpoint.commit",
        context=[
            "Mid-cycle checkpoints lock in spec/plan/tasks before execution. The final checkpoint locks in the verified, reviewed, retroed feature before archive.",
        ],
        hard_missing=["specs/<feat>/spec.md"],
        soft=["working tree contains changes worth committing"],
        postconditions=["git commit (+ tag for the final checkpoint)"],
        conditional=[
            "After `checkpoint.commit`, drift handling moves from `/speckit.refine.update` / `/speckit.iterate.define` to `/speckit.reconcile.run`.",
        ],
    ).hint("(any milestone where committing is appropriate)", direction="from") \
     .hint("(next phase per workflow)")

    # ======================================================================
    # Phase: implementation (agent-assign) + deprecated implement
    # ======================================================================
    g.node(
        "agent-assign-assign",
        title="/speckit.agent-assign.assign",
        context=[
            "Scans `.claude/agents/` and `~/.claude/agents/` and matches tasks to specialised sub-agents. Review the proposed assignments before validate.",
        ],
        hard_missing=["specs/<feat>/tasks.md"],
        soft=[],
        postconditions=["`specs/<feat>/agent-assignments.yml`"],
    )

    g.node(
        "agent-assign-validate",
        title="/speckit.agent-assign.validate",
        context=[
            "Validates that referenced agents actually exist, that every task has an assignment, and that phase ordering is consistent. Failures route back to assign.",
        ],
        hard_missing=["specs/<feat>/agent-assignments.yml"],
        soft=[],
        postconditions=["(no artefact -- read-only validation; report printed to stdout)"],
    )

    g.node(
        "agent-assign-execute",
        title="/speckit.agent-assign.execute",
        context=[
            "Replaces the deprecated `/speckit.implement` with per-task sub-agent execution. Each agent runs in its own context.",
            "Claude turbo-execute (dynamic workflows only): you MAY run per-task execution as one Workflow instead of invoking each agent serially; if workflows are unavailable or the user declines, fall back to serial execution (identical result, slower).",
            "Do NOT re-run `assign`/`validate`; consume their output.",
            "Author the Workflow from `specs/<feat>/tasks.md` + `specs/<feat>/agent-assignments.yml`: group tasks by dependency level (respect depends-on); tasks within a level are independent.",
            "Per level, `parallel()` one `agent()` per task with `agentType` = the agent in `agent-assignments.yml` and `isolation: 'worktree'`; pass task IDs, spec/plan excerpts, scope, and verification commands in the prompt.",
            "Pipeline each task execute -> its own verify in one stage; emit `specs/<feat>/task-<n>.report.md`. Barrier between dependency levels only.",
            "`model`/`effort` default to each agent's definition; override only at the `agent()` call when a task clearly needs it. All `agentType`s must already exist in `.claude/agents/` -- reuse, do not define new agents.",
            "Checkpoint after the workflow completes, then continue to `/speckit.verify-tasks`.",
        ],
        context_post=[
            "Orchestrator review gate: before accepting a task as done, review the ACTUAL code changes (git diff) against the task in `tasks.md` and the `spec.md`, not just the agent's `task-<n>.report.md`. Self-reports describe intent, not necessarily what landed.",
            "Keep each task's sub-agent alive after it reports. If the work falls short, `SendMessage` specific corrections to the SAME agent so it fixes only those issues with full context -- do not silently accept incomplete work or re-delegate from scratch. This holds even when execution ran as a parallel Workflow: review each agent's emitted diff before its worktree is reconciled, and dismiss an agent only once its task passes review.",
            "Unresolved gaps route forward to `/speckit.verify-tasks` (phantom-completion check) and `/speckit.fix-findings`.",
        ],
        hard_missing=["specs/<feat>/tasks.md", "specs/<feat>/agent-assignments.yml"],
        soft=["every agent referenced in agent-assignments.yml exists in .claude/agents/ or ~/.claude/agents/"],
        postconditions=["code changes per task + `specs/<feat>/task-<n>.report.md` per task"],
    )

    g.node(
        "implement",
        title="/speckit.implement",
        context=[
            "The agent-assign extension routes each task to a specialised sub-agent instead of running implementation in one generalist context. Benchmarks show meaningful quality gains; we've made it the project default.",
        ],
        hard_deprecated=[
            "/speckit.implement is deprecated in this project. Use /speckit.agent-assign.assign -> /speckit.agent-assign.validate -> /speckit.agent-assign.execute instead.",
        ],
        soft=[],
        postconditions=["(invocation blocked)"],
    ).hint("(legacy callers -- this command is no longer the implementation path in this project)", direction="from") \
     .hint("(this command is blocked at the hook layer; the dispatcher's HARD-DEPRECATED check returns a block decision)")

    # ======================================================================
    # Phase: post-impl verification + review
    # ======================================================================
    g.node(
        "verify-tasks",
        title="/speckit.verify-tasks",
        context=[
            "Catches phantom completions -- tasks marked done with no real implementation. Runs in a fresh context to avoid confirmation bias.",
            "Verify against the ACTUAL diff, not the agents' task reports -- a task self-reported as done with no corresponding code change is a phantom completion and must route back to `/speckit.fix-findings`.",
            "Claude turbo-path for Phase 3 QA (dynamic workflows only): post-implementation QA runs as three parallel pairs -- verify-tasks + verify (10/11), code-review + security-review (12/13), sync.analyze + sync.conflicts (15/16); you MAY run all three as one Workflow instead of six manual subagent calls.",
            "If workflows are unavailable or the user declines, run the pairs the normal way per the 50-speckit-workflow steps (identical outputs, not orchestrated).",
            "`parallel()` the six read-only checks mapped to `speckit-verify-tasks`, `speckit-verify`, the `code-review` and `security-review` skills, `speckit-sync`, `speckit-sync-conflicts`.",
            "Each returns structured findings; collect, then run `cleanup` (step 14) on the main thread between the review pair and the sync pair if a finding needs a fix (do NOT auto-fix inside the read-only workflow).",
            "`model`/`effort` default to each agent's definition (verify agents Opus/xhigh; sync agents Sonnet/high) -- do not override unless clearly needed.",
            "Reuse existing `agentType`s; define none. Do NOT touch the DAG nodes -- this is an execution shortcut, not a workflow replacement.",
        ],
        hard_missing=["specs/<feat>/tasks.md"],
        soft=[],
        postconditions=["`specs/<feat>/verify-tasks-report.md`"],
        conditional=[
            "If verify-tasks surfaces phantom completions, /speckit.converge appends the real implementation work as traceable tasks.",
        ],
    )

    g.node(
        "verify",
        title="/speckit.verify",
        context=[
            "Validates implementation against the plan. If the diff doesn't address the plan, route back to agent-assign or refine.update.",
        ],
        hard_missing=["specs/<feat>/plan.md"],
        soft=[],
        postconditions=["`specs/<feat>/verify-report.md`"],
        conditional=[
            "If verify surfaces gaps that look like bugs rather than spec violations, exit to /speckit.bugfix.report.",
            "If verify finds unmet FR/SC that is unbuilt work (not a bug or scope change), run /speckit.converge to append the missing work as tasks, then implement via agent-assign.",
        ],
    )

    g.node(
        "converge",
        title="/speckit.converge",
        context=[
            "Closes the gap between spec/plan/tasks intent and what the code actually implements. Reads spec.md + plan.md + tasks.md (constitution as governing constraints), assesses the present state of the code, and APPENDS each piece of remaining work as a new traceable task under a `## Phase N: Convergence` heading.",
            "APPEND-ONLY: never rewrites/renumbers/deletes existing tasks, never edits spec.md/plan.md, never touches application code. If the code already satisfies everything, tasks.md is left byte-for-byte unchanged and the result is reported clean.",
            "Distinct from iterate (scope/intent CHANGE -- edits spec/plan), bugfix (a defect in built code), and fix-findings (fixes review/qa findings). Use converge only when the spec is right but the implementation is incomplete.",
            "Must run only after implementation has run on the current tasks.md. The appended tasks are then completed via the agent-assign flow (NOT /speckit.implement, which is hard-blocked here).",
        ],
        hard_missing=["specs/<feat>/spec.md", "specs/<feat>/plan.md", "specs/<feat>/tasks.md"],
        soft=["implementation diff present (converge assesses built code)"],
        postconditions=[
            "`specs/<feat>/tasks.md` with an appended `## Phase N: Convergence` section (only when gaps were found; unchanged otherwise)",
        ],
        conditional=[
            "If converge reported a clean result (tasks.md byte-for-byte unchanged, no Convergence phase appended), there is no new work -- resume the Phase 3 QA step you came from instead of re-entering implementation.",
        ],
    )

    g.node(
        "review-run",
        title="/speckit.review.run",
        context=[
            "Orchestrates the granular review.{code,comments,tests,errors,types,simplify} variants. Findings feed fix-findings.",
            "Spawn each review sub-agent with a stay-alive instruction: 'report your findings and wait for my review -- do not end your turn; I may SendMessage to ask you to clarify or reassess a finding.'",
        ],
        context_post=[
            "Orchestrator review gate: triage the review sub-agents' findings before routing to fix-findings -- keep each reviewer alive and `SendMessage` to clarify ambiguous or low-confidence findings rather than forwarding them wholesale. Dismiss a reviewer only once you have triaged its findings.",
        ],
        hard_missing=["specs/<feat>/verify-report.md"],
        soft=[],
        postconditions=["`specs/<feat>/review-report.md`"],
    )

    # granular review variants -- all share the stay-alive fragment and route
    # back to review.run + fix-findings (the 5 malformed single-string going_to
    # entries are split into two real edges each here).
    g.node(
        "review-code",
        title="/speckit.review.code",
        context=["$ref:stay-alive"],
        soft=["implementation diff exists"],
    ).hint("(direct invocation for a focused code review)", direction="from")

    g.node(
        "review-comments",
        title="/speckit.review.comments",
        context=["$ref:stay-alive"],
        soft=["implementation diff"],
    ).hint("(direct invocation)", direction="from")

    g.node(
        "review-errors",
        title="/speckit.review.errors",
        context=["$ref:stay-alive"],
        soft=["implementation diff"],
    ).hint("(direct invocation)", direction="from")

    g.node(
        "review-simplify",
        title="/speckit.review.simplify",
        context=["$ref:stay-alive"],
        soft=["implementation diff"],
    ).hint("(direct invocation)", direction="from")

    g.node(
        "review-tests",
        title="/speckit.review.tests",
        context=["$ref:stay-alive"],
        soft=["test files in the diff"],
    ).hint("(direct invocation)", direction="from")

    g.node(
        "review-types",
        title="/speckit.review.types",
        context=["$ref:stay-alive"],
        soft=["typed source in the diff"],
    ).hint("(direct invocation)", direction="from")

    g.node(
        "qa-run",
        title="/speckit.qa.run",
        context=[
            "Systematic QA: browser-driven or CLI-based acceptance validation. Heavier than verify; reserved for features that need real-world exercise.",
        ],
        hard_missing=["specs/<feat>/review-report.md"],
        soft=[],
        postconditions=["`specs/<feat>/qa-report.md`"],
    )

    g.node(
        "qa-qa-template",
        title="/speckit.qa.qa-template",
    ).hint("(utility)", direction="from").hint("(utility -- not invoked directly)")

    g.node(
        "code-review",
        title="/speckit.code-review",
        context=[
            "General-purpose code review: correctness, regressions, security risks, missing tests, performance, maintainability. Complements the spec-aware review.run. Run the /code-review skill as a subagent against the current branch diff. Can run in parallel with /speckit.security-review.",
            "Spawn the review subagent with an explicit stay-alive instruction: 'report your findings and wait for my review -- do not end your turn; I may SendMessage to clarify findings.' Triage the findings before routing to fix-findings.",
        ],
        soft=["implementation diff present"],
        postconditions=["`specs/<feat>/code-review-report.md`"],
    )

    g.node(
        "fix-findings",
        title="/speckit.fix-findings",
        context=[
            "Automated analyze-fix-reanalyze loop bounded by `max_iterations` (default 10 in our override).",
            "When you spawn the fixing sub-agent, instruct it to stay alive after reporting: 'apply the fixes, report what you changed, and wait for my review -- do not end your turn; I may SendMessage corrections.'",
        ],
        context_post=[
            "Orchestrator review gate: do NOT dismiss the fixing sub-agent the moment it reports. Review the actual code changes against the original findings first. If a fix is incomplete or introduced new issues, `SendMessage` the specific problems to the SAME agent so it corrects only those with full context. Dismiss only once the fixes pass your review.",
        ],
        soft=["`specs/<feat>/review-report.md` or `qa-report.md` with findings"],
    )

    g.node(
        "cleanup",
        title="/speckit.cleanup",
        context=[
            "Post-impl hygiene: dead-code removal, unused imports, debug statements. Our override enables aggressive dead-code removal.",
        ],
        soft=["implementation diff present"],
        postconditions=["`specs/<feat>/cleanup-report.md`"],
    )

    # ======================================================================
    # Phase: memory capture + sync/drift
    # ======================================================================
    g.node(
        "memory-md-capture",
        title="/speckit.memory-md.capture",
        context=[
            "Human-in-the-loop: capture proposes durable lessons; you approve before they land in BUGS.md / DECISIONS.md / LESSONS.md. Skip noise; prefer pattern-level captures over one-off observations.",
        ],
        hard_missing=["docs/memory/INDEX.md"],
        soft=["specs/<feat>/verify-report.md"],
        postconditions=["additions to `docs/memory/{BUGS,DECISIONS,LESSONS}.md`"],
    )

    g.node(
        "memory-md-capture-from-diff",
        title="/speckit.memory-md.capture-from-diff",
        context=[
            "Reviews `git diff` and proposes lessons. Optimised for rapid bug-fix capture; lower ceremony than `/speckit.memory-md.capture`.",
        ],
        hard_missing=["docs/memory/INDEX.md"],
        soft=[],
        postconditions=["additions to `docs/memory/BUGS.md` (and optionally DECISIONS.md)"],
        conditional=["If the diff is purely formatting / whitespace, this is a no-op."],
    ).hint("(any post-quick-fix moment with a meaningful git diff)", direction="from") \
     .hint("(return to invoker -- typically verify or close-out)")

    g.node(
        "memory-md-share-lesson",
        title="/speckit.memory-md.share-lesson",
        context=[
            "Anonymises paths via SHA-256 before elevating the lesson to the shared global pool. Never share lessons containing secrets or proprietary identifiers.",
        ],
        hard_missing=["docs/memory/LESSONS.md"],
        soft=[],
        postconditions=["global shared-lessons store updated"],
    ).hint("(manual: when a local lesson has been validated and is worth sharing)", direction="from")

    g.node(
        "memory-md-sync-shared",
        title="/speckit.memory-md.sync-shared",
        context=[
            "Syncs matching tech-stack lessons from other projects into `docs/memory/SHARED_LESSONS.md`. Run at feature-start to absorb cross-project learnings.",
        ],
        hard_missing=["docs/memory/INDEX.md"],
        soft=[],
        postconditions=["`docs/memory/SHARED_LESSONS.md` refreshed"],
    ).hint("(new feature start -- bring matching tech-stack lessons into local context)", direction="from") \
     .hint("/speckit.plan - /speckit.specify (the imported lessons inform planning)")

    g.node(
        "memory-md-prepare-context",
        title="/speckit.memory-md.prepare-context",
        context=[
            "Use when the implementation is drifting and the agent needs to re-anchor in the memory index. Cheap to invoke; doesn't mutate spec/plan/tasks.",
        ],
        hard_missing=["docs/memory/INDEX.md"],
        soft=[],
        postconditions=["refreshed local DB cache + regenerated synthesis blocks"],
    ).hint("(any active implementation phase -- mid-cycle context refresh)", direction="from") \
     .hint("(return to the phase that invoked it -- agent-assign.execute, verify, review, etc.)")

    g.node(
        "memory-md-audit",
        title="/speckit.memory-md.audit",
        context=[
            "Finds contradictions, stale items, and duplicates across the memory tree. Read the proposals carefully before accepting cleanups.",
        ],
        hard_missing=["docs/memory/INDEX.md"],
        soft=[],
        postconditions=["`docs/memory/audit-report.md`"],
    ).hint("(periodic memory hygiene -- invoke when memory gets noisy)", direction="from")

    g.node(
        "memory-md-log-finding",
        title="/speckit.memory-md.log-finding",
        context=[
            "Converts audit findings into actionable follow-ups (typically gh issues).",
        ],
        hard_missing=["docs/memory/audit-report.md"],
        soft=[],
        postconditions=["gh issues opened OR project tracker entries created"],
    ).hint("(return -- terminal for the audit sub-cycle)")

    g.node(
        "memory-md-token-report",
        title="/speckit.memory-md.token-report",
        context=[
            "Compares estimated token usage of full vs optimised retrieval. Use to decide whether the optimizer is paying off.",
        ],
        hard_missing=["docs/memory/INDEX.md"],
        soft=[],
        postconditions=["(no artefact; report printed)"],
    ).hint("(anytime -- token / context cost audit)", direction="from") \
     .hint("(return -- advisory)")

    g.node(
        "sync-analyze",
        title="/speckit.sync.analyze",
        context=["Detects drift between specs and implementation. Read-only."],
        soft=["implementation diff"],
        postconditions=["`specs/<feat>/sync-report.md`"],
        conditional=[
            "If sync.analyze shows the code lacks work the spec calls for (drift, not a scope change), /speckit.converge appends it as tasks.",
        ],
    )

    g.node(
        "sync-conflicts",
        title="/speckit.sync.conflicts",
        context=[
            "Surfaces contradictions between specs or between specs and shared interfaces/contracts. Read-only.",
        ],
        hard_missing=["specs/<feat>/sync-report.md"],
        soft=[],
    )

    g.node(
        "reconcile",
        title="/speckit.reconcile.run",
        context=[
            "After /speckit.checkpoint.commit, refine and iterate are no longer appropriate -- reconcile is the drift-handling tool because it updates the spec to match the as-shipped implementation.",
        ],
        soft=["specs/<feat>/sync-report.md"],
        postconditions=["`specs/<feat>/reconcile-report.md`"],
    ).hint("(drift detected -- any post-checkpoint phase where spec <-> implementation diverged)", direction="from")

    g.node(
        "retro-run",
        title="/speckit.retro.run",
        context=[
            "Sprint-style retro: metrics, spec accuracy, improvements. Feeds DECISIONS.md if the team accepts changes.",
        ],
        soft=["specs/<feat>/sync-report.md"],
        postconditions=["`specs/<feat>/retro-report.md`"],
    )

    g.node(
        "retro-retro-template",
        title="/speckit.retro.retro-template",
    ).hint("(utility)", direction="from").hint("(utility -- not invoked directly)")

    g.node(
        "archive",
        title="/speckit.archive.run",
        context=[
            "Terminal step. Moves `specs/<feat>/` to `specs/archived/<feat>/`. Don't archive features with unresolved findings.",
        ],
        hard_missing=["specs/<feat>/verify-report.md", "specs/<feat>/review-report.md"],
        soft=[],
        postconditions=["`specs/<feat>/` moved to `specs/archived/<feat>/`"],
    ).hint("(terminal -- feature shipped)")

    # ======================================================================
    # Phase: refine loop
    # ======================================================================
    g.node(
        "refine-update",
        title="/speckit.refine.update",
        context=[
            "Refine is for INCREMENTAL edits to existing artefacts. If the change is actually a scope pivot, exit refine and run `/speckit.iterate.define` or specify a new feature.",
            "After `/speckit.checkpoint.commit`, drift handling moves to `/speckit.reconcile.run` instead.",
        ],
        hard_missing=["specs/<feat>/spec.md"],
        soft=[],
        postconditions=["the targeted artefact(s) updated"],
        conditional=[
            "If the change touches more than two phases, this is probably an iterate rather than a refine -- consider exiting the refine loop.",
        ],
    ).hint(
        "/speckit.specify - /speckit.clarify - /speckit.plan - /speckit.tasks - /speckit.checklist - /speckit.critique.run - /speckit.analyze - /speckit.taskstoissues",
        direction="from",
    ).hint("(any phase before /speckit.checkpoint.commit)", direction="from")

    g.node(
        "refine-diff",
        title="/speckit.refine.diff",
        context=[
            "Generates a structured diff of what refine.update changed so propagate can apply downstream edits.",
        ],
        soft=["artefact(s) that just changed"],
        postconditions=["`specs/<feat>/refine-diff.md`"],
    )

    g.node(
        "refine-propagate",
        title="/speckit.refine.propagate",
        context=[
            "Mechanically pushes the diff into downstream artefacts (plan, tasks, issues). Don't accept blindly -- review propagated edits.",
        ],
        hard_missing=["specs/<feat>/refine-diff.md"],
        soft=[],
        postconditions=["downstream artefacts updated"],
    )

    g.node(
        "refine-status",
        title="/speckit.refine.status",
        context=[
            "Final step of the refine loop. After this, re-enter at /speckit.specify and walk briefly through every downstream stage to confirm artefacts still hold up.",
        ],
        soft=["(none -- read-only status)"],
        postconditions=["(no artefact; status printed)"],
        conditional=[
            "At each downstream stage you re-enter, confirm the artefact is still valid or update it. Do not skip stages -- an upstream change can invalidate any of them.",
        ],
    )

    # ======================================================================
    # Phase: iterate loop + roadmap gate
    # ======================================================================
    g.node(
        "iterate-define",
        title="/speckit.iterate.define",
        context=[
            "Iterate is for SCOPE / INTENT pivots -- different from refine, which handles incremental edits. Capture the iteration intent here, then apply.",
        ],
        hard_missing=["specs/<feat>/spec.md"],
        soft=[],
        postconditions=["`specs/<feat>/pending-iteration.md`"],
    ).hint(
        "/speckit.specify - /speckit.clarify - /speckit.plan - /speckit.tasks - /speckit.checklist - /speckit.critique.run - /speckit.analyze - /speckit.taskstoissues",
        direction="from",
    ).hint("(any phase before /speckit.checkpoint.commit)", direction="from")

    g.node(
        "iterate-apply",
        title="/speckit.iterate.apply",
        context=[
            "Applies the iteration intent to spec + plan + tasks. After this, re-enter at /speckit.specify (mandatory) and walk forward through every downstream stage.",
        ],
        hard_missing=["specs/<feat>/pending-iteration.md"],
        soft=[],
        postconditions=[
            "spec/plan/tasks updated per the iteration",
            "the `/speckit.roadmap.write` entry for this feature is back in sync with the iterated spec/plan/tasks",
        ],
        conditional=[
            "At each downstream stage you re-enter, confirm the artefact is still valid or update it. Do not skip stages.",
        ],
    )

    g.node(
        "roadmap-write",
        title="/speckit.roadmap.write",
        context=[
            "Records / refreshes this feature's entry in the project roadmap so the roadmap reflects the current spec/plan/tasks. Run it after an iteration re-scopes the feature to keep the roadmap entry in sync.",
        ],
        soft=["specs/<feat>/spec.md"],
        postconditions=["the project roadmap entry for `<feat>` updated to match the current spec/plan/tasks"],
    ).hint("(return -- roadmap synced; resume the iterate re-entry walk at /speckit.specify)")

    # ======================================================================
    # Phase: bugfix sub-cycle
    # ======================================================================
    g.node(
        "bugfix-report",
        title="/speckit.bugfix.report",
        context=[
            "If the underlying issue is a spec gap (not a bug), exit to /speckit.refine.update instead.",
        ],
        soft=["(none)"],
        postconditions=["`specs/<feat>/bug-<n>.md`"],
    ).hint("(bug intake -- external signal)", direction="from")

    g.node(
        "bugfix-verify",
        title="/speckit.bugfix.verify",
        context=["Reproduce the bug with a failing test before patching."],
        hard_missing=["specs/<feat>/bug-*.md"],
        soft=[],
    )

    g.node(
        "bugfix-patch",
        title="/speckit.bugfix.patch",
        context=["Apply the fix; rerun the failing test to confirm."],
        hard_missing=["specs/<feat>/bug-*.md"],
        soft=[],
    )

    # ======================================================================
    # Phase: tinyspec sub-cycle
    # ======================================================================
    g.node(
        "tinyspec-classify",
        title="/speckit.tinyspec.classify",
        soft=["(none)"],
        postconditions=["`specs/<feat>/tinyspec.md` (classification block)"],
    ).hint("(quick-start entry -- minimal scope feature)", direction="from")

    g.node(
        "tinyspec-tinyspec",
        title="/speckit.tinyspec.tinyspec",
        hard_missing=["specs/<feat>/tinyspec.md"],
        soft=[],
    )

    g.node(
        "tinyspec-implement",
        title="/speckit.tinyspec.implement",
        hard_missing=["specs/<feat>/tinyspec.md"],
        soft=[],
    )

    # ======================================================================
    # Phase: github-issues
    # ======================================================================
    g.node(
        "github-issues-import",
        title="/speckit.github-issues.import",
        context=[
            "Imports issues into spec scaffolding so brownfield projects don't lose existing tracker context.",
        ],
        soft=["gh CLI authenticated; repo configured in github-issues config"],
        postconditions=["`specs/<feat>/imported-issues.md`"],
    ).hint("(new project with existing GitHub issues to ingest)", direction="from")

    g.node(
        "github-issues-link",
        title="/speckit.github-issues.link",
        soft=["specs/<feat>/issue-map.md"],
    ).hint("(post-/speckit.tasks -- link tasks to issues)", direction="from") \
     .hint("(return)")

    g.node(
        "github-issues-sync",
        title="/speckit.github-issues.sync",
        soft=["gh CLI authenticated"],
    ).hint("(mid-cycle -- keep issues in sync with tasks)", direction="from") \
     .hint("(return -- advisory)")

    # ======================================================================
    # Phase: fleet orchestration
    # ======================================================================
    g.node(
        "fleet",
        title="/speckit.fleet.run",
        context=[
            "Human-in-the-loop gates across all SpecKit phases. Our override pins primary=opus / review=sonnet and caps concurrency at 2.",
        ],
        soft=["(none)"],
        postconditions=["`specs/<feat>/fleet-state.md`"],
    ).hint("(orchestration entry -- running multiple speckit phases in parallel)", direction="from")

    g.node(
        "fleet-review",
        title="/speckit.fleet.review",
        hard_missing=["specs/<feat>/fleet-state.md"],
        soft=[],
    ).hint("(downstream gates as defined by fleet config)")

    # ======================================================================
    # Phase: conduct (single-phase executor)
    # ======================================================================
    g.node(
        "conduct",
        title="/speckit.conduct.run",
        context=[
            "Executes one speckit phase via a sub-agent. Lighter-weight than running a full workflow; use when you want one phase done in isolation.",
            "Spawn the sub-agent with a stay-alive instruction: 'produce the artefact, report it, and wait for my review -- do not end your turn; I may SendMessage corrections.'",
        ],
        context_post=[
            "Orchestrator review gate: do NOT dismiss the sub-agent the moment it reports. Review the produced artefact(s) first. If they fall short, `SendMessage` the specific issues to the SAME agent so it fixes only those with full context. Dismiss only once the artefact passes your review.",
        ],
        soft=["a spec/plan/tasks artefact appropriate to the phase being conducted"],
        postconditions=["(artefact(s) of the phase that was conducted)"],
        conditional=[
            "After conduct completes AND the produced artefact passes your review, the regular DAG resumes -- pick the next node based on which artefact you just produced.",
        ],
    ).hint("(any phase -- single-phase executor)", direction="from") \
     .hint("(return to surrounding phase; conduct does not advance the DAG)")

    # ======================================================================
    # Phase: status / doctor / worktree advisory + utility
    # ======================================================================
    g.node(
        "status-show",
        title="/speckit.status.show",
        context=["Read-only. Surfaces current feature + which artefacts exist."],
        soft=["(none; reads .specify/feature.json + spec/plan/task artefacts)"],
        postconditions=["(no artefact)"],
        conditional=[
            "Use the output to pick the next DAG node -- typically the first phase whose artefact is missing.",
        ],
    ).hint("(anytime -- advisory)", direction="from").hint("(return to invoker)")

    g.node(
        "doctor-check",
        title="/speckit.doctor.check",
        context=["Pure diagnostic. Does not mutate project state. Safe from any phase."],
        soft=["(none)"],
        postconditions=["(no artefact; report printed to stdout)"],
        conditional=[
            "If doctor flags missing extensions or stale workflows, run `speckit-upgrade-project` (fish) to refresh `.specify/` and `specify extension update` to refresh extensions.",
        ],
    ).hint("(anytime -- advisory health check)", direction="from") \
     .hint("(return to whatever phase you were in)")

    g.node(
        "worktree-create",
        title="/speckit.worktree.create",
        context=[
            "Spawns an isolated git worktree so parallel features don't trample each other. Pair with the worktree-isolation pattern in agent-assign.execute when running multiple agents.",
        ],
        soft=["(none)"],
        postconditions=["new git worktree under the configured worktree root"],
    ).hint("(parallel-work request from any implementation phase)", direction="from")

    g.node(
        "worktree-list",
        title="/speckit.worktree.list",
        soft=["(none)"],
    ).hint("(anytime -- advisory)", direction="from")

    g.node(
        "worktree-clean",
        title="/speckit.worktree.clean",
        context=["Removes the per-feature worktree. Don't run mid-cycle."],
        soft=["feature has been archived"],
    ).hint("(cleanup time, after the feature is archived)", direction="from") \
     .hint("(terminal)")

    # ======================================================================
    # Edges (canonical store; came_from/going_to are projections)
    # ======================================================================
    # -- bootstrap / memory init --
    g.edge("memory-md-init", "memory-md-init-project", "default", note="recommended next -- profile the project for shared-memory channels")
    g.edge("memory-md-init", "constitution", "conditional", note="preferred for greenfield")
    g.edge("memory-md-init", "specify", "conditional", note="acceptable if constitution already exists")
    g.edge("memory-md-init-project", "memory-md-sync-shared", "optional", note="pull matching shared lessons once channels are configured")
    g.edge("constitution", "memory-md-specify", "default", note="before_specify hook prepares memory context")
    g.edge("constitution", "specify", "conditional", note="if memory-md is not installed")
    g.edge("memory-md-specify", "specify", "default", note="proceed to write the spec with memory context loaded")

    # -- specify / clarify / plan --
    g.edge("specify", "clarify", "default")
    g.edge("clarify", "memory-md-plan-with-memory", "default", note="memory-md is installed by default")
    g.edge("clarify", "plan", "conditional", note="only if memory-md is not installed")
    g.edge("memory-md-plan-with-memory", "plan", "default", note="the planner reads memory-synthesis.md")
    g.edge("plan", "tasks", "default")
    g.edge("plan", "critique-run", "conditional", note="only if user explicitly requests critique before tasks")
    g.edge("tasks", "checklist", "default", note="requirements-quality gate over spec + plan + tasks")

    # -- pre-impl review (checklist -> critique + security-review -> analyze) --
    # critique.run is the default forward; security-review runs in parallel
    # (mandatory -- it cannot be skipped in the parallel gate). The skip path
    # formerly went to diagram.dependencies (cut) -> re-pointed to analyze.
    g.edge("checklist", "critique-run", "default", note="parallel with security-review -- review plan/tasks before implementation")
    g.edge("checklist", "security-review", "mandatory", note="pre-impl -- runs in parallel with critique.run")
    g.edge("checklist", "analyze", "conditional", note="only if user explicitly skips critique + security-review")
    # critique.run forward formerly -> diagram.dependencies (cut); now -> analyze.
    g.edge("critique-run", "analyze", "default", note="after security-review also completes")
    g.edge("critique-run", "refine-update", "conditional", note="if critique reveals plan-level rework")
    # security-review pre-impl forward formerly -> diagram.dependencies (cut);
    # now -> analyze. Post-impl branches stay conditional.
    g.edge("security-review", "analyze", "default", note="pre-impl -- after critique also completes")
    g.edge("security-review", "fix-findings", "conditional", note="post-impl, if security findings")
    g.edge("security-review", "cleanup", "conditional", note="post-impl, clean, after code-review also completes")
    g.edge("analyze", "taskstoissues", "default")
    g.edge("taskstoissues", "checkpoint-commit", "default", note="lock in the spec/plan/tasks before execution")

    # -- checkpoint -> implementation / archive --
    # checkpoint.commit is a SHARED node for both the mid-cycle and the final
    # checkpoint. The forward-to-implementation edge is therefore conditional on
    # this being the mid-cycle checkpoint -- making it 'default' would close a
    # real cycle (retro.run -> checkpoint.commit -> agent-assign.assign -> ... ->
    # retro.run) in the primary backbone.
    g.edge("checkpoint-commit", "agent-assign-assign", "conditional", note="after the mid-cycle checkpoint that follows taskstoissues")
    g.edge("checkpoint-commit", "archive", "conditional", note="after the final checkpoint that follows retro.run")

    # -- agent-assign chain --
    g.edge("agent-assign-assign", "agent-assign-validate", "default")
    g.edge("agent-assign-validate", "agent-assign-execute", "default")
    g.edge("agent-assign-validate", "agent-assign-assign", "conditional", note="if validation surfaces gaps")
    g.edge("agent-assign-execute", "verify-tasks", "default", note="confirm every task actually shipped code")
    g.edge("agent-assign-execute", "verify", "conditional", note="only if user explicitly skips verify-tasks")
    # deprecated implement redirects to the agent-assign entry point.
    g.edge("implement", "agent-assign-assign", "optional", note="deprecated -- use the agent-assign flow instead")

    # -- post-impl verification --
    g.edge("verify-tasks", "verify", "default")
    g.edge("verify-tasks", "converge", "conditional", note="phantom completions -- append the real implementation work as traceable tasks")
    g.edge("verify", "review-run", "default")
    g.edge("verify", "bugfix-report", "conditional", note="if verify surfaces gaps that look like bugs rather than spec violations")
    g.edge("verify", "converge", "conditional", note="if verify finds unmet FR/SC that is unbuilt work, not a bug or scope change")
    # converge: implement the appended Convergence tasks via the agent-assign flow.
    g.edge("converge", "agent-assign-assign", "default", note="implement the appended `## Phase N: Convergence` tasks via the agent-assign flow")
    g.edge("converge", "iterate-define", "conditional", note="only if the gap is actually a scope/intent change, not unbuilt work")
    g.edge("sync-analyze", "converge", "conditional", note="drift: the spec calls for work the code lacks")

    # -- review.run orchestrated variants --
    g.edge("review-run", "fix-findings", "conditional", note="if findings, after triage")
    g.edge("review-run", "qa-run", "default", note="clean")
    for variant in ("review-code", "review-comments", "review-errors", "review-simplify", "review-tests", "review-types"):
        # review.run orchestrates each variant; each routes back to review.run
        # and onward to fix-findings (the 5 malformed combined going_to strings
        # are split into two real edges here).
        g.edge("review-run", variant, "optional", note="orchestrated granular review variant")
        g.edge(variant, "review-run", "conditional", note="re-aggregate after the granular pass")
        g.edge(variant, "fix-findings", "conditional", note="if findings")

    # -- qa / code-review / fix-findings / cleanup --
    g.edge("qa-run", "code-review", "default", note="clean -- runs in parallel with security-review")
    g.edge("qa-run", "security-review", "mandatory", note="post-impl -- runs in parallel with code-review")
    g.edge("qa-run", "fix-findings", "conditional", note="failed")
    g.edge("code-review", "cleanup", "default", note="clean, after security-review also completes")
    g.edge("code-review", "fix-findings", "conditional", note="if findings")
    g.edge("fix-findings", "fix-findings", "conditional", note="loop -- when review shows the fix is incomplete or regressed")
    g.edge("fix-findings", "review-run", "conditional", note="loop until clean, after the fixes pass review")
    g.edge("fix-findings", "verify", "conditional", note="re-verify after substantial fixes")
    g.edge("cleanup", "memory-md-capture", "default", note="capture lessons while context is fresh")
    g.edge("cleanup", "sync-analyze", "conditional", note="if no lessons to capture")

    # -- memory capture + sync/drift -> retro -> checkpoint -> archive --
    g.edge("memory-md-capture", "sync-analyze", "default", note="proceed to drift check")
    g.edge("memory-md-capture", "memory-md-share-lesson", "conditional", note="if a captured lesson is generally applicable across projects")
    g.edge("verify", "memory-md-capture", "conditional", note="early capture")
    g.edge("bugfix-patch", "memory-md-capture-from-diff", "default", note="fast capture")
    g.edge("memory-md-share-lesson", "memory-md-sync-shared", "default", note="propagate to other projects")
    g.edge("memory-md-capture", "memory-md-sync-shared", "optional", note="bring matching tech-stack lessons into local context")
    g.edge("memory-md-audit", "memory-md-log-finding", "default", note="turn audit findings into tracker items")
    g.edge("sync-analyze", "sync-conflicts", "default")
    g.edge("sync-conflicts", "retro-run", "default")
    g.edge("sync-conflicts", "reconcile", "conditional", note="if conflicts need active resolution")
    g.edge("reconcile", "refine-update", "conditional", note="if the spec needs structured edits to catch up")
    g.edge("reconcile", "sync-analyze", "conditional", note="to confirm reconciliation closed the drift")
    g.edge("retro-run", "checkpoint-commit", "default", note="final checkpoint")

    # -- refine loop --
    g.edge("refine-update", "refine-diff", "default")
    g.edge("refine-update", "reconcile", "optional", note="post-checkpoint drift handling")
    g.edge("refine-diff", "refine-propagate", "default")
    g.edge("refine-propagate", "refine-status", "default")
    g.edge("refine-status", "specify", "mandatory", note="MANDATORY re-entry -- walk forward through every downstream stage to assess impact")

    # -- iterate loop + roadmap gate --
    g.edge("iterate-define", "iterate-apply", "default")
    g.edge("iterate-apply", "specify", "mandatory", note="MANDATORY re-entry -- walk forward through every downstream stage")
    # Locked roadmap gate: after applying an iteration, re-sync the roadmap.
    g.edge("iterate-apply", "roadmap-write", "mandatory", note="re-sync the roadmap entry to the iterated spec/plan/tasks")

    # -- bugfix sub-cycle --
    g.edge("verify", "bugfix-report", "optional", note="if a verification failure triages as a bug rather than a spec gap")
    g.edge("bugfix-report", "bugfix-verify", "default")
    g.edge("bugfix-verify", "bugfix-patch", "default")
    g.edge("bugfix-patch", "verify", "conditional", note="re-verify if the fix touched implementation")

    # -- tinyspec sub-cycle --
    g.edge("specify", "tinyspec-classify", "conditional", note="if spec is one-paragraph and full SDD is overkill")
    g.edge("tinyspec-classify", "tinyspec-tinyspec", "default")
    g.edge("tinyspec-tinyspec", "tinyspec-implement", "default")
    g.edge("tinyspec-implement", "verify", "conditional", note="short cycle")

    # -- github-issues --
    g.edge("github-issues-import", "specify", "conditional", note="treat imported issue as feature seed")
    g.edge("github-issues-import", "plan", "conditional", note="if the issue is well-defined enough to skip specify")

    # -- fleet --
    g.edge("fleet", "fleet-review", "default")

    # -- conduct self-loop --
    g.edge("conduct", "conduct", "conditional", note="loop -- when review finds issues in the produced artefact")

    # -- worktree family --
    g.edge("worktree-create", "worktree-list", "optional", note="confirm the worktree was created")
    g.edge("worktree-list", "worktree-clean", "optional", note="after the feature is archived")

    # ======================================================================
    # Phase groupings (documentary only -- do not affect emitted JSON)
    # ======================================================================
    g.phase("bootstrap", ["memory-md-init", "memory-md-init-project", "constitution", "memory-md-specify"])
    g.phase("specify", ["specify", "clarify", "memory-md-plan-with-memory", "plan", "tasks"])
    g.phase("pre-impl-review", ["checklist", "critique-run", "security-review", "analyze", "taskstoissues", "checkpoint-commit"])
    g.phase("implement", ["agent-assign-assign", "agent-assign-validate", "agent-assign-execute", "implement", "converge"])
    g.phase("post-impl-review", ["verify-tasks", "verify", "review-run", "review-code", "review-comments", "review-errors", "review-simplify", "review-tests", "review-types", "qa-run", "code-review", "fix-findings", "cleanup"])
    g.phase("close-out", ["memory-md-capture", "memory-md-capture-from-diff", "sync-analyze", "sync-conflicts", "reconcile", "retro-run", "archive"])
    g.phase("refine", ["refine-update", "refine-diff", "refine-propagate", "refine-status"])
    g.phase("iterate", ["iterate-define", "iterate-apply", "roadmap-write"])
    g.phase("bugfix", ["bugfix-report", "bugfix-verify", "bugfix-patch"])
    g.phase("tinyspec", ["tinyspec-classify", "tinyspec-tinyspec", "tinyspec-implement"])
    g.phase("github-issues", ["github-issues-import", "github-issues-link", "github-issues-sync"])
    g.phase("orchestration", ["fleet", "fleet-review", "conduct"])
    g.phase("memory", ["memory-md-share-lesson", "memory-md-sync-shared", "memory-md-prepare-context", "memory-md-audit", "memory-md-log-finding", "memory-md-token-report"])
    g.phase("utility", ["status-show", "doctor-check", "worktree-create", "worktree-list", "worktree-clean", "critique-critique-template", "qa-qa-template", "retro-retro-template"])

    return g


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="build_nodes.py",
        description=(
            "Authoring builder for the SpecKit DAG. Compiles a typed in-memory "
            "graph to the dispatcher-compatible scripts/nodes.json."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="regenerate to a buffer and diff against committed nodes.json; exit 1 on drift",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="run build-time validation only (no write, no diff)",
    )
    parser.add_argument(
        "--print",
        dest="do_print",
        action="store_true",
        help="write the generated JSON to stdout (no file write)",
    )
    parser.add_argument(
        "--out",
        default=DEFAULT_NODES_JSON,
        help="path to nodes.json (default: alongside this script)",
    )
    args = parser.parse_args(argv)

    try:
        g = build_main_graph()
    except BuildError as exc:
        sys.stderr.write("BUILD ERROR: %s\n" % (exc,))
        return 2

    if args.validate:
        return cmd_validate(g)

    # Validation is implicit in build()/render(); surface it cleanly.
    try:
        if args.do_print:
            sys.stdout.write(g.render())
            return 0
        if args.check:
            return cmd_check(g, args.out)
        return cmd_write(g, args.out)
    except BuildError as exc:
        sys.stderr.write("BUILD ERROR: %s\n" % (exc,))
        return 2


if __name__ == "__main__":
    sys.exit(main())
