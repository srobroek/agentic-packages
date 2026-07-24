#!/usr/bin/env bash
# per-agent-stop.sh — SubagentStop hook dispatcher for contract-holding agents.
#
# Wired per-agent (Claude: agent frontmatter hooks:; Codex: agent_type matcher).
# Delegates entirely to the shared rules-eval.sh evaluator in the beads package.
# This script is only the RULES_DIR → eval bridge; all evaluation logic lives
# in rules-eval.sh (spec 002, packages/beads/scripts/rules-eval.sh).
#
# RULES_DIR: rules files are co-deployed with this package under .apm/rules/.
# The deployed root is ${PLUGIN_ROOT} set by the APM runtime; we derive the
# rules dir from PLUGIN_ROOT or, fallback, from this script's own location.
#
# Portability: bash 3.2, BSD/GNU tolerant.
set -uo pipefail   # NOT -e: must fail open.

# Locate RULES_DIR.
_script_dir="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
_plugin_root="${PLUGIN_ROOT:-}"
if [ -n "$_plugin_root" ]; then
  _rules_dir="${_plugin_root}/.apm/rules"
else
  # Deployed layout: scripts/ is inside .apm/hooks/; rules/ is a sibling of hooks/ under .apm/.
  _rules_dir="${_script_dir}/../../rules"
fi

# Locate rules-eval.sh in the beads package (co-deployed via APM dependency).
# Beads package ships rules-eval.sh under scripts/. Two resolution strategies:
#   1. RULES_EVAL env override (testing / CI).
#   2. Walk from PLUGIN_ROOT to the deployed beads package (APM global layout).
_eval="${RULES_EVAL:-}"
if [ -z "$_eval" ]; then
  # Standard APM global deploy: ~/.claude/plugins/<pkg>/scripts/rules-eval.sh
  # From this package's PLUGIN_ROOT, sibling packages live at the same depth.
  if [ -n "$_plugin_root" ]; then
    _candidate="$(dirname "$_plugin_root")/agentic-packages-beads/scripts/rules-eval.sh"
    [ -f "$_candidate" ] && _eval="$_candidate"
  fi
fi
# Fallback: monorepo development layout — beads is 4 dirs up from .apm/hooks/scripts/.
if [ -z "$_eval" ]; then
  _candidate="${_script_dir}/../../../beads/scripts/rules-eval.sh"
  [ -f "$_candidate" ] && _eval="$_candidate"
fi

# If neither found, fail open.
if [ -z "$_eval" ] || [ ! -f "$_eval" ]; then
  printf '{}\n'
  exit 0
fi

# Pipe stdin to the evaluator with RULES_DIR pointed at this package's rules/.
exec env RULES_DIR="$_rules_dir" BD_BIN="${BD_BIN:-bd}" bash "$_eval"
