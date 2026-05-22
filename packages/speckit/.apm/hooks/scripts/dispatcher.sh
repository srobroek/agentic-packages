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
case "$cmd" in speckit.*) ;; *) exit 0 ;; esac
id="${cmd#speckit.}"

node_file="$(cd "$(dirname "$0")/.." && pwd)/nodes/${id}.${phase}.md"
[ -f "$node_file" ] || exit 0
node_body="$(cat "$node_file")"

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
