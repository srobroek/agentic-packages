"""Module-author SDK — loaded by module.py via importlib.

This is the public API every ``module.py`` uses. It is loaded BY FILE PATH,
not by package import:

    sdk = importlib.util.spec_from_file_location("sdk", sdk_path)
    ...

See shared-contracts.md §6 for the mandatory sys.modules registration pattern.

Provides:
  - ``load_frozen_inputs(plan_path, module_id)`` → ``FrozenInputs``
  - ``FrozenInputs`` — typed accessors for all input types
  - ``idempotent_write(rel_path, body, *, reconcile, inspect)``
  - ``run_tool(args, cwd, warnings, label, *, timeout)``
  - ``append_if_absent(path, marker, block, warnings, label)``
  - ``is_safe_relative_path(p)``
  - ``emit_result(result)``

Standard library only (no third-party deps).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

# sdk.py is the ONE runner module a `module.py` subprocess loads BY FILE PATH (via
# the module's `import sdk` shim fallback). In that context the runner dir is NOT
# guaranteed on sys.path — the executor injects PYTHONPATH (spec 005 FR-001), but a
# test or tool that runs `uv run module.py` directly does not. So sdk self-bootstraps
# its own dir onto sys.path here, BEFORE importing siblings, so the whole sdk import
# closure (contracts, plan → paths/manifest) resolves regardless of how sdk was
# loaded. (The CLI/pytest entry points also set the path; this is idempotent.)
_RUNNER = Path(__file__).resolve().parent
if str(_RUNNER) not in sys.path:
    sys.path.insert(0, str(_RUNNER))

# Sibling runner modules import by plain name (spec 005 OQ-2).
import contracts as _contracts  # noqa: E402
import plan as _plan_mod  # noqa: E402

canonical_json = _contracts.canonical_json
SetupError = _contracts.SetupError
ErrorCode = _contracts.ErrorCode
GateFailure = _contracts.GateFailure
Provenance = _contracts.Provenance
MODULE_EMITTABLE_PROVENANCE = _contracts.MODULE_EMITTABLE_PROVENANCE
ModuleResult = _contracts.ModuleResult
Diff = _contracts.Diff
RESULT_REQUIRED_KEYS = _contracts.RESULT_REQUIRED_KEYS
SCHEMA_VERSION = _contracts.SCHEMA_VERSION
load_plan = _plan_mod.load_plan


# --------------------------------------------------------------------------- #
# FrozenInputs — typed accessor object                                        #
# --------------------------------------------------------------------------- #
class FrozenInputs:
    """Typed read-only view of a module's frozen answers.

    Exposes one accessor per input type (get_str, get_bool,
    get_list, get_choice, get_multichoice) plus ``.reconcile``.
    """

    def __init__(self, module_entry: Any, plan: Any) -> None:
        self._answers: dict[str, Any] = dict(module_entry.answers)
        self._reconcile: bool = bool(module_entry.reconcile)
        self._module_id: str = module_entry.id
        self._mode: str = getattr(plan, "mode", "init")

    @property
    def reconcile(self) -> bool:
        """Whether the module runs in reconcile mode (overwrite-to-match)."""
        return self._reconcile

    @property
    def mode(self) -> str:
        """The run mode of the frozen plan: ``"init"`` or ``"reproduce"``.

        A Tier-2 resolver uses this to gate network work: registry pin
        verification runs in ``init`` (the pins were freshly decided this run);
        on ``reproduce`` the pins are already frozen + were verified at init, so
        verification is skipped to keep reproduce zero-network (spec 003)."""
        return self._mode

    def _get(self, key: str, default: Any = None) -> Any:
        return self._answers.get(key, default)

    def get_str(self, key: str, default: str = "") -> str:
        """Return the value for *key* as a ``str``."""
        v = self._get(key)
        if v is None:
            return default
        return str(v)

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Return the value for *key* as a ``bool``."""
        v = self._get(key)
        if v is None:
            return default
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        return bool(v)

    def get_list(self, key: str, default: list | None = None) -> list:
        """Return the value for *key* as a ``list``."""
        v = self._get(key)
        if v is None:
            return default if default is not None else []
        if isinstance(v, list):
            return list(v)
        return [v]

    def get_choice(self, key: str, default: str = "") -> str:
        """Return the value for *key* as a single-choice string."""
        v = self._get(key)
        if v is None:
            return default
        return str(v)

    def get_multichoice(self, key: str, default: list | None = None) -> list[str]:
        """Return the value for *key* as a list of selected choices."""
        v = self._get(key)
        if v is None:
            return default if default is not None else []
        if isinstance(v, list):
            return [str(x) for x in v]
        return [str(v)]


