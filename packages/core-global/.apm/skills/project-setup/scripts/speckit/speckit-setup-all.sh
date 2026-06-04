#!/usr/bin/env bash
set -euo pipefail

# Speckit bootstrap — installs the dotfiles-managed extension set and
# workflow definitions into a project using official `specify` commands.
#
# Usage:
#   speckit-setup-all.sh [project-dir]
#
# project-dir defaults to the current working directory.

PROJECT_DIR="${1:-.}"
PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EXTENSION_FILE="$SCRIPT_DIR/speckit-extensions.txt"
CATALOGS_FILE="$SCRIPT_DIR/speckit-catalogs.txt"
WORKFLOW_ROOT="$(cd "$SCRIPT_DIR/workflows" && pwd)"

if [ ! -d "$PROJECT_DIR/.specify" ]; then
    echo "Error: $PROJECT_DIR is not a speckit project (no .specify/ directory)" >&2
    exit 1
fi

if ! command -v specify >/dev/null 2>&1; then
    echo "Error: specify CLI not found on PATH" >&2
    exit 1
fi

if [ ! -f "$EXTENSION_FILE" ]; then
    echo "Error: extension list not found at $EXTENSION_FILE" >&2
    exit 1
fi

cd "$PROJECT_DIR"

echo "=== Speckit bootstrap: $PROJECT_DIR ==="

if [ -f "$CATALOGS_FILE" ]; then
    echo "Ensuring extension catalogs..."
    while IFS= read -r catalog || [ -n "$catalog" ]; do
        case "$catalog" in
            ''|\#*) continue ;;
        esac

        if [ -n "${SPECKIT_CATALOG_URL:-}" ] && [ "$SPECKIT_CATALOG_URL" = "$catalog" ]; then
            echo "  $catalog — catalog already configured via SPECKIT_CATALOG_URL"
            continue
        fi

        if [ -f .specify/extension-catalogs.yml ] && grep -Fq "$catalog" .specify/extension-catalogs.yml; then
            echo "  $catalog — catalog already configured"
            continue
        fi

        echo "  $catalog — adding catalog"
        specify extension catalog add --name community --install-allowed "$catalog"
    done < "$CATALOGS_FILE"
fi

echo "Installing required extensions..."

while IFS= read -r extension || [ -n "$extension" ]; do
    extension="${extension%%#*}"
    extension="$(printf '%s' "$extension" | xargs)"
    [ -n "$extension" ] || continue

    if [ -d ".specify/extensions/$extension" ]; then
        echo "  $extension — already installed"
        specify extension enable "$extension" >/dev/null 2>&1 || true
        continue
    fi

    echo "  $extension — installing"
    specify extension add "$extension"
    specify extension enable "$extension" >/dev/null 2>&1 || true
done < "$EXTENSION_FILE"

install_workflow() {
    local workflow_id="$1"
    local workflow_dir="$WORKFLOW_ROOT/$workflow_id"

    if [ ! -f "$workflow_dir/workflow.yml" ]; then
        echo "  WARN: workflow asset missing for $workflow_id at $workflow_dir" >&2
        return 0
    fi

    if [ -f ".specify/workflows/$workflow_id/workflow.yml" ]; then
        echo "  Replacing workflow $workflow_id..."
        specify workflow remove "$workflow_id" >/dev/null 2>&1 || true
    else
        echo "  Installing workflow $workflow_id..."
    fi

    specify workflow add "$workflow_dir"
}

install_workflow "speckit"
install_workflow "speckit-quality"
install_workflow "speckit-full"

echo ""
echo "Speckit bootstrap complete."
