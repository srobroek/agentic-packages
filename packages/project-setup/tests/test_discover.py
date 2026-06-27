"""Tests for sources/discover.py — discover_modules, build_discovery_roots.

Tests cover:
  * Precedence ordering: env > project > home > fetched > bundled.
  * Same-root-kind duplicate id → hard ID_COLLISION with both paths in
    module_ids (NEVER a shadow).
  * Cross-level duplicate → shadow (higher wins, logged, no error).
  * default_enabled=true on a non-bundled module → FORBIDDEN_FIELD hard error.
  * Bundled-only run discovers base modules normally.
  * Malformed manifests are collected as parse_errors, not crashes.

Run via:
    uv run --with pytest pytest -q packages/project-setup/tests/test_discover.py
"""

from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

_RUNNER = Path(__file__).resolve().parents[1] / "skills" / "project-setup" / "runner"
_SOURCES = _RUNNER / "sources"


def _load_runner(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_source(name: str):
    qualified = f"sources.{name}"
    if qualified in sys.modules:
        return sys.modules[qualified]
    spec = importlib.util.spec_from_file_location(qualified, _SOURCES / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = mod
    spec.loader.exec_module(mod)
    return mod


# Pre-load runner deps
_load_runner("contracts")
_load_runner("paths")

discover_mod = _load_source("discover")

discover_modules = discover_mod.discover_modules
build_discovery_roots = discover_mod.build_discovery_roots
RootKind = discover_mod.RootKind
_RootEntry = discover_mod._RootEntry

contracts_mod = sys.modules["contracts"]
ErrorCode = contracts_mod.ErrorCode


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_MINIMAL_TOML = textwrap.dedent("""\
    [meta]
    repository = "github.com/test/test"
    author = "Test"

    [module]
    id          = "{id}"
    name        = "{name}"
    version     = "0.1.0"
    description = "test module"
    reconcile   = false
""")

_TOML_WITH_DEFAULT_ENABLED = textwrap.dedent("""\
    [meta]
    repository = "github.com/test/test"
    author = "Test"

    [module]
    id              = "{id}"
    name            = "{name}"
    version         = "0.1.0"
    description     = "test module"
    reconcile       = false
    default_enabled = true
""")


def _make_module(root: Path, module_id: str, default_enabled: bool = False) -> Path:
    """Create a minimal module directory under *root*."""
    mod_dir = root / module_id
    mod_dir.mkdir(parents=True, exist_ok=True)
    template = _TOML_WITH_DEFAULT_ENABLED if default_enabled else _MINIMAL_TOML
    toml = template.format(id=module_id, name=module_id.replace("-", " ").title())
    (mod_dir / "module.toml").write_text(toml)
    return mod_dir


def _root_entry(path: Path, kind: RootKind) -> _RootEntry:
    return _RootEntry(path=path, kind=kind)


# ---------------------------------------------------------------------------
# Basic discovery
# ---------------------------------------------------------------------------

class TestBasicDiscovery:
    def test_single_root_discovers_modules(self, tmp_path):
        root = tmp_path / "bundled"
        root.mkdir()
        _make_module(root, "git-init")
        _make_module(root, "core-identity")

        entries = [_root_entry(root, RootKind.BUNDLED)]
        modules, report = discover_modules(entries, bundled_root=root)

        assert "git-init" in modules
        assert "core-identity" in modules
        assert len(report.hard_errors) == 0
        assert len(report.shadows) == 0

    def test_empty_root_discovers_nothing(self, tmp_path):
        entries = [_root_entry(tmp_path / "empty", RootKind.BUNDLED)]
        modules, report = discover_modules(entries)
        assert modules == {}

    def test_non_existent_root_is_silently_skipped(self, tmp_path):
        entries = [_root_entry(tmp_path / "does_not_exist", RootKind.BUNDLED)]
        modules, report = discover_modules(entries)
        assert modules == {}
        assert len(report.hard_errors) == 0

    def test_subdirs_without_module_toml_are_skipped(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        (root / "not-a-module").mkdir()  # no module.toml
        _make_module(root, "real-module")

        entries = [_root_entry(root, RootKind.BUNDLED)]
        modules, report = discover_modules(entries)

        assert "real-module" in modules
        assert "not-a-module" not in modules

    def test_discovered_module_has_correct_fields(self, tmp_path):
        root = tmp_path / "bundled"
        root.mkdir()
        _make_module(root, "my-module")

        entries = [_root_entry(root, RootKind.BUNDLED)]
        modules, report = discover_modules(entries, bundled_root=root)

        m = modules["my-module"]
        assert m.id == "my-module"
        assert m.root_kind == RootKind.BUNDLED
        assert m.manifest_path.name == "module.toml"
        assert m.root_path == root / "my-module"


# ---------------------------------------------------------------------------
# Precedence ordering
# ---------------------------------------------------------------------------

class TestPrecedenceOrdering:
    def test_env_beats_bundled(self, tmp_path):
        env_root = tmp_path / "env"
        env_root.mkdir()
        bundled_root = tmp_path / "bundled"
        bundled_root.mkdir()

        _make_module(env_root, "git-init")
        _make_module(bundled_root, "git-init")

        entries = [
            _root_entry(env_root, RootKind.ENV),
            _root_entry(bundled_root, RootKind.BUNDLED),
        ]
        modules, report = discover_modules(entries, bundled_root=bundled_root)

        assert modules["git-init"].root_kind == RootKind.ENV
        assert len(report.shadows) == 1
        assert report.shadows[0]["id"] == "git-init"
        assert report.shadows[0]["winner_kind"] == "env"
        assert report.shadows[0]["shadow_kind"] == "bundled"

    def test_project_beats_home_beats_fetched_beats_bundled(self, tmp_path):
        roots = {}
        for kind_name in ("project", "home", "fetched", "bundled"):
            d = tmp_path / kind_name
            d.mkdir()
            _make_module(d, "shared-module")
            roots[kind_name] = d

        entries = [
            _root_entry(roots["project"], RootKind.PROJECT),
            _root_entry(roots["home"], RootKind.HOME),
            _root_entry(roots["fetched"], RootKind.FETCHED),
            _root_entry(roots["bundled"], RootKind.BUNDLED),
        ]
        modules, report = discover_modules(entries, bundled_root=roots["bundled"])

        assert modules["shared-module"].root_kind == RootKind.PROJECT
        # Three shadows (home, fetched, bundled lose)
        shadow_ids = [s["id"] for s in report.shadows]
        assert shadow_ids.count("shared-module") == 3

    def test_shadow_logged_not_an_error(self, tmp_path):
        high = tmp_path / "high"
        high.mkdir()
        low = tmp_path / "low"
        low.mkdir()
        _make_module(high, "mod-x")
        _make_module(low, "mod-x")

        entries = [
            _root_entry(high, RootKind.ENV),
            _root_entry(low, RootKind.BUNDLED),
        ]
        modules, report = discover_modules(entries)

        # Shadow = NO hard error
        assert len(report.hard_errors) == 0
        assert len(report.shadows) == 1
        assert modules["mod-x"].root_kind == RootKind.ENV

    def test_unique_ids_across_roots_no_shadow(self, tmp_path):
        r1 = tmp_path / "r1"
        r1.mkdir()
        r2 = tmp_path / "r2"
        r2.mkdir()
        _make_module(r1, "mod-a")
        _make_module(r2, "mod-b")

        entries = [_root_entry(r1, RootKind.HOME), _root_entry(r2, RootKind.BUNDLED)]
        modules, report = discover_modules(entries)

        assert "mod-a" in modules
        assert "mod-b" in modules
        assert len(report.shadows) == 0
        assert len(report.hard_errors) == 0


# ---------------------------------------------------------------------------
# Same-root-kind collision → hard ID_COLLISION
# ---------------------------------------------------------------------------

class TestSameRootKindCollision:
    def test_collision_in_env_root_kind_is_hard_error(self, tmp_path):
        """Two FETCHED roots (multiple fetched sources) with the same id."""
        fetched_a = tmp_path / "fetched_a"
        fetched_a.mkdir()
        fetched_b = tmp_path / "fetched_b"
        fetched_b.mkdir()
        _make_module(fetched_a, "duplicate-id")
        _make_module(fetched_b, "duplicate-id")

        entries = [
            _root_entry(fetched_a, RootKind.FETCHED),
            _root_entry(fetched_b, RootKind.FETCHED),
        ]
        modules, report = discover_modules(entries)

        # Must be a HARD error, not a shadow
        assert len(report.hard_errors) == 1
        err = report.hard_errors[0]
        assert err.error_code == ErrorCode.ID_COLLISION
        # Both manifest paths named in module_ids
        assert len(err.module_ids) == 2
        paths = [Path(p) for p in err.module_ids]
        assert any("fetched_a" in str(p) for p in paths)
        assert any("fetched_b" in str(p) for p in paths)

    def test_collision_excludes_id_from_final_map(self, tmp_path):
        root_a = tmp_path / "a"
        root_a.mkdir()
        root_b = tmp_path / "b"
        root_b.mkdir()
        _make_module(root_a, "dupe")
        _make_module(root_b, "dupe")
        _make_module(root_a, "unique")

        entries = [
            _root_entry(root_a, RootKind.FETCHED),
            _root_entry(root_b, RootKind.FETCHED),
        ]
        modules, report = discover_modules(entries)

        assert "dupe" not in modules     # excluded due to collision
        assert "unique" in modules       # unaffected unique id survives

    def test_collision_hard_error_names_both_paths(self, tmp_path):
        root_a = tmp_path / "src_a"
        root_a.mkdir()
        root_b = tmp_path / "src_b"
        root_b.mkdir()
        _make_module(root_a, "common-tool")
        _make_module(root_b, "common-tool")

        entries = [
            _root_entry(root_a, RootKind.FETCHED),
            _root_entry(root_b, RootKind.FETCHED),
        ]
        _, report = discover_modules(entries)

        err = report.hard_errors[0]
        assert len(err.module_ids) == 2

    def test_same_id_in_different_root_kinds_is_shadow_not_collision(self, tmp_path):
        """env + bundled with same id → shadow, NOT ID_COLLISION."""
        env_root = tmp_path / "env"
        env_root.mkdir()
        bundled_root = tmp_path / "bundled"
        bundled_root.mkdir()
        _make_module(env_root, "shared-id")
        _make_module(bundled_root, "shared-id")

        entries = [
            _root_entry(env_root, RootKind.ENV),
            _root_entry(bundled_root, RootKind.BUNDLED),
        ]
        modules, report = discover_modules(entries, bundled_root=bundled_root)

        assert len(report.hard_errors) == 0  # no hard error
        assert len(report.shadows) == 1       # logged shadow
        assert "shared-id" in modules
        assert modules["shared-id"].root_kind == RootKind.ENV  # env wins

    def test_multiple_collisions_all_reported(self, tmp_path):
        r1 = tmp_path / "r1"
        r1.mkdir()
        r2 = tmp_path / "r2"
        r2.mkdir()
        for mid in ("alpha", "beta", "gamma"):
            _make_module(r1, mid)
            _make_module(r2, mid)

        entries = [
            _root_entry(r1, RootKind.FETCHED),
            _root_entry(r2, RootKind.FETCHED),
        ]
        _, report = discover_modules(entries)

        collision_ids = {
            err.module_ids[0].split("/")[-2]  # parent dir name = module id
            for err in report.hard_errors
            if err.error_code == ErrorCode.ID_COLLISION
        }
        assert len(report.hard_errors) == 3


# ---------------------------------------------------------------------------
# default_enabled enforcement (FR-035)
# ---------------------------------------------------------------------------

class TestDefaultEnabledEnforcement:
    def test_bundled_module_may_set_default_enabled_true(self, tmp_path):
        bundled = tmp_path / "bundled"
        bundled.mkdir()
        _make_module(bundled, "core-id", default_enabled=True)

        entries = [_root_entry(bundled, RootKind.BUNDLED)]
        modules, report = discover_modules(entries, bundled_root=bundled)

        # No hard error for bundled modules
        de_errors = [e for e in report.hard_errors
                     if e.error_code == ErrorCode.FORBIDDEN_FIELD]
        assert len(de_errors) == 0
        assert "core-id" in modules

    def test_non_bundled_module_default_enabled_true_is_rejected(self, tmp_path):
        home_root = tmp_path / "home"
        home_root.mkdir()
        _make_module(home_root, "bad-module", default_enabled=True)

        entries = [_root_entry(home_root, RootKind.HOME)]
        modules, report = discover_modules(entries)

        de_errors = [e for e in report.hard_errors
                     if e.error_code == ErrorCode.FORBIDDEN_FIELD]
        assert len(de_errors) == 1
        err = de_errors[0]
        assert err.module_id == "bad-module"
        assert "default_enabled" in err.received.lower() or "default_enabled" in err.how_to_fix

    def test_fetched_module_default_enabled_true_is_rejected(self, tmp_path):
        fetched = tmp_path / "fetched"
        fetched.mkdir()
        _make_module(fetched, "third-party", default_enabled=True)

        entries = [_root_entry(fetched, RootKind.FETCHED)]
        modules, report = discover_modules(entries)

        de_errors = [e for e in report.hard_errors
                     if e.error_code == ErrorCode.FORBIDDEN_FIELD]
        assert len(de_errors) == 1

    def test_env_module_default_enabled_true_is_rejected(self, tmp_path):
        env_root = tmp_path / "env"
        env_root.mkdir()
        _make_module(env_root, "env-module", default_enabled=True)

        entries = [_root_entry(env_root, RootKind.ENV)]
        modules, report = discover_modules(entries)

        de_errors = [e for e in report.hard_errors
                     if e.error_code == ErrorCode.FORBIDDEN_FIELD]
        assert len(de_errors) == 1

    def test_non_bundled_default_enabled_false_is_allowed(self, tmp_path):
        """default_enabled=false (or absent) is fine anywhere."""
        home = tmp_path / "home"
        home.mkdir()
        _make_module(home, "ok-module", default_enabled=False)

        entries = [_root_entry(home, RootKind.HOME)]
        modules, report = discover_modules(entries)

        de_errors = [e for e in report.hard_errors
                     if e.error_code == ErrorCode.FORBIDDEN_FIELD]
        assert len(de_errors) == 0
        assert "ok-module" in modules


# ---------------------------------------------------------------------------
# Malformed manifest handling
# ---------------------------------------------------------------------------

class TestMalformedManifests:
    def test_invalid_toml_is_collected_not_crash(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        bad_dir = root / "bad-module"
        bad_dir.mkdir()
        (bad_dir / "module.toml").write_text("this is not valid toml ][")
        _make_module(root, "good-module")

        entries = [_root_entry(root, RootKind.BUNDLED)]
        modules, report = discover_modules(entries)

        assert "good-module" in modules
        assert "bad-module" not in modules
        assert len(report.parse_errors) >= 1

    def test_missing_id_field_is_collected_not_crash(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        bad_dir = root / "no-id"
        bad_dir.mkdir()
        (bad_dir / "module.toml").write_text(
            "[meta]\nrepository = 'x'\nauthor = 'y'\n\n[module]\nname = 'X'\n"
        )

        entries = [_root_entry(root, RootKind.BUNDLED)]
        modules, report = discover_modules(entries)

        assert "no-id" not in modules
        assert len(report.parse_errors) >= 1


# ---------------------------------------------------------------------------
# build_discovery_roots
# ---------------------------------------------------------------------------

class TestBuildDiscoveryRoots:
    def test_includes_bundled_entry(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PROJECT_SETUP_MODULES_DIR", raising=False)
        roots = build_discovery_roots(fetched_roots=[], project_dir=None)
        kinds = [r.kind for r in roots]
        assert RootKind.BUNDLED in kinds

    def test_bundled_is_last(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PROJECT_SETUP_MODULES_DIR", raising=False)
        roots = build_discovery_roots(fetched_roots=[], project_dir=None)
        assert roots[-1].kind == RootKind.BUNDLED

    def test_env_dir_is_first_when_set(self, tmp_path, monkeypatch):
        env_dir = tmp_path / "env_modules"
        env_dir.mkdir()
        monkeypatch.setenv("PROJECT_SETUP_MODULES_DIR", str(env_dir))
        roots = build_discovery_roots(fetched_roots=[], project_dir=None)
        assert roots[0].kind == RootKind.ENV
        assert roots[0].path == env_dir

    def test_env_dir_absent_when_not_set(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PROJECT_SETUP_MODULES_DIR", raising=False)
        roots = build_discovery_roots(fetched_roots=[], project_dir=None)
        kinds = [r.kind for r in roots]
        assert RootKind.ENV not in kinds

    def test_fetched_roots_in_correct_position(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PROJECT_SETUP_MODULES_DIR", raising=False)
        f1 = tmp_path / "f1"
        f2 = tmp_path / "f2"
        roots = build_discovery_roots(fetched_roots=[f1, f2], project_dir=None)
        kinds = [r.kind for r in roots]
        # FETCHED should appear before BUNDLED
        fetched_indices = [i for i, k in enumerate(kinds) if k == RootKind.FETCHED]
        bundled_index = kinds.index(RootKind.BUNDLED)
        assert all(i < bundled_index for i in fetched_indices)
        assert len(fetched_indices) == 2

    def test_project_dir_appears_before_home(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PROJECT_SETUP_MODULES_DIR", raising=False)
        roots = build_discovery_roots(fetched_roots=[], project_dir=tmp_path)
        kinds = [r.kind for r in roots]
        assert kinds.index(RootKind.PROJECT) < kinds.index(RootKind.HOME)

    def test_full_order(self, tmp_path, monkeypatch):
        env_dir = tmp_path / "env_modules"
        env_dir.mkdir()
        monkeypatch.setenv("PROJECT_SETUP_MODULES_DIR", str(env_dir))

        f1 = tmp_path / "f1"
        roots = build_discovery_roots(fetched_roots=[f1], project_dir=tmp_path)
        kinds = [r.kind for r in roots]

        # Expected: ENV > PROJECT > HOME > FETCHED > BUNDLED
        assert kinds[0] == RootKind.ENV
        assert RootKind.PROJECT in kinds
        assert RootKind.HOME in kinds
        assert RootKind.FETCHED in kinds
        assert kinds[-1] == RootKind.BUNDLED


# ---------------------------------------------------------------------------
# Bundled-only run
# ---------------------------------------------------------------------------

class TestBundledOnlyRun:
    def test_bundled_modules_discoverable_when_present(self, tmp_path):
        bundled = tmp_path / "bundled"
        bundled.mkdir()
        for mid in ("core-identity", "git-init", "gitignore-generate"):
            _make_module(bundled, mid)

        entries = [_root_entry(bundled, RootKind.BUNDLED)]
        modules, report = discover_modules(entries, bundled_root=bundled)

        assert "core-identity" in modules
        assert "git-init" in modules
        assert "gitignore-generate" in modules
        assert len(report.hard_errors) == 0
        assert len(report.shadows) == 0