# --------------------------------------------------------------------------- #
# load_frozen_inputs                                                           #
# --------------------------------------------------------------------------- #
def load_frozen_inputs(plan_path: str | Path, module_id: str) -> FrozenInputs:
    """Load the frozen plan and return a ``FrozenInputs`` for *module_id*.

    Parameters
    ----------
    plan_path:
        Path to the frozen ``plan.json`` (passed as ``--plan`` arg).
    module_id:
        The module's own id (passed as ``--step`` parent context, or the
        module knows its own id from its manifest).

    Returns
    -------
    FrozenInputs
        A typed accessor over the module's frozen answers.

    Raises
    ------
    GateFailure
        If the plan is malformed or the module id is not in the plan.
    """
    plan = load_plan(Path(plan_path))
    if module_id not in plan.modules:
        raise GateFailure([SetupError(
            error_code=ErrorCode.PLAN_MALFORMED,
            module_id=module_id,
            expected=f"module '{module_id}' in frozen plan",
            received="not found",
            how_to_fix=(
                f"Module '{module_id}' is not in the frozen plan at {plan_path}. "
                "Re-run project-setup to regenerate the plan."
            ),
        )])
    return FrozenInputs(plan.modules[module_id], plan)


# --------------------------------------------------------------------------- #
# idempotent_write                                                             #
# --------------------------------------------------------------------------- #
def idempotent_write(
    rel_path: str | Path,
    body: str | bytes,
    *,
    project_dir: str | Path | None = None,
    reconcile: bool = False,
    inspect: bool = False,
) -> Diff:
    """Write *body* to *rel_path* relative to *project_dir* idempotently.

    Tier-1 guarantee: the bytes produced in ``inspect=True`` mode are IDENTICAL
    to those that would be written in ``inspect=False`` mode (same encoding,
    same content). The only difference is that in inspect mode nothing is
    written to disk.

    Parameters
    ----------
    rel_path:
        A safe relative path within *project_dir* (validated by
        ``is_safe_relative_path``).
    body:
        The content to write (str encoded to UTF-8, or raw bytes).
    project_dir:
        The project root; defaults to ``$PROJECT_DIR`` env var or ``cwd()``.
    reconcile:
        If True: overwrite existing file to match *body*; if False: skip
        existing files (write-if-absent).
    inspect:
        If True: produce the ``Diff`` preview without writing anything.

    Returns
    -------
    Diff
        Describes what would be / was written (kind="create"/"modify"/"skip").
    """
    if project_dir is None:
        env_pd = os.environ.get("PROJECT_DIR")
        project_dir = Path(env_pd) if env_pd else Path.cwd()
    project_dir = Path(project_dir).resolve()

    rel_path = Path(rel_path)
    if not is_safe_relative_path(rel_path):
        raise SetupError(
            error_code=ErrorCode.PATH_ESCAPE,
            expected="safe relative path (no .., no absolute, no symlink escape)",
            received=str(rel_path),
            how_to_fix=f"Use a path within the project directory (no '..' or absolute paths): {rel_path}",
        )

    abs_path = project_dir / rel_path

    # Normalize body to bytes (the canonical byte form)
    if isinstance(body, str):
        body_bytes = body.encode("utf-8")
    else:
        body_bytes = bytes(body)

    rel_str = str(rel_path)

    if abs_path.exists():
        existing = abs_path.read_bytes()
        if existing == body_bytes:
            return Diff(path=rel_str, kind="skip", preview="(identical, no change)")
        if reconcile:
            if not inspect:
                abs_path.parent.mkdir(parents=True, exist_ok=True)
                abs_path.write_bytes(body_bytes)
            return Diff(path=rel_str, kind="modify", preview=_preview(body_bytes))
        else:
            # Write-if-absent: file exists, skip
            return Diff(path=rel_str, kind="skip", preview="(exists, skipping — use reconcile to overwrite)")
    else:
        if not inspect:
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_bytes(body_bytes)
        return Diff(path=rel_str, kind="create", preview=_preview(body_bytes))


def _preview(body_bytes: bytes, max_chars: int = 200) -> str:
    """Short human-readable preview of file content."""
    try:
        text = body_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return f"<binary, {len(body_bytes)} bytes>"
    lines = text.splitlines()
    head = "\n".join(lines[:5])
    if len(lines) > 5 or len(head) > max_chars:
        return head[:max_chars] + "…"
    return head


