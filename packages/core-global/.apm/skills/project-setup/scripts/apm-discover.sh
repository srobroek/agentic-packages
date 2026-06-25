#!/usr/bin/env bash
# shellcheck shell=bash
# Resolve APM, ensure remote marketplaces are registered, print package
# inventory, and show/update package preferences for project setup.
#
# Usage:
#   apm-discover.sh [--profile name] [--select-package package@marketplace]
#                   [--selection-note text]
#                   [--preferences-file path] [--no-update-preferences]
#                   [--marketplace-repo owner/repo] [--marketplace-name name]
#                   [--extra-marketplace name=owner/repo]
#                   [--skip-marketplace-register] [--first-party-only]
#
# Marketplace registry comes from agentic-packages/indexes/apm-package-preferences.json
# .marketplaces when available, ordered by priority. Add future marketplaces there.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTIC_TOOLS_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
PREFERENCES_FILE="${APM_PACKAGE_PREFERENCES_FILE:-}"
if [ -z "$PREFERENCES_FILE" ]; then
    if [ -f "indexes/apm-package-preferences.json" ]; then
        PREFERENCES_FILE="indexes/apm-package-preferences.json"
    elif [ -f "$AGENTIC_TOOLS_DIR/indexes/apm-package-preferences.json" ]; then
        PREFERENCES_FILE="$AGENTIC_TOOLS_DIR/indexes/apm-package-preferences.json"
    else
        PREFERENCES_FILE="indexes/apm-package-preferences.json"
    fi
fi
REGISTER_MARKETPLACE=true
DEFAULT_MARKETPLACES=(
    "srobroek-agentic=srobroek/agentic-packages"
    "wshobson-agents=wshobson/agents"
    "voltagent-subagents=VoltAgent/awesome-claude-code-subagents"
)
MARKETPLACES=()
EXTRA_MARKETPLACES=()
FIRST_PARTY_ONLY=false
FIRST_MARKETPLACE_REPO=""
FIRST_MARKETPLACE_NAME=""
PROFILES=()
SELECTED_PACKAGES=()
SELECTION_NOTE=""
UPDATE_PREFERENCES=true

run_apm() {
    if [ -z "${GITHUB_APM_PAT:-}" ] && command -v gh >/dev/null 2>&1; then
        GITHUB_APM_PAT="$(gh auth token 2>/dev/null || true)"
        if [ -n "$GITHUB_APM_PAT" ]; then
            export GITHUB_APM_PAT
        fi
    fi

    if command -v apm >/dev/null 2>&1; then
        apm "$@"
    elif command -v mise >/dev/null 2>&1 && mise which apm >/dev/null 2>&1; then
        mise exec -- apm "$@"
    elif command -v uv >/dev/null 2>&1; then
        uv tool run --from apm-cli apm "$@"
    else
        return 127
    fi
}

add_marketplace() {
    local entry="$1"
    if [[ "$entry" != *=* ]]; then
        echo "Error: marketplace must use name=owner/repo format: $entry" >&2
        exit 1
    fi
    EXTRA_MARKETPLACES+=("$entry")
}

load_marketplaces() {
    if [ ! -f "$PREFERENCES_FILE" ]; then
        printf '%s\n' "${DEFAULT_MARKETPLACES[@]}"
        return 0
    fi

    python3 - "$PREFERENCES_FILE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
marketplaces = data.get("marketplaces", {})
rows = []
for name, meta in marketplaces.items():
    if not meta.get("default", True):
        continue
    repo = meta.get("repo")
    if not repo:
        continue
    rows.append((int(meta.get("priority", 0)), name, repo))

for _priority, name, repo in sorted(rows, reverse=True):
    print(f"{name}={repo}")
PY
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --profile) PROFILES+=("${2:?--profile needs a value}"); shift 2 ;;
        --select-package) SELECTED_PACKAGES+=("${2:?--select-package needs a value}"); shift 2 ;;
        --selection-note) SELECTION_NOTE="${2:?--selection-note needs a value}"; shift 2 ;;
        --preferences-file) PREFERENCES_FILE="${2:?--preferences-file needs a value}"; shift 2 ;;
        --no-update-preferences) UPDATE_PREFERENCES=false; shift ;;
        --first-party-only)
            FIRST_PARTY_ONLY=true
            shift
            ;;
        --marketplace-repo)
            FIRST_MARKETPLACE_REPO="${2:?--marketplace-repo needs a value}"
            shift 2
            ;;
        --marketplace-name)
            FIRST_MARKETPLACE_NAME="${2:?--marketplace-name needs a value}"
            shift 2
            ;;
        --include-upstream-agents)
            # Backward-compatible no-op: upstream marketplaces are included by default.
            shift
            ;;
        --include-wshobson-agents)
            add_marketplace "wshobson-agents=wshobson/agents"
            shift
            ;;
        --include-voltagent-subagents)
            add_marketplace "voltagent-subagents=VoltAgent/awesome-claude-code-subagents"
            shift
            ;;
        --extra-marketplace)
            add_marketplace "${2:?--extra-marketplace needs a value}"
            shift 2
            ;;
        --skip-marketplace-register) REGISTER_MARKETPLACE=false; shift ;;
        --help)
            sed -n '2,/^$/p' "$0" | sed -E 's/^#[[:space:]]?//'
            exit 0
            ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

if ! run_apm --version >/dev/null 2>&1; then
    echo "Error: apm is not available via apm, mise exec -- apm, or uv tool run --from apm-cli apm" >&2
    exit 127
fi

echo "APM: $(run_apm --version)"

MARKETPLACES=()
while IFS= read -r _mp_line; do
    [ -n "$_mp_line" ] && MARKETPLACES+=("$_mp_line")
