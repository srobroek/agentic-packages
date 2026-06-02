#!/usr/bin/env bash
# Bootstrap a SpecKit project: scaffold .specify/, register the community
# extension catalog, install + enable the required extension set, and install
# the workflow definitions. Idempotent -- safe to re-run.
#
# Prereqs: `specify` CLI on PATH (uv tool install specify-cli) and `apm`.
# The APM speckit orchestration bundle (agents, DAG, hooks) is installed
# separately via `apm install speckit@<marketplace>`; this script wires the
# upstream spec-kit side that the bundle's DAG keys off.
#
# Usage: setup-speckit.sh [--integration <name>] [--script <sh|ps>] [--force]
#   --integration   coding-agent integration for `specify init` (default: codex)
#   --script        script flavor for `specify init` (default: sh)
#   --force         pass --force to `specify init` (skip dir-not-empty prompt)

set -euo pipefail

INTEGRATION="codex"
SCRIPT_FLAVOR="sh"
FORCE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --integration) INTEGRATION="${2:?--integration needs a value}"; shift 2 ;;
    --script)      SCRIPT_FLAVOR="${2:?--script needs a value}"; shift 2 ;;
    --force)       FORCE="--force"; shift ;;
    -h|--help)     sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

CATALOG_NAME="community"
CATALOG_URL="https://raw.githubusercontent.com/github/spec-kit/main/extensions/catalog.community.json"

# The required extension set the DAG depends on. Keep in sync with the README
# "Setting up a SpecKit project" list and the speckit-dag node coverage.
EXTENSIONS=(
  archive brownfield bugfix checkpoint cleanup conduct critique diagram doctor
  fix-findings fleet github-issues iterate onboard optimize qa reconcile refine
  retro review security-review status tinyspec verify verify-tasks worktree
)

# Workflow definitions (multi-step command bundles) shipped by spec-kit.
WORKFLOWS=(speckit speckit-quality speckit-full)

need() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: '$1' not found on PATH" >&2; exit 1; }; }
need specify

echo "==> 1/4 specify init (.specify/ scaffold) -- integration=$INTEGRATION script=$SCRIPT_FLAVOR"
if [ -d .specify ] && [ -z "$FORCE" ]; then
  echo "    .specify/ already present -- skipping init (pass --force to re-run)"
else
  # stdin from /dev/null so the post-init "Agent Folder Security" prompt and any
  # other interactive confirmations resolve to their non-interactive default
  # instead of blocking (or aborting under set -e).
  specify init --here --integration "$INTEGRATION" --script "$SCRIPT_FLAVOR" $FORCE </dev/null
fi

echo "==> 2/4 register community extension catalog"
# Match on URL, not just name: a default catalog (e.g. 'custom' from
# SPECKIT_CATALOG_URL) may already point at this community URL.
catalogs="$(specify extension catalog list 2>/dev/null || true)"
if printf '%s\n' "$catalogs" | grep -qF "$CATALOG_URL"; then
  echo "    a catalog for this URL is already registered -- skipping"
elif printf '%s\n' "$catalogs" | grep -qw "$CATALOG_NAME"; then
  echo "    catalog '$CATALOG_NAME' already registered -- skipping"
else
  specify extension catalog add --name "$CATALOG_NAME" --install-allowed "$CATALOG_URL" </dev/null
fi

echo "==> 3/4 install + enable ${#EXTENSIONS[@]} extensions"
installed="$(specify extension list 2>/dev/null || true)"
for ext in "${EXTENSIONS[@]}"; do
  if printf '%s\n' "$installed" | grep -qw "$ext"; then
    echo "    = $ext (already installed)"
  else
    echo "    + $ext"
    specify extension add "$ext" </dev/null
  fi
  specify extension enable "$ext" </dev/null >/dev/null 2>&1 || true
done

echo "==> 4/4 install workflow definitions: ${WORKFLOWS[*]}"
for wf in "${WORKFLOWS[@]}"; do
  if specify extension add "$wf" </dev/null >/dev/null 2>&1; then
    echo "    + $wf"
  else
    echo "    = $wf (present or bundled)"
  fi
done

echo ""
echo "==> SpecKit setup complete."
echo "    Next: ensure the APM speckit bundle is installed for the orchestration"
echo "    layer (agents + DAG hooks):"
echo "      apm install speckit@<marketplace> --target claude,codex,agent-skills"
echo "      apm compile --target codex,claude --no-constitution"
echo "    Then start the workflow with /speckit.specify."
