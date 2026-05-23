#!/usr/bin/env bash
# SpecKit DAG dispatcher.
#
# Wired through .apm/hooks/speckit-{claude,codex}-hooks.json. Fires on:
#   Claude: UserPromptExpansion · PreToolUse:Skill · PostToolUse:Skill
#   Codex:  UserPromptSubmit · PreToolUse · PostToolUse
#
# Arguments: $1 = "pre" or "post" (phase).
#
# Pre  → reads nodes/<id>.pre.md  (Came from + Preconditions),
#        evaluates HARD-DEPRECATED / HARD-MISSING / HARD-EXISTS lines,
#        either blocks the invocation or injects the body as
#        additionalContext.
# Post → reads nodes/<id>.post.md (Going to + Postconditions +
#        Conditional branching), injects the body as additionalContext.
#
# No state file. <feat> placeholder resolves from the first hyphenated
# token in command_args / prompt body. Missing node files = silent
# no-op (graceful for new commands not yet documented).

set -euo pipefail

payload="$(cat || true)"
phase="${1:-pre}"

event=$(printf '%s' "$payload" | jq -r '.hook_event_name // empty' 2>/dev/null || true)

cmd=""
case "$event" in
  UserPromptExpansion)
    cmd=$(printf '%s' "$payload" | jq -r '.command_name // empty' 2>/dev/null || true)
    ;;
  PreToolUse|PostToolUse)
    cmd=$(printf '%s' "$payload" | jq -r '.tool_input.skill // .tool_input.command_name // empty' 2>/dev/null || true)
    if [ -z "$cmd" ]; then
      # Codex PreToolUse / PostToolUse may not carry a skill; try the
      # tool_input.prompt body instead.
      prompt=$(printf '%s' "$payload" | jq -r '.tool_input.prompt // empty' 2>/dev/null || true)
      cmd=$(printf '%s' "$prompt" | grep -oE '/speckit\.[a-z][a-z0-9.-]*' | head -1 | sed 's|^/||')
    fi
    ;;
  UserPromptSubmit)
    prompt=$(printf '%s' "$payload" | jq -r '.prompt // empty' 2>/dev/null || true)
    cmd=$(printf '%s' "$prompt" | grep -oE '/speckit\.[a-z][a-z0-9.-]*' | head -1 | sed 's|^/||')
    ;;
  *)
    exit 0
    ;;
esac

[ -n "$cmd" ] || exit 0
# Normalise: Claude Code skill names use hyphens (speckit-foo-bar),
# DAG node files use dots as segment separators but keep intra-segment
# hyphens (agent-assign.execute). We strip the "speckit-" prefix and
# match node files by converting their dots to hyphens for comparison.
raw="${cmd#speckit-}"
raw="${raw#speckit.}"
[ -n "$raw" ] || exit 0
raw="${raw//./-}"

# Locate the nodes/ directory. APM doesn't ship files alongside hook
# scripts by default, so the nodes/ tree usually lives in the APM
# cache at apm_modules/<owner>/<repo>/packages/speckit/.apm/hooks/nodes/.
# Resolution order:
#   1. SPECKIT_DAG_NODES_DIR env override (testing / custom layouts)
#   2. sibling ../nodes/ (in-repo development, or if APM later ships
#      them next to dispatcher.sh)
#   3. apm_modules cache discovery under $CLAUDE_PROJECT_DIR / cwd
nodes_dir=""
if [ -n "${SPECKIT_DAG_NODES_DIR:-}" ] && [ -d "$SPECKIT_DAG_NODES_DIR" ]; then
  nodes_dir="$SPECKIT_DAG_NODES_DIR"
elif [ -d "$(dirname "$0")/../nodes" ]; then
  nodes_dir="$(cd "$(dirname "$0")/.." && pwd)/nodes"
else
  for root in "${CLAUDE_PROJECT_DIR:-}" "$PWD"; do
    [ -n "$root" ] || continue
    [ -d "$root/apm_modules" ] || continue
    candidate=$(find "$root/apm_modules" -maxdepth 8 -path "*/packages/speckit/.apm/hooks/nodes" -type d 2>/dev/null | head -1)
    if [ -n "$candidate" ]; then
      nodes_dir="$candidate"
      break
    fi
  done
fi
[ -n "$nodes_dir" ] || exit 0

