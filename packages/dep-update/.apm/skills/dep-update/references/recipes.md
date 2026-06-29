# dep-update: registry endpoints + apply commands + semver rules

A reference cookbook for the deterministic parts of the dep-update skill.
All registry endpoints are machine-readable JSON — never scrape rendered HTML
for version numbers. Reserve web-fetch / browser for changelog prose
(migration guides, breaking-change blogs) that has no structured endpoint.

---

## Registry endpoints

### PyPI

```sh
UA='dep-update-skill (+https://github.com/srobroek/agentic-packages)'

# Latest version + yanked status + source repo URL
curl -fsSL -A "$UA" "https://pypi.org/pypi/<name>/json" \
  | python3 -c '
import sys, json
d = json.load(sys.stdin)
info = d["info"]
print("latest :", info["version"])
print("yanked :", info.get("yanked", False))
print("repo   :", info.get("project_urls", {}).get("Source") or info.get("home_page"))
'

# All release versions + yanked flags (to skip yanked candidates)
curl -fsSL -A "$UA" "https://pypi.org/pypi/<name>/json" \
  | python3 -c '
import sys, json
d = json.load(sys.stdin)
for ver, files in d["releases"].items():
    yanked = all(f.get("yanked", False) for f in files) if files else False
    print(ver, "YANKED" if yanked else "")
'
```

A version where **all** published files are yanked is `DISCONFIRMED` and must
not be offered as an upgrade target.

### npm / pnpm / yarn / bun

```sh
UA='dep-update-skill (+https://github.com/srobroek/agentic-packages)'

# Latest version + repo
curl -fsSL -A "$UA" "https://registry.npmjs.org/<name>" \
  | python3 -c '
import sys, json
d = json.load(sys.stdin)
latest = d["dist-tags"]["latest"]
repo = d.get("repository", {})
repo_url = repo.get("url", repo) if isinstance(repo, dict) else repo
print("latest:", latest)
print("repo  :", repo_url)
print("deprecated:", d["versions"][latest].get("deprecated", "no"))
'

# All published versions
curl -fsSL -A "$UA" "https://registry.npmjs.org/<name>" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print(*d["versions"].keys(), sep="\n")'
```

### Go modules (advisory only — no apply)

```sh
# Latest via the Go module proxy
curl -fsSL "https://proxy.golang.org/<module>/@latest"
# -> {"Version":"v1.2.3","Time":"..."}

# All versions
curl -fsSL "https://proxy.golang.org/<module>/@v/list"
# -> newline-separated version tags
```

### Rust / crates.io (advisory only — no apply)

```sh
UA='dep-update-skill (+https://github.com/srobroek/agentic-packages)'
curl -fsSL -A "$UA" "https://crates.io/api/v1/crates/<name>" \
  | python3 -c '
import sys, json
d = json.load(sys.stdin)["crate"]
print("latest:", d["max_stable_version"])
print("repo  :", d.get("repository", ""))
'
```

---

## Per-ecosystem apply commands

| Ecosystem  | Package manager | Apply command                                   | Notes                                      |
|------------|-----------------|------------------------------------------------|--------------------------------------------|
| Python     | uv              | `uv add "name==new_ver"`                        | Updates pyproject.toml + uv.lock atomically |
| Python     | pip (fallback)  | `pip install "name==new_ver"` + update manifest | Manual: edit requirements.txt / pyproject.toml |
| Node       | pnpm            | `pnpm update name --version new_ver`            |                                            |
| Node       | bun             | `bun add "name@new_ver"`                        |                                            |
| Node       | yarn            | `yarn add "name@new_ver"`                       |                                            |
| Node       | npm             | `npm install "name@new_ver"`                    |                                            |
| Rust       | (advisory only) | `cargo update -p name --precise new_ver`        | Not applied by this skill; advisory only   |
| Go         | (advisory only) | `go get module@new_ver && go mod tidy`          | Not applied by this skill; advisory only   |

Node package manager precedence (when `answers.toml` is absent):
`pnpm-lock.yaml` → `bun.lock`/`bun.lockb` → `yarn.lock` → `package-lock.json`.

---

## Semver classification rule