done < <(load_marketplaces)
if [ "${#MARKETPLACES[@]}" -eq 0 ]; then
    MARKETPLACES=("${DEFAULT_MARKETPLACES[@]}")
fi

if [ -n "$FIRST_MARKETPLACE_REPO" ] || [ -n "$FIRST_MARKETPLACE_NAME" ]; then
    first_name="${MARKETPLACES[0]%%=*}"
    first_repo="${MARKETPLACES[0]#*=}"
    [ -n "$FIRST_MARKETPLACE_NAME" ] && first_name="$FIRST_MARKETPLACE_NAME"
    [ -n "$FIRST_MARKETPLACE_REPO" ] && first_repo="$FIRST_MARKETPLACE_REPO"
    MARKETPLACES=("$first_name=$first_repo" "${MARKETPLACES[@]:1}")
fi

if $FIRST_PARTY_ONLY; then
    MARKETPLACES=("${MARKETPLACES[0]}")
fi

if [ "${#EXTRA_MARKETPLACES[@]}" -gt 0 ]; then
    MARKETPLACES+=("${EXTRA_MARKETPLACES[@]}")
fi

ensure_marketplace() {
    local entry="$1"
    local name="${entry%%=*}"
    local repo="${entry#*=}"

    if $REGISTER_MARKETPLACE; then
        echo "Ensuring marketplace: $name ($repo)"
        if run_apm marketplace list | awk '{print $1}' | grep -qx "$name"; then
            run_apm marketplace update "$name" || true
        else
            run_apm marketplace add "$repo" --name "$name"
        fi
    else
        echo "Skipping marketplace registration/update: $name ($repo)"
    fi
}

for marketplace in "${MARKETPLACES[@]}"; do
    ensure_marketplace "$marketplace"
done

echo "Registered marketplaces:"
run_apm marketplace list

for marketplace in "${MARKETPLACES[@]}"; do
    marketplace_name="${marketplace%%=*}"
    echo ""
    echo "Packages from $marketplace_name:"
    run_apm marketplace browse "$marketplace_name"
done

echo ""
echo "Preferred package choices:"
python3 - "$PREFERENCES_FILE" "${PROFILES[@]+"${PROFILES[@]}"}" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
profiles = [profile.lower() for profile in sys.argv[2:]] or ["all"]

if not path.exists():
    print(f"  WARN: preference index not found: {path}")
    raise SystemExit(0)

data = json.loads(path.read_text())
packages = data.get("preferred_packages", {})
rows = []
for package_id, meta in packages.items():
    package_profiles = [profile.lower() for profile in meta.get("profiles", [])]
    if "all" not in profiles and not set(profiles).intersection(package_profiles):
        continue
    priority = int(meta.get("priority", 0))
    selection_count = int(meta.get("selection_count", 0))
    score = priority + (selection_count * 10)
    rows.append((score, priority, selection_count, package_id, meta))

if not rows:
    print("  No preference-index matches for profiles: " + ", ".join(profiles))
    raise SystemExit(0)

for score, priority, selection_count, package_id, meta in sorted(rows, reverse=True):
    profiles_text = ", ".join(meta.get("profiles", []))
    reason = meta.get("reason", "")
    print(f"  - {package_id}")
    print(f"    score: {score} priority: {priority} selections: {selection_count} profiles: {profiles_text}")
    if reason:
        print(f"    reason: {reason}")
    print(f"    install: apm install {package_id}")
    print(f"    setup flag: --apm-dependency {package_id}")
PY

echo ""
echo "Non-preferred package choices:"
echo "  Any package shown in the marketplace browse tables above may be selected."
echo "  Selecting a non-preferred package promotes it into the preference index:"
echo "    --select-package <package@marketplace> --selection-note <why>"

if [ "${#SELECTED_PACKAGES[@]}" -gt 0 ]; then
    if ! $UPDATE_PREFERENCES; then
        echo ""
        echo "Preference index update skipped by --no-update-preferences"
    else
        echo ""
        echo "Updating preference index:"
        python3 - "$PREFERENCES_FILE" "$SELECTION_NOTE" "$(IFS=,; printf '%s' "${PROFILES[*]+"${PROFILES[*]}"}")" "${SELECTED_PACKAGES[@]+"${SELECTED_PACKAGES[@]}"}" <<'PY'
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
note = sys.argv[2]
profile_arg = sys.argv[3]
selected = sys.argv[4:]
selected_profiles = [item for item in profile_arg.split(",") if item] or ["all"]
path.parent.mkdir(parents=True, exist_ok=True)

if path.exists():
    data = json.loads(path.read_text())
else:
    data = {"schema_version": 1, "marketplaces": {}, "preferred_packages": {}}

packages = data.setdefault("preferred_packages", {})
timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

for package_id in selected:
    if "@" not in package_id:
        raise SystemExit(f"Invalid package id, expected package@marketplace: {package_id}")
    meta = packages.setdefault(
        package_id,
        {
            "priority": 50,
            "profiles": selected_profiles,
            "reason": f"Selected during project setup: {note}" if note else "Selected during project setup.",
            "selection_count": 0,
        },
    )
    existing_profiles = set(meta.get("profiles", []))
    for profile in selected_profiles:
        existing_profiles.add(profile)
    meta["profiles"] = sorted(existing_profiles)
    meta["selection_count"] = int(meta.get("selection_count", 0)) + 1
    meta["last_selected_at"] = timestamp
    if note:
        meta["last_selection_note"] = note
    print(f"  - {package_id}: selections={meta['selection_count']}")

path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

try:
    repo_check = subprocess.run(
        ["git", "-C", str(path.parent), "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    if repo_check.returncode == 0:
        subprocess.run(["git", "-C", str(path.parent), "diff", "--", str(path)], check=False)
except FileNotFoundError:
    pass
PY
    fi
fi