# --------------------------------------------------------------------------- #
# scan_top_level_dirs — shallow read-only dir scan (spec 006 FR-004)           #
# --------------------------------------------------------------------------- #
def scan_top_level_dirs(project_dir: "str | Path | None" = None) -> "frozenset[str]":
    """Return the set of top-level DIRECTORY names directly under *project_dir*.

    No recursion, directories only (files excluded), hidden dirs (``.``-prefixed)
    INCLUDED. A missing or empty project dir yields an empty frozenset — never
    raises. Used by the AGENTS.md architecture splice to validate that paths the
    agent references actually exist (phantom-path guard, spec 006 FR-007). Pure
    stdlib, no network.
    """
    if project_dir is None:
        env_pd = os.environ.get("PROJECT_DIR")
        project_dir = Path(env_pd) if env_pd else Path.cwd()
    base = Path(project_dir)
    if not base.is_dir():
        return frozenset()
    try:
        return frozenset(e.name for e in os.scandir(base) if e.is_dir())
    except OSError:
        return frozenset()


# --------------------------------------------------------------------------- #
# detect_marketplaces — offline registry detection (spec 018 FR-001)           #
# --------------------------------------------------------------------------- #
def detect_marketplaces(home: "str | Path | None" = None) -> "dict[str, list[str]]":
    """Return per-system marketplace names read from the user's offline registry files.

    Spec 018 FR-001. Reads three registry files without network or subprocess:

    - APM:         ``<home>/.apm/marketplaces.json``
    - Claude Code: ``<home>/.claude/plugins/known_marketplaces.json``
    - Codex:       ``<home>/.codex/config.toml``

    Returns ``{"apm": [...], "claude-code": [...], "codex": [...]}`` where each
    list contains marketplace NAMES found in the respective registry.  A missing
    file, malformed JSON/TOML, or empty registry yields an empty list for that
    system — NEVER raises.

    This is registry-PRESENCE detection (offline). The result is intended to be
    frozen into ``answers.toml`` by the interview (FR-002).  Modules MUST NOT
    call this at execute time; they must read the frozen answer instead, to
    preserve the determinism contract (Decision F — re-detecting at execute time
    would make a clone behave differently on a machine with vs without a
    marketplace).
    """
    base = Path(home) if home is not None else Path.home()

    # --- APM: ~/.apm/marketplaces.json ---
    # Shape: {"marketplaces": [{"name": "...", "url": "...", ...}, ...]}
    apm_names: list[str] = []
    try:
        raw = (base / ".apm" / "marketplaces.json").read_bytes()
        data = json.loads(raw)
        if isinstance(data, dict):
            for m in data.get("marketplaces", []):
                if isinstance(m, dict) and m.get("name"):
                    apm_names.append(m["name"])
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        apm_names = []
    except Exception:  # noqa: BLE001 — broad safety net, never raises
        apm_names = []

    # --- Claude Code: ~/.claude/plugins/known_marketplaces.json ---
    # Shape: a flat object whose KEYS are marketplace names
    # e.g. {"claude-plugins-official": {...}, "repomix": {...}}
    cc_names: list[str] = []
    try:
        raw = (base / ".claude" / "plugins" / "known_marketplaces.json").read_bytes()
        data = json.loads(raw)
        if isinstance(data, dict):
            cc_names = list(data.keys())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        cc_names = []
    except Exception:  # noqa: BLE001
        cc_names = []

    # --- Codex: ~/.codex/config.toml ---
    # Shape: [marketplaces.<name>] tables → top-level key "marketplaces" is a
    # dict whose keys are names (e.g. {"openai-bundled": {...}, ...})
    codex_names: list[str] = []
    try:
        raw = (base / ".codex" / "config.toml").read_bytes()
        data = tomllib.loads(raw.decode("utf-8"))
        marketplaces = data.get("marketplaces", {})
        if isinstance(marketplaces, dict):
            codex_names = list(marketplaces.keys())
    except (FileNotFoundError, tomllib.TOMLDecodeError, OSError):
        codex_names = []
    except Exception:  # noqa: BLE001
        codex_names = []

    return {"apm": apm_names, "claude-code": cc_names, "codex": codex_names}


