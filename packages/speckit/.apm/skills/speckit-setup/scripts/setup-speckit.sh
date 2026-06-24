#!/usr/bin/env bash
# Bootstrap a SpecKit project: scaffold .specify/, register the community
# extension catalog, install + enable the required extension set, register their
# command files for the requested integration, and install the workflow
# definitions. Idempotent -- safe to re-run.
#
# This is the single source of truth for the spec-kit side of SpecKit setup.
# The global `project-setup` skill delegates here (after `apm install speckit`)
# rather than carrying its own copy.
#
# Prereqs: `specify` CLI on PATH (uv tool install specify-cli).
# The APM speckit orchestration bundle (agents, DAG, hooks) carries this script;
# the bundle's DAG keys off the `.specify/` scaffold this produces.
#
# Usage: setup-speckit.sh [--integration <name>] [--script <sh|ps>] [--force]
#   --integration   coding-agent integration for `specify init` (default: codex)
#   --script        script flavor for `specify init` (default: sh)
#   --force         pass --force to `specify init` (skip dir-not-empty prompt)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKFLOW_ROOT="$SCRIPT_DIR/workflows"

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
# agent-assign is mandatory: steering routes implementation through the
# agent-assign flow and the DAG hard-blocks the deprecated /speckit.implement.
#
# Entries are either a bare extension name (resolved from the community catalog)
# or `name=source-url` for first-party extensions not (yet) in the catalog, which
# install via `specify extension add --from <url>`. Custom-source installs are
# best-effort: an unreachable/unpublished source warns and is skipped rather than
# aborting setup. One list, one source of truth; bash 3.2-safe (no associative arrays).
#   roadmap -- the spec-roadmap extension, from srobroek/speckit-roadmap.
EXTENSIONS=(
  agent-assign
  archive brownfield bugfix checkpoint cleanup conduct critique diagram doctor
  fix-findings fleet github-issues iterate memory-md onboard optimize qa reconcile
  refine retro review security-review status tinyspec verify verify-tasks worktree
  roadmap=https://github.com/srobroek/speckit-roadmap
)

# Workflow definitions, installed via the `workflow` primitive (since spec-kit
# 0.11.x workflows are a first-class primitive, NOT extensions -- they do not
# resolve through `extension add`). All three ship in this package under
# workflows/<id>/workflow.yml and are installed from those local dirs:
#   speckit          -- our gated override of the upstream Full SDD Cycle
#   speckit-quality  -- post-implementation QA cycle
#   speckit-full     -- spec -> implement -> QA in one run
WORKFLOWS=(speckit speckit-quality speckit-full)

need() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: '$1' not found on PATH" >&2; exit 1; }; }
need specify

echo "==> 1/5 specify init (.specify/ scaffold) -- integration=$INTEGRATION script=$SCRIPT_FLAVOR"
if [ -d .specify ] && [ -z "$FORCE" ]; then
  echo "    .specify/ already present -- skipping init (pass --force to re-run)"
else
  # stdin from /dev/null so the post-init "Agent Folder Security" prompt and any
  # other interactive confirmations resolve to their non-interactive default
  # instead of blocking (or aborting under set -e).
  specify init --here --integration "$INTEGRATION" --script "$SCRIPT_FLAVOR" $FORCE </dev/null
fi

echo "==> 2/5 register community extension catalog"
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

echo "==> 3/5 install + enable ${#EXTENSIONS[@]} extensions"
installed="$(specify extension list 2>/dev/null || true)"
for entry in "${EXTENSIONS[@]}"; do
  # Split "name=source" (custom source) from a bare "name" (community catalog).
  ext="${entry%%=*}"
  src="${entry#*=}"
  [ "$src" = "$entry" ] && src=""   # no '=' present -> no custom source
  if printf '%s\n' "$installed" | grep -qw "$ext"; then
    echo "    = $ext (already installed)"
  elif [ -n "$src" ]; then
    # Custom-source extension (not in the community catalog). Best-effort:
    # an unreachable/unpublished source warns and continues, leaving the rest
    # of the required catalog set intact.
    echo "    + $ext (from $src)"
    if ! specify extension add --from "$src" </dev/null; then
      echo "    WARNING: could not install '$ext' from $src -- skipping (publish it or check access)" >&2
      continue
    fi
  else
    echo "    + $ext"
    specify extension add "$ext" </dev/null
  fi
  specify extension enable "$ext" </dev/null >/dev/null 2>&1 || true
