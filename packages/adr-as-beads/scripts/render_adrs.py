#!/usr/bin/env python3
"""Render MADR files from beads `decision` beads.

The bead is the record; the file is a projection of it. Nothing here is a source
of truth, so this never edits a bead and never syncs: it reads the local Dolt
store through `bd export` and writes markdown.

`bd export` rather than `bd list --type decision --json`, which omits `design`,
`notes`, `dependencies`, and `spec_id` -- the fields an ADR is made of. Rather
than `bd show` per bead too: show carries everything but costs ~0.45s each,
where one export costs ~0.45s total and is byte-identical across runs.

Only CLOSED decisions render. A `deferred` bead is a proposed decision nobody
has settled, and an `open` one is being drafted right now; writing either to
docs/adr/ would publish a choice that has not been made.

Exit codes: 0 on success or any environment gap (no `bd`, no database, no
decisions), 1 only when rendering itself fails. A missing tool must not block a
commit -- see the hook-contract fail-open rule.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ADR_DIR = Path("docs/adr")

# Bare `bd` inherits the caller's pager and interactive prompts. A git hook has
# no tty, so an unset pager can hang the commit rather than fail it.
BD_ENV_FLAGS = {"BD_NO_PAGER": "1", "BD_NON_INTERACTIVE": "1"}

# MADR 4.0.0 section order. The bead field each one reads is resolved in
# `render_one`; a section with nothing behind it is omitted rather than emitted
# with a placeholder, because a placeholder reads as an answered question.
_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(title: str) -> str:
    """Kebab-case a title for the filename, collapsing runs of punctuation."""
    return _SLUG_STRIP.sub("-", title.lower()).strip("-") or "untitled"


def run_bd(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str] | None:
    """Run a bd subcommand, returning None when bd is absent or errors.

    Absence is the common case in CI and on a fresh clone, and it is not a
    failure: the committed markdown is already correct there, since whoever
    committed it had the database.
    """
    if shutil.which("bd") is None:
        return None
    import os

    env = dict(os.environ)
    env.update(BD_ENV_FLAGS)
    try:
        return subprocess.run(  # noqa: S603
            ["bd", *args],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def export_decisions(repo: Path) -> list[dict] | None:
    """Return every decision bead, or None when the database is unreachable.

    `bd export` writes to a path rather than stdout, so this uses a temp file
    and reads it back. The export is JSONL: one bead per line.
    """
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "beads.jsonl"
        result = run_bd(["export", "--output", str(out)], repo)
        if result is None or result.returncode != 0 or not out.is_file():
            return None
        rows = []
        for line in out.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                # One malformed line must not discard every other decision.
                continue
    return [r for r in rows if r.get("issue_type") == "decision"]


def sections_from(bead: dict) -> dict[str, str]:
    """Split a bead description on its `## ` headings.

    `bd lint` enforces `## Decision`, `## Rationale`, and
    `## Alternatives Considered` on a decision bead, so the description is
    already sectioned markdown. Anything before the first heading is preamble
    and becomes the context section.
    """
    text = (bead.get("description") or "").strip()
    if not text:
        return {}
    parts = re.split(r"^##\s+(.+?)\s*$", text, flags=re.MULTILINE)
    out: dict[str, str] = {}
    preamble = parts[0].strip()
    if preamble:
        out["_preamble"] = preamble
    for name, body in zip(parts[1::2], parts[2::2]):
        out[name.strip()] = body.strip()
    return out


def supersession(bead: dict) -> tuple[list[str], list[str]]:
    """Return (supersedes, superseded_by) bead ids from typed edges.

    `bd supersede <old> --with <new>` records the edge on the OLD bead pointing
    at the new one, so a bead's own `supersedes` dependency means it has been
    replaced. Reading the edge rather than a metadata key keeps the file and the
    bead from disagreeing, which is what a hand-maintained field allowed.
    """
    superseded_by = [
        dep.get("depends_on_id") or dep.get("id")
        for dep in bead.get("dependencies") or []
        if dep.get("dependency_type") == "supersedes" or dep.get("type") == "supersedes"
    ]
    return [], [d for d in superseded_by if d]


def render_one(bead: dict, number: int) -> str:
    """Render one bead as a MADR document."""
    title = (bead.get("title") or "Untitled decision").strip()
    sections = sections_from(bead)
    _, superseded_by = supersession(bead)

    status = "superseded" if superseded_by else "accepted"
    date = (bead.get("closed_at") or bead.get("updated_at") or "")[:10]

    lines = [
        "<!-- Generated from a beads decision bead. Edit the bead, not this file:",
        f"     bd show {bead.get('id')} -->",
        "---",
        f"number: {number}",
        f"title: {title}",
        f"status: {status}",
        f"date: {date}",
        f"bead: {bead.get('id')}",
    ]
    if spec := bead.get("spec_id"):
        lines.append(f"spec: {spec}")
    if superseded_by:
        lines.append(f"superseded-by: {', '.join(superseded_by)}")
    lines += ["---", "", f"# {title}", ""]

    if superseded_by:
        lines += [
            f"> Superseded by {', '.join(superseded_by)}. Kept because it records"
            " what was believed at the time.",
            "",
        ]

    context = sections.get("Context and Problem Statement") or sections.get("_preamble")
    if context:
        lines += ["## Context and Problem Statement", "", context, ""]
    if drivers := sections.get("Decision Drivers"):
        lines += ["## Decision Drivers", "", drivers, ""]
    if options := sections.get("Alternatives Considered") or sections.get(
        "Considered Options"
    ):
        lines += ["## Considered Options", "", options, ""]

    outcome = sections.get("Decision") or sections.get("Decision Outcome")
    rationale = sections.get("Rationale")
    if outcome or rationale:
        lines += ["## Decision Outcome", ""]
        if outcome:
            lines += [outcome, ""]
        if rationale:
            lines += ["### Rationale", "", rationale, ""]

    if consequences := sections.get("Consequences"):
        lines += ["### Consequences", "", consequences, ""]
    if confirmation := sections.get("Confirmation") or bead.get("acceptance_criteria"):
        lines += ["### Confirmation", "", confirmation, ""]

    # `design` holds rationale, evidence, unknowns, bounds, and alternatives per
    # the carrier doctrine, and notes hold the running narrative. Both are ADR
    # substance rather than metadata, so they render rather than being dropped.
    if design := (bead.get("design") or "").strip():
        lines += ["## More Information", "", design, ""]
    if notes := (bead.get("notes") or "").strip():
        if not design:
            lines += ["## More Information", ""]
        lines += [notes, ""]

    return "\n".join(lines).rstrip() + "\n"


def render_all(repo: Path, *, write: bool = True) -> tuple[list[Path], str | None]:
    """Render every closed decision. Returns (stale-or-written paths, skip reason).

    `write=False` is the --check path and must not touch the tree. An earlier
    version shared one code path and so REPAIRED the drift it was reporting: the
    gate failed, the file was silently corrected, and a second run passed with
    the author's hand edit destroyed and never committed.
    """
    beads = export_decisions(repo)
    if beads is None:
        return [], "no beads database reachable"

    closed = [b for b in beads if b.get("status") == "closed"]
    if not closed:
        return [], "no closed decision beads"

    # Number by creation order, not bead id: `adr-11` must not become 0011 with
    # ten gaps. Ties break on id so the numbering is stable across runs.
    closed.sort(key=lambda b: ((b.get("created_at") or ""), b.get("id") or ""))

    target = repo / ADR_DIR
    if write:
        target.mkdir(parents=True, exist_ok=True)

    changed = []
    for index, bead in enumerate(closed, start=1):
        body = render_one(bead, index)
        path = target / f"{index:04d}-{slugify(bead.get('title') or '')}.md"
        # Compare before writing, so an unrelated commit does not restage every ADR.
        if path.is_file() and path.read_text(encoding="utf-8") == body:
            continue
        changed.append(path)
        if write:
            path.write_text(body, encoding="utf-8")
    return changed, None


def stage(paths: list[Path], repo: Path) -> None:
    """Stage what was written, so it lands in the triggering commit.

    Required, not a convenience: prek fails a commit outright when a hook
    modifies a tracked file and leaves it unstaged, and silently omits a new
    untracked one. Staging is what makes a writing hook viable.
    """
    if not paths:
        return
    try:
        subprocess.run(  # noqa: S603
            ["git", "add", "--", *[str(p) for p in paths]],
            cwd=repo,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def main(argv: list[str]) -> int:
    check_only = "--check" in argv
    repo = Path.cwd()

    try:
        written, skipped = render_all(repo, write=not check_only)
    except Exception as exc:  # noqa: BLE001
        print(f"render-adrs: {exc}", file=sys.stderr)
        return 1

    if skipped:
        # Not a failure. A repository with no decisions yet, or a clone without
        # the database, is the normal case rather than a broken one.
        return 0

    if check_only:
        if written:
            print(
                "render-adrs: these ADR files are stale relative to their beads:",
                file=sys.stderr,
            )
            for path in written:
                print(f"  {path}", file=sys.stderr)
            print("Run the renderer and commit the result.", file=sys.stderr)
            return 1
        return 0

    stage(written, repo)
    for path in written:
        print(f"render-adrs: wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
