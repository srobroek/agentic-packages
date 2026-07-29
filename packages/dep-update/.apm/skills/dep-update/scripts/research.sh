#!/usr/bin/env bash
#
# dep-update/research.sh: for each dependency from detect.py, query its
# registry for the current latest version and classify the potential bump.
#
# Portability floor: bash 3.2.57 + BSD sed/grep/awk (stock macOS). Registry
# queries use an embedded python3 block (stdlib urllib+json only, no third-
# party deps). No runner SDK import.
#
# Input: reads "ecosystem<TAB>name<TAB>version" lines from stdin (detect.py
# output), or a project dir as the first argument (detect.py is run internally).
#
# Output: one JSON-lines record per dependency on stdout:
#   {"ecosystem":"pypi","name":"requests","installed":"2.28.0",
#    "latest":"2.32.3","class":"MINOR-CHECK","status":"OK"}
#
# status values:
#   OK            — classified successfully
#   CURRENT       — installed == latest; omit from upgrade plan
#   UNRESOLVABLE  — 404 / auth / network error; skip gracefully
#   DISCONFIRMED  — all PyPI files for the candidate are yanked; skip
#
# Test seam: set DEP_UPDATE_REGISTRY_OPENER to a path to a Python script that
# provides a custom urllib opener. The opener script must define a module-level
# function `build_opener()` returning a urllib.request opener, or set the env
# var to a fixture directory path (see inline logic below). In tests, set
# DEP_UPDATE_REGISTRY_OPENER to the path of a Python file that monkey-patches
# the fetch function.
#
# Simpler test seam: set DEP_UPDATE_FIXTURE_DIR to a directory containing
# <ecosystem>_<name>.json fixture files. When set, the registry fetch reads the
# fixture file instead of making a network call. This is the recommended test
# approach.
#
# Usage: research.sh [project-dir]
#   With no stdin (terminal), runs detect.py against project-dir first.

set -uo pipefail