# Find the node file by normalising both sides to hyphens.
# Node file "agent-assign.execute.post.md" → stem "agent-assign.execute"
# → normalised "agent-assign-execute" which matches $raw.
node_file=""
for candidate in "$nodes_dir"/*."${phase}".md; do
  [ -f "$candidate" ] || continue
  stem="$(basename "$candidate" ".${phase}.md")"
  if [ "${stem//./-}" = "$raw" ]; then
    node_file="$candidate"
    break
  fi
done
[ -n "$node_file" ] || exit 0
node_body="$(cat "$node_file")"
id="${raw}"

# Resolve <feat> using SpecKit's canonical 3-tier priority (matches
# .specify/scripts/bash/common.sh::get_feature_paths):
#   1. SPECIFY_FEATURE_DIRECTORY env var
#   2. .specify/feature.json "feature_directory" (set by /speckit.specify)
#   3. git branch name prefix matching specs/<branch-stem>* (legacy fallback)
# If none resolve, <feat> stays empty and HARD-MISSING/HARD-EXISTS
# checks that reference it become no-ops. HARD-DEPRECATED still fires
# unconditionally.
proj_root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
feat=""

if [ -n "${SPECIFY_FEATURE_DIRECTORY:-}" ]; then
  feat="${SPECIFY_FEATURE_DIRECTORY#specs/}"
  feat="${feat%/}"
elif [ -f "$proj_root/.specify/feature.json" ]; then
  feature_dir=$(jq -r '.feature_directory // empty' "$proj_root/.specify/feature.json" 2>/dev/null || true)
  feat="${feature_dir#specs/}"
  feat="${feat%/}"
fi

# Tier 3: branch-name prefix lookup. Branch like "001-foo-bar" maps to specs/001-foo-bar/.
if [ -z "$feat" ] && [ -d "$proj_root/.git" ] || [ -f "$proj_root/.git" ]; then
  branch=$(git -C "$proj_root" rev-parse --abbrev-ref HEAD 2>/dev/null || true)
  if [ -n "$branch" ] && [ -d "$proj_root/specs/$branch" ]; then
    feat="$branch"
  fi
fi

if [ "$phase" = "pre" ]; then
  # Pre phase: evaluate hard blocks from HARD-* lines in the node body.
  block_reason=""
  while IFS= read -r line; do
    case "$line" in
      *"HARD-DEPRECATED:"*)
        block_reason="${line#*HARD-DEPRECATED: }"
        break
        ;;
      *"HARD-MISSING:"*)
        path_tmpl="${line#*HARD-MISSING: }"
        # Trim leading dash/space/backtick + trailing whitespace/backtick.
        path_tmpl=$(printf '%s' "$path_tmpl" | sed -E 's/^[`[:space:]-]+//; s/[`[:space:]]+$//')
        path="${path_tmpl//<feat>/$feat}"
        if [ -n "$feat" ] && [ ! -e "$path" ]; then
          block_reason="Required artefact missing: $path"
          break
        fi
        ;;
      *"HARD-EXISTS:"*)
        path_tmpl="${line#*HARD-EXISTS: }"
        path_tmpl=$(printf '%s' "$path_tmpl" | sed -E 's/^[`[:space:]-]+//; s/[`[:space:]]+$//')
        path="${path_tmpl//<feat>/$feat}"
        if [ -n "$feat" ] && [ -e "$path" ]; then
          block_reason="Conflicting artefact present: $path — use /speckit.refine.update to amend instead of re-running this step"
          break
        fi
        ;;
    esac
  done <<< "$node_body"

  if [ -n "$block_reason" ]; then
    case "$event" in
      UserPromptExpansion)
        jq -n --arg m "$block_reason" --arg c "$node_body" '{
          decision: "block",
          reason: $m,
          hookSpecificOutput: {
            hookEventName: "UserPromptExpansion",
            additionalContext: $c
          }
        }'
        ;;
      UserPromptSubmit)
        jq -n --arg m "$block_reason" --arg c "$node_body" '{
          decision: "block",
          reason: $m,
          hookSpecificOutput: {
            hookEventName: "UserPromptSubmit",
            additionalContext: $c
          }
        }'
        ;;
      PreToolUse)
        jq -n --arg m "$block_reason" --arg c "$node_body" '{
          hookSpecificOutput: {
            hookEventName: "PreToolUse",
            permissionDecision: "deny",
            permissionDecisionReason: $m,
            additionalContext: $c
          }
        }'
        ;;
    esac
    exit 0
  fi
fi

# Soft injection: pre passes without block, OR post phase always.
jq -n --arg c "$node_body" --arg ev "$event" '{
  hookSpecificOutput: {
    hookEventName: $ev,
    additionalContext: $c
  }
}'