Given installed version `A.B.C` and candidate latest `X.Y.Z` (normalized to
three numeric parts; leading `v` stripped; pre-release suffixes stripped for
comparison):

| Condition           | Safety class      | Apply offered? |
|---------------------|-------------------|----------------|
| `A==X, B==Y, C<Z`  | `PATCH-SAFE`       | Yes            |
| `A==X, B<Y`        | `MINOR-CHECK`      | Yes (with cite)|
| `A<X`              | `MAJOR-ADVISORY`   | **Never**      |
| `A==X, B==Y, C==Z` | CURRENT (omit)     | n/a            |

Pre-release candidates (`rc`, `alpha`, `beta`, `a`, `b`, `dev`) are excluded
from the upgrade offer unless the installed version is also pre-release. The
latest stable version is used instead.

All-yanked PyPI versions are `DISCONFIRMED` and not offered.

A dep with no registry response (404, auth error, timeout, network down) is
`UNRESOLVABLE` — listed with the reason, skill continues with remaining deps.

---

## Changelog fetch order (MINOR-CHECK + MAJOR-ADVISORY)

1. Registry metadata URLs (`info.project_urls.Source` for PyPI; `repository`
   for npm) — machine-readable, no network scraping.
2. Blobless bare git clone at the tag span (`git clone --bare --filter=blob:none`):
   ```sh
   REPO=<url-from-registry>; FROM=<current-tag>; TO=<latest-tag>
   TMP=$(mktemp -d)
   git clone --bare --filter=blob:none "$REPO" "$TMP/r.git" 2>/dev/null
   G="git --git-dir=$TMP/r.git"
   # Find actual tag names (handle v-prefix, @-prefix, etc.)
   $G tag --list | grep -E "(^|[-@/])v?${FROM}$"
   $G tag --list | grep -E "(^|[-@/])v?${TO}$"
   # CHANGELOG at the target tag
   for f in CHANGELOG.md CHANGELOG CHANGES.md HISTORY.md NEWS.md; do
     $G cat-file -e "${TO}:${f}" 2>/dev/null && { $G show "${TO}:${f}"; break; }
   done
   rm -rf "$TMP"
   ```
3. Migration / breaking-change prose page (web-fetch only for MAJOR-ADVISORY):
   ```sh
   # Find the migration guide path in the repo first
   $G ls-tree -r --name-only "$TO" | grep -iE 'migrat|upgrad|breaking'
   ```
   Prefer the project's own guide over third-party blogs; flag blogs as
   derivative. Only now is a targeted web fetch justified.
4. If none found: report "no changelog found" and advise the user to check
   the upstream repo manually.

Each source must be cited by URL or git tag in the upgrade plan.

---

## answers.toml read (opportunistic)

```python
# Python >= 3.11 stdlib tomllib; else install tomli backport.
try:
    import tomllib
except ImportError:
    import tomli as tomllib  # pip install tomli

import pathlib

answers_path = pathlib.Path(".project-setup/answers.toml")
if answers_path.exists():
    with open(answers_path, "rb") as fh:
        data = tomllib.load(fh)
    # Python module baseline pins
    py = data.get("module", {}).get("lang-python", {})
    pinned_deps = py.get("pinned_deps", [])   # list of "name@version" strings
    dev_deps    = py.get("dev_deps", [])
    framework   = py.get("framework", "")
    python_ver  = py.get("python_version", "")
    ruff_ver    = py.get("ruff_version", "")
    # TypeScript module baseline pins
    ts = data.get("module", {}).get("lang-ts", {})
    ts_pinned    = ts.get("pinned_deps", [])
    ts_dev       = ts.get("dev_deps", [])
    pkg_manager  = ts.get("package_manager", "")
    pkg_mgr_pin  = ts.get("package_manager_pin", "")
```

Absent file, absent `[module.lang-*]` section, or absent key → use empty
defaults. Never raise an error for missing answers.toml.

The `pinned_deps` format is `"name@exact-version"` strings. Parse as:
```python
for entry in pinned_deps:
    name, _, ver = entry.partition("@")
```

If a dep's lockfile version differs from its `answers.toml` baseline version,
flag it as "drifted from project-setup baseline: <baseline>" in the plan row.