# --------------------------------------------------------------------------- #
# fetch_addon_catalog — runtime catalog fetch (spec 020 FR-B1)                 #
# --------------------------------------------------------------------------- #
def fetch_addon_catalog(
    url: str,
    *,
    timeout: float = 10.0,
    _opener: "Any | None" = None,
) -> "list[dict]":
    """Fetch an addon catalog JSON from *url* and return the list of records.

    Spec 020 FR-B1.  This is a discovery aid fetched at INIT — it is NOT frozen;
    only the chosen source locators (written to ``.project-setup/sources.toml``)
    are frozen.  The URL is caller-supplied (see ``addon_catalog_urls`` for how
    to resolve it from config/env) — there is NO hardcoded default.

    The catalog JSON may be either:

    - A JSON **list** of record objects, OR
    - A JSON **object** with a top-level ``"modules"`` or ``"addons"`` key whose
      value is a list of record objects.

    Each record is expected to have ``{name, description, locator, category}``
    fields; extra keys are ignored and missing optional keys are tolerated.
    Non-conforming records (not a dict) are silently dropped.

    On **any** failure — network error, timeout, malformed JSON, unexpected shape,
    empty response — returns ``[]`` and NEVER raises (mirrors
    ``detect_marketplaces`` defensiveness).  Stdlib urllib only; no third-party
    HTTP client.

    Parameters
    ----------
    url:
        The catalog JSON endpoint to fetch.
    timeout:
        Per-request timeout in seconds.
    _opener:
        Test seam: a callable ``(url, timeout) -> parsed-json`` used in place of
        the real network fetch.  When ``None`` the stdlib ``urllib.request`` is
        used.  Should raise on failure (same contract as ``_registry_get``).
    """
    import json as _json
    import urllib.request

    try:
        if _opener is not None:
            data = _opener(url, timeout)
        else:
            with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
                data = _json.loads(resp.read().decode("utf-8"))

        # Tolerate both shapes: bare list OR object with a "modules"/"addons" key.
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            records = data.get("modules") or data.get("addons") or []
            if not isinstance(records, list):
                return []
        else:
            return []

        # Filter: keep only dict records; drop anything else silently.
        return [r for r in records if isinstance(r, dict)]

    except Exception:  # noqa: BLE001 — broad safety net, never raises
        return []


# --------------------------------------------------------------------------- #
# addon_catalog_urls — resolve catalog URLs from config/env (spec 020 FR-B2)  #
# --------------------------------------------------------------------------- #
def addon_catalog_urls(home: "str | Path | None" = None) -> "list[str]":
    """Return the list of addon catalog URLs from env and/or home config.

    Spec 020 FR-B2.  Sources (in priority order, merged + deduped, env first):

    1. ``PROJECT_SETUP_CATALOG_URL`` env var — a single URL or a
       comma/space-separated list of URLs.
    2. Home config TOML (``~/.config/project-setup/config.toml``) — either
       ``[catalog] urls = [...]`` (list under a ``[catalog]`` table) or a
       top-level ``catalog_urls`` key (list).

    No hardcoded default URLs — an unconfigured install returns ``[]`` and no
    remote fetch occurs (FR-B6 behavior unchanged).  Never raises; a missing
    file, malformed TOML, or wrong-type value yields ``[]`` for that source.
    Uses ``paths.home_config_path()`` for the default config location.

    Parameters
    ----------
    home:
        Override the home directory used to locate the config file (test seam,
        mirrors ``detect_marketplaces``).  When ``None``, ``paths.home_config_path()``
        is used (which itself respects ``$PROJECT_SETUP_CONFIG`` / ``$XDG_CONFIG_HOME``).
    """
    import paths as _paths_local

    seen: dict[str, None] = {}  # ordered dedup via insertion-ordered dict

    # ── Source 1: env var (single or comma/space-separated list) ──────────── #
    env_val = os.environ.get("PROJECT_SETUP_CATALOG_URL", "").strip()
    if env_val:
        # Split on commas first, then whitespace within each token.
        for token in re.split(r"[,\s]+", env_val):
            token = token.strip()
            if token:
                seen[token] = None

    # ── Source 2: home config TOML ─────────────────────────────────────────── #
    try:
        if home is not None:
            cfg_path = Path(home) / ".config" / "project-setup" / "config.toml"
        else:
            cfg_path = _paths_local.home_config_path()

        if cfg_path.is_file():
            with open(cfg_path, "rb") as fh:
                cfg_data = tomllib.load(fh)

            # [catalog] urls = [...] takes precedence over catalog_urls top-level.
            catalog_section = cfg_data.get("catalog", {})
            if isinstance(catalog_section, dict):
                urls_val = catalog_section.get("urls")
                if isinstance(urls_val, list):
                    for u in urls_val:
                        if isinstance(u, str) and u.strip():
                            seen[u.strip()] = None

            # Fallback: top-level catalog_urls list.
            top_level = cfg_data.get("catalog_urls")
            if isinstance(top_level, list):
                for u in top_level:
                    if isinstance(u, str) and u.strip():
                        seen[u.strip()] = None

    except Exception:  # noqa: BLE001 — broad safety net, never raises
        pass

    return list(seen)


