"""Regression tests for EXTERNAL marketplace sources in the doc generators.

A marketplace package whose ``source`` is a git repo (not a sibling
``./packages/<dir>``) has no local dir for the canonical ``packages/*`` walk to
produce. Before the external-source support, ``build_inventory.build_context``
rebuilt the whole ``marketplace.packages`` list from that walk, so any
hand-authored external entry was silently DROPPED on the next
``render-docs.py marketplace-block`` run (and the CI staleness gate rewrote
``source`` back to ``./packages/<dir>``).

These tests pin the contract that makes a direct external ``source:`` viable:

* an external entry survives ``build_context`` verbatim (source + ref + subdir),
* it is NOT reported as a "dropped" stale curation entry,
* a name collision (external entry whose name also has a packages/ dir) resolves
  to the LOCAL entry + a warning, never a duplicate,
* local entries are byte-identical (no regression for the common case),
* the entry round-trips through ``render-docs._render_marketplace_block``.

Run via:
  uv run --with pytest --with pyyaml pytest -q .apm/scripts/test_external_marketplace_source.py
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / filename)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bi = _load("build_inventory", "build_inventory.py")
rd = _load("render_docs", "render-docs.py")


def _marketplace(*entries: dict) -> dict:
    return {
        "owner": {"name": "srobroek"},
        "versioning": {"strategy": "tag_pattern"},
        "packages": list(entries),
    }


# --------------------------------------------------------------------------- #
# _is_local_source                                                             #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "source,is_local",
    [
        ("./packages/foo", True),
        ("./path/to/thing", True),
        ("srobroek/project-setup", False),
        ("github.com/srobroek/project-setup", False),
        ("https://github.com/srobroek/project-setup", False),
        ("https://github.com/srobroek/project-setup.git", False),
        ({"type": "github", "repo": "srobroek/project-setup"}, False),
        (None, False),
    ],
)
def test_is_local_source(source, is_local):
    assert bi._is_local_source(source) is is_local


@pytest.mark.parametrize(
    "source,slug",
    [
        ("srobroek/project-setup", "srobroek/project-setup"),
        ("github.com/srobroek/vibe-hero", "srobroek/vibe-hero"),
        ("https://github.com/srobroek/vibe-hero", "srobroek/vibe-hero"),
        ("https://github.com/srobroek/vibe-hero.git", "srobroek/vibe-hero"),
        ("gitlab.com/group/repo", "group/repo"),
        ({"type": "github", "repo": "a/b"}, "a/b"),
        ({"type": "url", "url": "https://github.com/c/d"}, "c/d"),
        ("", ""),
        (None, ""),
    ],
)
def test_external_repo_slug(source, slug):
    assert bi._external_repo_slug(source) == slug


# --------------------------------------------------------------------------- #
# external_marketplace doc-table records                                       #
# --------------------------------------------------------------------------- #


def test_external_marketplace_records_built():
    mk = _marketplace(
        {
            "name": "zzz-demo",
            "source": "srobroek/project-setup",
            "ref": "v1.2.3",
            "category": "project-lifecycle",
            "tags": ["skill", "lifecycle"],
        }
    )
    ctx = bi.build_context(mk)
    em = ctx["external_marketplace"]
    rec = [r for r in em if r["name"] == "zzz-demo"]
    assert rec, "external_marketplace record missing"
    r = rec[0]
    assert r["repo"] == "srobroek/project-setup"
    assert r["ref"] == "v1.2.3"
    assert r["category"] == "project-lifecycle"
    assert r["tags"] == ["skill", "lifecycle"]


def test_external_marketplace_excludes_local_and_collisions():
    # Local packages never appear; a colliding external name (also a local dir)
    # is excluded from external_marketplace too (local wins).
    mk = _marketplace({"name": "agent-builder", "source": "srobroek/elsewhere", "ref": "main"})
    ctx = bi.build_context(mk)
    names = {r["name"] for r in ctx["external_marketplace"]}
    assert "agent-builder" not in names
    assert not any(bi._is_local_source(r.get("source")) for r in ctx["external_marketplace"])


# --------------------------------------------------------------------------- #
# external entry preservation                                                  #
# --------------------------------------------------------------------------- #


def test_external_entry_survives_build_context():
    mk = _marketplace(
        {
            "name": "zzz-external-demo",
            "source": "srobroek/project-setup",
            "ref": "v1.2.3",
            "category": "project-lifecycle",
            "tags": ["skill", "lifecycle"],
        }
    )
    ctx = bi.build_context(mk)
    entries = ctx["marketplace"]["entries"]
    match = [e for e in entries if e["name"] == "zzz-external-demo"]
    assert match, "external entry with no local dir was dropped"
    e = match[0]
    assert e["source"] == "srobroek/project-setup"
    assert e["ref"] == "v1.2.3"
    assert e["category"] == "project-lifecycle"
    assert e["tags"] == ["skill", "lifecycle"]


def test_external_entry_key_order_is_canonical():
    mk = _marketplace(
        {
            "name": "zzz-external-demo",
            "tags": ["a"],
            "category": "x",
            "subdir": "sub",
            "ref": "v1.2.3",
            "source": "srobroek/project-setup",
        }
    )
    ctx = bi.build_context(mk)
    e = [x for x in ctx["marketplace"]["entries"] if x["name"] == "zzz-external-demo"][0]
    # name, source, ref, subdir, ..., category, tags -- regardless of author order.
    assert list(e.keys()) == ["name", "source", "ref", "subdir", "category", "tags"]


def test_external_entry_not_reported_as_dropped():
    mk = _marketplace(
        {"name": "zzz-external-demo", "source": "srobroek/project-setup", "ref": "main"}
    )
    ctx = bi.build_context(mk)
    drops = [
        w for w in ctx["marketplace"]["warnings"] if "zzz-external-demo" in w and "dropped" in w
    ]
    assert not drops, f"external entry wrongly reported as dropped: {drops}"


def test_dict_form_external_source_preserved():
    mk = _marketplace(
        {
            "name": "zzz-dict-demo",
            "source": {"type": "github", "repo": "srobroek/project-setup", "ref": "main"},
        }
    )
    ctx = bi.build_context(mk)
    e = [x for x in ctx["marketplace"]["entries"] if x["name"] == "zzz-dict-demo"]
    assert e, "dict-form external entry was dropped"
    assert e[0]["source"] == {"type": "github", "repo": "srobroek/project-setup", "ref": "main"}


# --------------------------------------------------------------------------- #
# collision: local dir wins                                                    #
# --------------------------------------------------------------------------- #


def test_name_collision_local_wins_no_duplicate():
    # 'agent-builder' is a real local package; an external entry with the same name
    # must be ignored (local wins) and NOT produce a second entry.
    mk = _marketplace({"name": "agent-builder", "source": "srobroek/somewhere-else", "ref": "main"})
    ctx = bi.build_context(mk)
    matches = [e for e in ctx["marketplace"]["entries"] if e["name"] == "agent-builder"]
    assert len(matches) == 1, f"expected exactly one agent-builder entry, got {matches}"
    assert matches[0]["source"] == "./packages/agent-builder"
    warns = [w for w in ctx["marketplace"]["warnings"] if "agent-builder" in w and "ignored" in w]
    assert warns, "expected a collision warning when local dir shadows external source"


# --------------------------------------------------------------------------- #
# no regression for local-only blocks                                          #
# --------------------------------------------------------------------------- #


def test_repo_block_local_entries_have_canonical_shape():
    # Local (./packages/<dir>) entries must keep the name/source/category/tags
    # shape with no git-source fields -- the common case must not regress. The
    # assertion is per-kind rather than "everything is local" so it still holds
    # whether or not the catalog currently carries an external git entry; it
    # carries none today.
    ctx = bi.build_context()  # reads the repo's apm.yml
    entries = ctx["marketplace"]["entries"]
    assert entries, "no marketplace entries produced"
    local = [e for e in entries if bi._is_local_source(e.get("source"))]
    external = [e for e in entries if not bi._is_local_source(e.get("source"))]
    assert local, "expected local ./packages entries"
    for e in local:
        assert e["source"].startswith("./packages/"), e
        assert set(e.keys()) <= {"name", "source", "category", "tags"}, e
    # External entries are allowed to carry source/ref/subdir; just ensure they
    # are NOT local-path-shaped (the whole point of the feature).
    for e in external:
        assert not str(e.get("source", "")).startswith("./"), e


# --------------------------------------------------------------------------- #
# render round-trip                                                            #
# --------------------------------------------------------------------------- #


def test_external_entry_round_trips_through_render():
    import yaml

    mk = _marketplace(
        {
            "name": "zzz-external-demo",
            "source": "srobroek/project-setup",
            "ref": "v1.2.3",
            "category": "project-lifecycle",
            "tags": ["skill", "lifecycle"],
        }
    )
    entries = bi.build_context(mk)["marketplace"]["entries"]
    block = rd._render_marketplace_block(mk, entries)
    parsed = yaml.safe_load(block)["marketplace"]
    e = [x for x in parsed["packages"] if x["name"] == "zzz-external-demo"][0]
    assert e["source"] == "srobroek/project-setup"
    assert e["ref"] == "v1.2.3"
