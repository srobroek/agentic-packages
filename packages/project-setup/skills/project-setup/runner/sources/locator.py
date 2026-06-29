"""Locator parsing — sole owner of source-locator resolution.

Parses every supported locator form into a structured ``Locator`` dataclass:

  * GitHub shorthand:  ``owner/repo``, ``owner/repo/subdir``, ``owner/repo#ref``
  * Full HTTPS URL:    ``https://github.com/owner/repo[.git][/subdir][#ref]``
  * SSH URL:           ``git@github.com:owner/repo[.git][#ref]``
  * Local path:        any absolute path, or a relative path starting with
                       ``./`` or ``../``, or any path whose first component
                       exists on disk (heuristic).

``normalize_origin`` collapses the three git URL forms for the same repository
to one canonical string so that the cache key is stable regardless of which
form a user typed.  ``cache_key`` returns a short stable hex digest.

Standard library only (no third-party imports).  No network access.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Locator dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Locator:
    """Parsed representation of a module source locator.

    Attributes
    ----------
    kind:
        ``"git"`` for any remote git repository, ``"local"`` for a
        filesystem path.
    origin:
        For *git*: the NORMALIZED canonical origin string used as the cache
        key seed (e.g. ``"github.com/owner/repo"``).  For *local*: the
        absolute filesystem path as a string.
    subdir:
        Subdirectory within the repository/path that contains modules, or
        ``""`` if the root itself is the module root.
    ref:
        Git ref (branch, tag, SHA).  Defaults to ``"HEAD"`` when omitted.
        Unused for *local* locators.
    """

    kind: str       # "git" | "local"
    origin: str     # normalized canonical origin
    subdir: str     # "" or "path/inside/repo"
    ref: str        # git ref; "HEAD" when omitted; unused for local


# ---------------------------------------------------------------------------
# Internal parsing helpers
# ---------------------------------------------------------------------------

# Matches:  owner/repo[/rest...][#ref]
#   owner and repo must be non-empty, no protocol prefix, no dots-at-start.
_SHORTHAND_RE = re.compile(
    r'^(?P<owner>[A-Za-z0-9_.\-]+)/(?P<repo>[A-Za-z0-9_.\-]+)'
    r'(?P<rest>/[^#]*)?'
    r'(?:#(?P<ref>.+))?$'
)

# Matches SSH git URLs:  git@<host>:<owner>/<repo>[.git][#ref]
_SSH_RE = re.compile(
    r'^git@(?P<host>[^:]+):(?P<owner>[^/]+)/(?P<repo>[^/.#]+)(\.git)?'
    r'(?:#(?P<ref>.+))?$'
)

# Matches HTTPS git URLs:  https://<host>/<owner>/<repo>[.git][/<subdir>][#ref]
_HTTPS_RE = re.compile(
    r'^https?://(?P<host>[^/]+)/(?P<owner>[^/]+)/(?P<repo>[^/.#]+)(\.git)?'
    r'(?P<rest>/[^#]*)?'
    r'(?:#(?P<ref>.+))?$'
)


def _clean_subdir(raw: str | None) -> str:
    """Normalise a captured rest-path into a clean subdir string."""
    if not raw:
        return ""
    return raw.strip("/")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_locator(raw: str) -> Locator:
    """Parse *raw* into a :class:`Locator`.

    Raises
    ------
    ValueError
        If the locator cannot be parsed into any recognised form.
    """
    raw = raw.strip()
    if not raw:
        raise ValueError("empty locator string")

    # 1. Local path detection: absolute, or ./…, or ../…
    p = Path(raw.split("#")[0])  # drop any fragment before path-checking
    if (
        raw.startswith("/")
        or raw.startswith("./")
        or raw.startswith("../")
        or p.is_absolute()
    ):
        return Locator(kind="local", origin=str(Path(raw).expanduser().resolve()), subdir="", ref="")

    # 2. SSH URL
    m = _SSH_RE.match(raw)
    if m:
        host = m.group("host")
        owner = m.group("owner")
        repo = m.group("repo")
        ref = m.group("ref") or "HEAD"
        origin = normalize_origin(f"git@{host}:{owner}/{repo}.git")
        return Locator(kind="git", origin=origin, subdir="", ref=ref)

    # 3. HTTPS URL
    m = _HTTPS_RE.match(raw)
    if m:
        host = m.group("host")
        owner = m.group("owner")
        repo = m.group("repo")
        subdir = _clean_subdir(m.group("rest"))
        ref = m.group("ref") or "HEAD"
        origin = normalize_origin(f"https://{host}/{owner}/{repo}.git")
        return Locator(kind="git", origin=origin, subdir=subdir, ref=ref)

    # 4. Shorthand  owner/repo[/subdir...][#ref]
    #    Guard: must not look like a local relative path that happens to
    #    contain a slash (e.g. "src/foo").  We accept it as a git shorthand
    #    only when the first component is not an existing filesystem entry.
    m = _SHORTHAND_RE.match(raw)
    if m:
        owner = m.group("owner")
        repo = m.group("repo")
        rest = m.group("rest") or ""
        ref = m.group("ref") or "HEAD"

        # If the first component is an existing directory on disk treat it as
        # a local path — this avoids misidentifying "myteam/local-modules" on
        # a machine where "myteam/" is a real directory.
        first_component = Path(owner)
        if first_component.is_dir():
            full = Path(raw.split("#")[0]).expanduser().resolve()
            return Locator(kind="local", origin=str(full), subdir="", ref="")

        subdir = _clean_subdir(rest)
        origin = normalize_origin(f"https://github.com/{owner}/{repo}.git")
        return Locator(kind="git", origin=origin, subdir=subdir, ref=ref)

    raise ValueError(f"cannot parse locator: {raw!r}")


def normalize_origin(raw_origin: str) -> str:
    """Collapse all URL forms for the same git repository into one string.

    Rules
    -----
    * Strip ``.git`` suffix.
    * Rewrite SSH ``git@github.com:owner/repo`` → ``github.com/owner/repo``.
    * Strip ``https://`` / ``http://`` scheme prefix.
    * Lower-case the host portion only (paths are case-sensitive on GitHub).
    * Strip trailing slashes.

    The result is always in the form ``host/owner/repo`` (no scheme, no
    ``.git``, no trailing slash).
    """
    s = raw_origin.strip()

    # SSH form: git@host:owner/repo[.git]
    m = re.match(r'^git@([^:]+):(.+?)(?:\.git)?$', s)
    if m:
        host = m.group(1).lower()
        path = m.group(2).rstrip("/")
        return f"{host}/{path}"

    # HTTPS / HTTP form
    m = re.match(r'^https?://([^/]+)/(.+?)(?:\.git)?/?$', s)
    if m:
        host = m.group(1).lower()
        path = m.group(2).rstrip("/")
        return f"{host}/{path}"

    # Bare host/owner/repo (already normalized or shorthand seed)
    s = s.rstrip("/")
    if s.endswith(".git"):
        s = s[:-4]
    return s


def cache_key(locator: Locator) -> str:
    """Return a short stable hex digest for *locator*.

    For **git** locators the key is derived from the normalized origin AND the
    ref so that different pinned refs of the same repository map to DIFFERENT
    cache directories (e.g. ``org/addons#v1`` and ``org/addons#v2`` coexist
    without thrashing).  The same ``(origin, ref)`` pair always resolves to the
    same directory, enabling cross-project reuse when two projects pin the same
    addon at the same ref.  Subdir slicing happens inside the cache entry and
    does not affect the key.

    For **local** locators the key is derived from the absolute origin path
    only (the ref field is unused for local sources).
    """
    if locator.kind == "local":
        seed = locator.origin.encode()
    else:
        seed = f"{locator.origin}@{locator.ref}".encode()
    return hashlib.sha256(seed).hexdigest()[:16]