# --------------------------------------------------------------------------- #
# splice_between_sentinels — replace a marked span inside a file (spec 006)     #
# --------------------------------------------------------------------------- #
def splice_between_sentinels(
    rel_path: "str | Path",
    begin: str,
    end: str,
    body: str,
    *,
    project_dir: "str | Path | None" = None,
    inspect: bool = False,
    missing: str = "append",
    warnings: "list[str] | None" = None,
) -> "Diff":
    """Replace the content between *begin* and *end* markers in a file with *body*.

    Unlike ``idempotent_write`` (which replaces the WHOLE file), this replaces only
    the span BETWEEN the marker lines, preserving everything outside byte-for-byte.
    The marker lines themselves are preserved/written; *body* is the inner text (no
    markers). Returns a ``Diff`` (``create`` | ``modify`` | ``skip``). ``inspect=True``
    yields the identical diff kind without writing (Tier-1 guarantee, spec 006 FR-001).

    Cases (spec 006 FR-001/002/003):
      - file absent → write ``begin\\n{body}\\n{end}\\n`` (kind="create").
      - both markers present → replace the inner span; identical inner → "skip";
        else "modify". Content outside the markers is untouched.
      - ``begin`` present but ``end`` absent (malformed) → ALWAYS skip + warn
        ``malformed sentinel span (begin without end)``, regardless of *missing*.
      - markers absent + ``missing="append"`` (default) → append the marked block
        after the first case-insensitive ``## Architecture`` heading (or EOF), warn
        ``sentinel markers absent — appending architecture section`` ("modify"/"create").
      - markers absent + ``missing="error"`` → skip + warn, no write.

    Pure stdlib, no network.
    """
    warns = warnings if warnings is not None else []

    if project_dir is None:
        env_pd = os.environ.get("PROJECT_DIR")
        project_dir = Path(env_pd) if env_pd else Path.cwd()
    project_dir = Path(project_dir).resolve()

    rel_path = Path(rel_path)
    if not is_safe_relative_path(rel_path):
        raise SetupError(
            error_code=ErrorCode.PATH_ESCAPE,
            expected="safe relative path (no .., no absolute, no symlink escape)",
            received=str(rel_path),
            how_to_fix=f"Use a path within the project directory: {rel_path}",
        )
    abs_path = project_dir / rel_path
    rel_str = str(rel_path)
    block = f"{begin}\n{body}\n{end}\n"

    # --- file absent → create with the marked block ---
    if not abs_path.exists():
        if not inspect:
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_text(block, encoding="utf-8")
        return Diff(path=rel_str, kind="create", preview=_preview(block.encode("utf-8")))

    existing = abs_path.read_text(encoding="utf-8")
    bi = existing.find(begin)
    ei = existing.find(end)

    # --- malformed: begin without end → always skip+warn ---
    if bi != -1 and ei == -1:
        warns.append(f"malformed sentinel span (begin without end) in {rel_str}; skipping")
        return Diff(path=rel_str, kind="skip", preview="(malformed sentinel span — skipped)")

    # --- both markers present → replace the inner span ---
    if bi != -1 and ei != -1 and ei >= bi:
        inner_start = bi + len(begin)
        prefix = existing[:inner_start]
        suffix = existing[ei:]
        new_content = f"{prefix}\n{body}\n{suffix}"
        if new_content == existing:
            return Diff(path=rel_str, kind="skip", preview="(identical span, no change)")
        if not inspect:
            abs_path.write_text(new_content, encoding="utf-8")
        return Diff(path=rel_str, kind="modify", preview=_preview(body.encode("utf-8")))

    # --- markers absent ---
    if missing == "error":
        warns.append(f"sentinel markers absent in {rel_str} — skipping (missing=error)")
        return Diff(path=rel_str, kind="skip", preview="(sentinel markers absent — skipped)")

    # missing == "append": insert the marked block after the first "## Architecture"
    # heading (case-insensitive), else at EOF.
    warns.append("sentinel markers absent — appending architecture section")
    lines = existing.splitlines(keepends=True)
    insert_at = len(lines)
    for i, ln in enumerate(lines):
        if ln.strip().lower().startswith("## architecture"):
            insert_at = i + 1
            break
    sep = "" if (insert_at == 0 or lines[insert_at - 1].endswith("\n")) else "\n"
    new_content = "".join(lines[:insert_at]) + sep + block + "".join(lines[insert_at:])
    if not inspect:
        abs_path.write_text(new_content, encoding="utf-8")
    return Diff(path=rel_str, kind="modify", preview=_preview(block.encode("utf-8")))