done

echo "==> 4/5 register extension commands for integration=$INTEGRATION"
# `specify extension add` only renders an extension's command files for the
# integration that is ACTIVE at add-time, and `specify integration switch`
# re-registers all installed+enabled extensions ONLY on a genuine switch
# (switching to the already-active integration is a no-op). So if extensions were
# added under a different integration than the one now requested (e.g. the
# default `codex` init, then later using `claude`), their command files are never
# rendered for the requested agent -- and re-running this script does not fix it,
# because the extensions are already "installed" and the install loop skips them.
# Force a (re-)registration of every enabled extension for "$INTEGRATION":
#   - requested integration is NOT active -> one genuine switch re-registers all.
#   - requested integration IS active     -> bounce through another built-in
#     integration and back to force re-registration (switch-to-self is a no-op).
# Switching built-in integrations (claude/codex) is offline; only the local
# extension registry is read to re-render command files.
current_integration="$(
  grep -o '"default_integration"[[:space:]]*:[[:space:]]*"[^"]*"' .specify/integration.json 2>/dev/null \
    | sed 's/.*"\([^"]*\)".*/\1/' | head -n1
)"
if [ -n "$current_integration" ] && [ "$current_integration" != "$INTEGRATION" ]; then
  specify integration switch "$INTEGRATION" </dev/null
  echo "    switched $current_integration -> $INTEGRATION (extensions re-registered)"
else
  if [ "$INTEGRATION" = "codex" ]; then BOUNCE="claude"; else BOUNCE="codex"; fi
  echo "    $INTEGRATION already active -- bouncing via $BOUNCE to force re-registration"
  # Disable -e around the bounce so a mid-bounce failure cannot leave the project
  # stranded on the bounce integration; always attempt to land back on "$INTEGRATION".
  set +e
  specify integration switch "$BOUNCE" </dev/null && specify integration switch "$INTEGRATION" </dev/null
  bounce_rc=$?
  set -e
  if [ "$bounce_rc" -ne 0 ]; then
    echo "    WARNING: re-registration bounce failed; ensuring active integration is $INTEGRATION" >&2
    specify integration switch "$INTEGRATION" </dev/null || true
  fi
fi

echo "==> 5/5 install workflow definitions from local dirs: ${WORKFLOWS[*]}"
for wf in "${WORKFLOWS[@]}"; do
  wf_dir="$WORKFLOW_ROOT/$wf"
  if [ ! -f "$wf_dir/workflow.yml" ]; then
    echo "    WARN: workflow asset missing for $wf at $wf_dir -- skipping" >&2
    continue
  fi
  # Replace any existing definition so our opinionated overrides win over the
  # version spec-kit bundles at init (e.g. the upstream `speckit` workflow).
  if specify workflow list 2>/dev/null | grep -qw "$wf"; then
    echo "    ~ $wf (replacing existing)"
    specify workflow remove "$wf" </dev/null >/dev/null 2>&1 || true
  else
    echo "    + $wf"
  fi
  specify workflow add "$wf_dir" </dev/null
done

echo ""
echo "==> SpecKit setup complete."
echo "    The speckit orchestration layer (agents + DAG hooks) ships in the same"
echo "    package as this script. If steering is not yet compiled, run:"
echo "      apm compile --target codex,claude --no-constitution"
echo "    Then start the workflow with /speckit.specify."