note() { printf '%s\n' "$*" >&2; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# --- collect deps into a temp file -----------------------------------------
# Writes dep lines (ecosystem<TAB>name<TAB>version) to a temp file.
# If RESEARCH_USE_STDIN=1 is set, reads from stdin (for tests / piped use).
# Otherwise runs detect.py against the target dir.

collect_deps() {
  local target="${1:-.}"
  local tmpfile
  tmpfile=$(mktemp "${TMPDIR:-/tmp}/dep-update-deps.XXXXXX")
  if [ "${RESEARCH_USE_STDIN:-0}" = "1" ]; then
    cat >"$tmpfile"
  else
    python3 "${SCRIPT_DIR}/detect.py" "$target" 2>/dev/null >"$tmpfile"
  fi
  printf '%s' "$tmpfile"
}

# --- registry query via embedded python3 ------------------------------------
#
# The python block reads registry JSON and prints a JSON-lines result.
# All classification logic lives here to avoid fragile shell JSON parsing.

query_registry() {
  local ecosystem="$1"
  local name="$2"
  local installed="$3"

  # Pass variables via environment to avoid @Q bash 4+ quoting.
  _QR_ECOSYSTEM="$ecosystem" _QR_NAME="$name" _QR_INSTALLED="$installed" \
  python3 - <<'PY'
import json
import os
import sys
import urllib.request
import urllib.error

ecosystem = os.environ["_QR_ECOSYSTEM"]
name = os.environ["_QR_NAME"]
installed = os.environ["_QR_INSTALLED"]

def fetch_json(url):
    """Fetch JSON from url. Honour DEP_UPDATE_FIXTURE_DIR for offline tests."""
    fixture_dir = os.environ.get("DEP_UPDATE_FIXTURE_DIR", "")
    if fixture_dir:
        # Fixture filename: <ecosystem>_<name>.json  (/ in name -> __)
        safe_name = name.replace("/", "__").replace("@", "__at__")
        fixture = os.path.join(fixture_dir, f"{ecosystem}_{safe_name}.json")
        if os.path.exists(fixture):
            with open(fixture) as fh:
                return json.load(fh)
        # No fixture => simulate offline
        raise urllib.error.URLError("fixture not found (offline simulation)")
    ua = "dep-update-skill (+https://github.com/srobroek/agentic-packages)"
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp)

def normalize_version(v):
    """Return (major, minor, patch) tuple or None for non-numeric versions."""
    # Strip leading 'v'
    v = v.lstrip("v")
    # Strip pre-release/local suffixes
    import re
    m = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?", v)
    if not m:
        return None
    major = int(m.group(1))
    minor = int(m.group(2) or 0)
    patch = int(m.group(3) or 0)
    return (major, minor, patch)

def is_prerelease(v):
    import re
    return bool(re.search(r"(a|b|rc|alpha|beta|dev|post)[\d.]", v, re.I))

def classify(installed_v, latest_v):
    """Return PATCH-SAFE / MINOR-CHECK / MAJOR-ADVISORY / CURRENT."""
    cur = normalize_version(installed_v)
    lat = normalize_version(latest_v)
    if cur is None or lat is None:
        return "MINOR-CHECK"  # conservative fallback for non-semver
    if cur == lat:
        return "CURRENT"
    if lat[0] > cur[0]:
        return "MAJOR-ADVISORY"
    if lat[0] == cur[0] and lat[1] > cur[1]:
        return "MINOR-CHECK"
    if lat[0] == cur[0] and lat[1] == cur[1] and lat[2] > cur[2]:
        return "PATCH-SAFE"
    # latest is older than installed (e.g. installed is pre-release beyond latest stable)
    return "CURRENT"

result = {"ecosystem": ecosystem, "name": name, "installed": installed}

try:
    if ecosystem == "pypi":
        url = f"https://pypi.org/pypi/{name}/json"
        data = fetch_json(url)
        latest = data["info"]["version"]
        # Check for yanked: if the latest version has all files yanked, DISCONFIRMED.
        releases = data.get("releases", {})
        latest_files = releases.get(latest, [])
        if latest_files and all(f.get("yanked", False) for f in latest_files):
            result.update({"status": "DISCONFIRMED", "latest": latest,
                           "class": "DISCONFIRMED",
                           "reason": "all files for latest are yanked on PyPI"})
            print(json.dumps(result))
            sys.exit(0)
    elif ecosystem in ("npm", "node"):
        url = f"https://registry.npmjs.org/{name}"
        data = fetch_json(url)
        latest = data.get("dist-tags", {}).get("latest", "")
        if not latest:
            result.update({"status": "UNRESOLVABLE", "reason": "no dist-tags.latest"})
            print(json.dumps(result))
            sys.exit(0)
    else:
        # cargo / go: advisory reporting only; no registry fetch implemented here.
        result.update({"status": "UNRESOLVABLE",
                       "reason": f"registry fetch not implemented for {ecosystem} (advisory-only)"})
        print(json.dumps(result))
        sys.exit(0)
except urllib.error.HTTPError as e:
    code = e.code
    reason = "auth-required" if code in (401, 403) else f"HTTP {code}"
    result.update({"status": "UNRESOLVABLE", "reason": reason})
    print(json.dumps(result))
    sys.exit(0)
except urllib.error.URLError as e:
    result.update({"status": "UNRESOLVABLE", "reason": f"network error: {e.reason}"})
    print(json.dumps(result))
    sys.exit(0)
except Exception as e:
    result.update({"status": "UNRESOLVABLE", "reason": str(e)})
    print(json.dumps(result))
    sys.exit(0)

# Skip pre-releases unless installed is also pre-release.
if is_prerelease(latest) and not is_prerelease(installed):
    # Find the latest stable version.
    if ecosystem == "pypi":
        all_versions = list(releases.keys())
    else:
        all_versions = list(data.get("versions", {}).keys())
    stable = [v for v in all_versions if not is_prerelease(v)]
    if stable:
        # Sort by normalized tuple descending.
        stable.sort(key=lambda v: normalize_version(v) or (0, 0, 0), reverse=True)
        latest = stable[0]
    else:
        # All are pre-release; use the original latest.
        pass

cls = classify(installed, latest)

result.update({"latest": latest, "class": cls,
               "status": "CURRENT" if cls == "CURRENT" else "OK"})
print(json.dumps(result))
PY
}

# --- main ------------------------------------------------------------------

main() {
  local target="${1:-.}"

  if [ ! -d "$target" ]; then
    note "research.sh: '$target' is not a directory"
    return 2
  fi

  note "dep-update/research: querying registries..."
  note ""

  local total=0 ok=0 unresolvable=0 current=0

  # Collect deps into a temp file to avoid stdin/process-substitution conflicts.
  local deps_file
  deps_file=$(collect_deps "$target")

  while IFS=$'\t' read -r ecosystem name version; do
    [ -n "$ecosystem" ] || continue
    [ -n "$name" ]      || continue
    total=$((total + 1))
    local rec
    rec=$(query_registry "$ecosystem" "$name" "$version")
    printf '%s\n' "$rec"
    # Tally for summary (parse status with grep for portability).
    local status
    status=$(printf '%s\n' "$rec" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("status","?"))' 2>/dev/null || echo "?")
    case "$status" in
      OK)            ok=$((ok + 1)) ;;
      CURRENT)       current=$((current + 1)) ;;
      UNRESOLVABLE)  unresolvable=$((unresolvable + 1)) ;;
      DISCONFIRMED)  unresolvable=$((unresolvable + 1)) ;;
    esac
  done < "$deps_file"
  rm -f "$deps_file"

  note ""
  note "dep-update/research: ${total} dep(s) queried"
  note "  classified:    ${ok}"
  note "  already-current: ${current}"
  note "  unresolvable:  ${unresolvable}"

  if [ "$total" -gt 0 ] && [ "$ok" -eq 0 ] && [ "$current" -eq 0 ] && [ "$unresolvable" -eq "$total" ]; then
    note ""
    note "WARNING: all registry queries failed — no registry access or all deps are private."
    note "No upgrade plan can be produced. Check your network connection and retry."
  fi

  return 0
}

main "$@"