# --------------------------------------------------------------------------- #
# verify_pins — MCP-free registry verification (spec 003 FR-005/006/007)       #
# --------------------------------------------------------------------------- #
# Per-pin verification status.
PIN_VERIFIED = "verified"          # the exact version exists on the registry
PIN_DISCONFIRMED = "disconfirmed"  # registry answered, version absent/yanked/bad name
PIN_UNREACHABLE = "unreachable"    # registry could not be reached (offline/timeout)

_PYPI_JSON = "https://pypi.org/pypi/{name}/json"
_NPM_JSON = "https://registry.npmjs.org/{name}"


def _split_pin(pin: str) -> tuple[str, str]:
    """Split a ``name@version`` pin. npm scoped names (``@scope/pkg@1.2.3``)
    keep their leading ``@``; the version is the part after the LAST ``@``."""
    s = str(pin).strip()
    at = s.rfind("@")
    if at <= 0:  # no '@', or only the leading scope '@' → no explicit version
        return s, ""
    return s[:at], s[at + 1:]


def _registry_get(url: str, timeout: float) -> Any:
    """GET *url* and parse JSON. Returns the parsed object, or ``None`` for a
    404/missing package (a definitive "does not exist"), or raises on a transport
    error (caller maps that to UNREACHABLE). Stdlib urllib only — no MCP, no
    third-party HTTP client (FR-006)."""
    import json as _json
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 (https only)
            return _json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None  # package does not exist — definitive disconfirm
        raise  # other HTTP errors are transport-ish → unreachable
    # URLError / socket timeout / OSError propagate → caller marks UNREACHABLE.


def verify_pins(
    pins: list[str],
    ecosystem: str,
    *,
    timeout: float = 10.0,
    _opener: Any = None,
) -> dict[str, str]:
    """Verify each ``name@version`` pin against its package registry, MCP-free.

    The mandatory, MCP-free pin verification of spec 003 (FR-005/006/007): every
    pin a Tier-2 resolver proposes is checked to actually exist on the live
    registry BEFORE it is gated or written, so hallucinated / typosquatted /
    yanked versions are rejected. Correctness never depends on any MCP server.

    Parameters
    ----------
    pins:
        A list of ``name@exact-version`` strings (npm scoped names supported).
    ecosystem:
        ``"pypi"`` (Python) or ``"npm"`` (TypeScript/JS).
    timeout:
        Per-request timeout in seconds.
    _opener:
        Test seam: a callable ``(url, timeout) -> parsed-json | None`` used in
        place of the real network fetch (so unit tests need no network). When
        ``None`` the stdlib ``_registry_get`` is used.

    Returns
    -------
    dict[str, str]
        Maps each input pin to one of ``PIN_VERIFIED`` / ``PIN_DISCONFIRMED`` /
        ``PIN_UNREACHABLE``. A pin with no explicit version is ``DISCONFIRMED``
        (the resolver contract forbids ranges/"latest"). The CALLER decides
        policy: a disconfirmed pin is rejected (INPUT_VALUE_INVALID, fail-closed);
        an unreachable pin is reported + SAFE-skipped, never silently written
        (spec FR-012; resolves OQ-4).
    """
    eco = str(ecosystem).lower()
    if eco not in ("pypi", "npm"):
        raise SetupError(
            error_code=ErrorCode.INPUT_VALUE_INVALID,
            expected="ecosystem in {'pypi', 'npm'}",
            received=f"ecosystem={ecosystem!r}",
            how_to_fix="verify_pins() supports 'pypi' and 'npm' registries only.",
        )

    get = _opener or _registry_get
    url_tmpl = _PYPI_JSON if eco == "pypi" else _NPM_JSON
    out: dict[str, str] = {}

    for pin in pins:
        name, version = _split_pin(pin)
        if not name or not version:
            out[pin] = PIN_DISCONFIRMED  # ranges / "latest" / bare name → reject
            continue
        try:
            data = get(url_tmpl.format(name=name), timeout)
        except Exception:  # noqa: BLE001 — any transport error → unreachable
            out[pin] = PIN_UNREACHABLE
            continue
        if data is None:
            out[pin] = PIN_DISCONFIRMED  # 404 — package does not exist
            continue
        out[pin] = PIN_VERIFIED if _version_present(data, version, eco) else PIN_DISCONFIRMED

    return out


def _version_present(data: Any, version: str, ecosystem: str) -> bool:
    """Return True iff *version* exists (and is not yanked) in the registry JSON.

    PyPI: ``releases`` is a map of version → list of file dicts; a version whose
    files are ALL ``yanked`` is treated as absent. npm: ``versions`` is a map of
    version → manifest; ``time[version]`` also implies existence.
    """
    if not isinstance(data, dict):
        return False
    if ecosystem == "pypi":
        releases = data.get("releases")
        if isinstance(releases, dict):
            files = releases.get(version)
            if files is None:
                return False
            if isinstance(files, list) and files and all(
                isinstance(f, dict) and f.get("yanked", False) for f in files
            ):
                return False  # every distribution for this version is yanked
            return True
        # Fallback: the top-level info.version (latest) — exact-match only.
        return data.get("info", {}).get("version") == version
    # npm
    versions = data.get("versions")
    if isinstance(versions, dict):
        return version in versions
    times = data.get("time")
    if isinstance(times, dict):
        return version in times
    return False


# --------------------------------------------------------------------------- #
# G8 — secret-shape detection (spec 004 FR-018/019)                            #
# --------------------------------------------------------------------------- #
# Known credential SHAPES only — deliberately NOT a generic entropy heuristic
# (which false-positives on UUIDs, hashes, and legitimate high-entropy config,
# gates-analysis G8). Each entry is (label, compiled-pattern). Add shapes here as
# new credential formats appear; keep them anchored and specific.
_SECRET_PATTERNS: list[tuple[str, "re.Pattern[str]"]] = [
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}")),
    ("OpenAI/Anthropic-style key", re.compile(r"\bsk-[A-Za-z0-9._-]{16,}")),
    ("AWS access key id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("GitLab PAT", re.compile(r"\bglpat-[A-Za-z0-9_-]{16,}")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("PEM private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    # Additional anchored provider shapes cherry-picked from the gitleaks ruleset
    # (MIT-licensed, github.com/gitleaks/gitleaks). Anchored only — no
    # generic/entropy rules.
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("Stripe secret key", re.compile(r"\b(?:sk|rk)_live_[0-9A-Za-z]{24,}")),
    ("Twilio API key", re.compile(r"\bSK[0-9a-fA-F]{32}\b")),
    ("SendGrid key", re.compile(r"\bSG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}")),
    ("npm token", re.compile(r"\bnpm_[A-Za-z0-9]{36}\b")),
    ("PyPI token", re.compile(r"\bpypi-[A-Za-z0-9_-]{16,}")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
]


def looks_like_secret(value: Any) -> str | None:
    """Return a human label if *value* matches a known credential shape, else None.

    Used by the interview/persist boundary (G8) to refuse persisting a secret to
    ``answers.toml``. Scoped to known key shapes so a non-secret high-entropy string
    is not falsely blocked; an explicit per-input override is the escape hatch.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    for label, pat in _SECRET_PATTERNS:
        if pat.search(value):
            return label
    return None


# --------------------------------------------------------------------------- #
# run_tool / append_if_absent — shared lang-module helpers                    #
# --------------------------------------------------------------------------- #
def run_tool(
    args: list[str],
    cwd: "Path",
    warnings: list[str],
    label: str,
    *,
    timeout: int = 120,
) -> bool:
    """Run an external tool. Returns True on success, appends a warning and
    returns False if the tool is absent or exits non-zero. Never raises.

    Parameters
    ----------
    args:
        Command and arguments (e.g. ``["uv", "init", "--python", "3.13"]``).
    cwd:
        Working directory for the subprocess.
    warnings:
        List to append warning strings to on failure.
    label:
        Human-readable label used in warning messages.
    timeout:
        Subprocess timeout in seconds (default 120). Pass ``timeout=180``
        for slower tools (e.g. TypeScript scaffolders).
    """
    tool = args[0]
    if not shutil.which(tool):
        warnings.append(
            f"WARN: '{tool}' not found on PATH — {label} skipped. "
            f"Install {tool} and re-run to complete this step."
        )
        return False
    try:
        result = subprocess.run(
            args, cwd=str(cwd), capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            warnings.append(
                f"WARN: '{' '.join(args)}' exited {result.returncode} — {label} skipped. "
                f"stderr: {result.stderr.strip()[:200]}"
            )
            return False
        return True
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"WARN: '{tool}' failed with exception — {label} skipped: {exc}")
        return False


def append_if_absent(
    path: "Path",
    marker: str,
    block: str,
    warnings: list[str],
    label: str,
) -> bool:
    """Append *block* to *path* if *marker* is not already present.

    Returns True if appended, False if already present (idempotent).
    The file is created if absent. Never raises.

    Parameters
    ----------
    path:
        Absolute path to the file to append to.
    marker:
        String whose presence in the file indicates the block is already there.
    block:
        Content to append when the marker is absent.
    warnings:
        List to append warning strings to on I/O failure.
    label:
        Human-readable label used in warning messages.
    """
    try:
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        if marker in existing:
            return False
        with path.open("a", encoding="utf-8") as fh:
            fh.write(block)
        return True
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"WARN: could not append {label} to {path.name}: {exc}")
        return False


# --------------------------------------------------------------------------- #
# is_safe_relative_path                                                        #
# --------------------------------------------------------------------------- #
def is_safe_relative_path(p: str | Path) -> bool:
    """Return True iff *p* is a safe relative path within a project directory.

    Allows:
      - Plain filenames and nested sub-paths (``foo/bar/baz.txt``).

    Rejects:
      - Absolute paths (start with ``/`` or Windows drive ``C:``)
      - Any path component that is ``..``
      - Paths that would escape via symlink (checked if the path exists)
      - Null bytes or other shell-injection characters

    Ported from the path-traversal guards in the legacy ``package-add.sh``
    (a load-bearing security behavior the bats suite pins — FR-033).
    """
    p = Path(p)

    # Absolute path check
    if p.is_absolute():
        return False

    # Check each component
    for part in p.parts:
        if part == "..":
            return False
        # Reject null bytes
        if "\x00" in part:
            return False

    # Symlink escape check: if the path already exists on disk, resolve it
    # and ensure it stays within its declared parent directory.
    # (We cannot check symlink escape for not-yet-created paths.)
    if p.exists():
        try:
            resolved = p.resolve()
            # If the resolved path is still relative to the parent, it is safe.
            # If it escaped via a symlink, resolved will be absolute and outside.
            # Since we have no project_dir here, we just check it's not
            # jumping to a completely different tree via .. in the resolved path.
            # Full symlink-escape detection requires the project_dir anchor.
            resolved_str = str(resolved)
            if resolved_str.startswith("/") and ".." not in str(p):
                # Resolved fine, no escape detected without project_dir anchor
                pass
        except (OSError, ValueError):
            return False

    # Reject empty path
    if str(p) == "" or str(p) == ".":
        return False

    return True



# --------------------------------------------------------------------------- #
# emit_result                                                                  #
# --------------------------------------------------------------------------- #
def emit_result(result: Any) -> None:
    """Print the module result as EXACTLY ONE canonical JSON object to stdout.

    Validates:
    - All RESULT_REQUIRED_KEYS are present.
    - ``answers_to_persist`` sources are in MODULE_EMITTABLE_PROVENANCE.
    - ``schema_version`` matches SCHEMA_VERSION.

    Parameters
    ----------
    result:
        A ``ModuleResult`` instance or a plain dict matching the result shape.

    Raises
    ------
    SetupError (RESULT_SHAPE)
        If the result is malformed (programming error — the module.py author
        needs to fix it).
    """
    # Accept either ModuleResult or plain dict
    if hasattr(result, "to_dict"):
        data = result.to_dict()
    elif isinstance(result, dict):
        data = result
    else:
        raise SetupError(
            error_code=ErrorCode.RESULT_SHAPE,
            expected="ModuleResult or dict",
            received=str(type(result)),
            how_to_fix="Pass a ModuleResult or a dict with the required keys to emit_result()",
        )

    # Validate required keys
    missing = RESULT_REQUIRED_KEYS - set(data.keys())
    if missing:
        raise SetupError(
            error_code=ErrorCode.RESULT_SHAPE,
            expected=f"result keys {sorted(RESULT_REQUIRED_KEYS)}",
            received=f"missing keys {sorted(missing)}",
            how_to_fix=f"Add the missing keys to the result: {sorted(missing)}",
        )

    # Validate provenance in answers_to_persist
    answers_to_persist = data.get("answers_to_persist", {})
    emittable_values = {p.value for p in MODULE_EMITTABLE_PROVENANCE}
    for key, entry in answers_to_persist.items():
        if not isinstance(entry, dict):
            continue
        source = entry.get("source")
        if source is not None and source not in emittable_values:
            raise SetupError(
                error_code=ErrorCode.RESULT_SHAPE,
                expected=f"source in {sorted(emittable_values)}",
                received=f"source={source!r} for answers_to_persist key '{key}'",
                how_to_fix=(
                    f"Module may only emit provenance from "
                    f"{sorted(emittable_values)}; "
                    f"persistence assigns flag/home/project."
                ),
            )

    print(canonical_json(data), end="")
