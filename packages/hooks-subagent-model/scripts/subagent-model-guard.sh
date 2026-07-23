#!/usr/bin/env bash
set -euo pipefail

# subagent-model-guard.sh — PreToolUse:Agent deny gate for Claude and Codex.
#
# Problem: the parent session often runs an expensive top-tier model. A spawn
# that omits `model` and names a subagent_type with no pinned model in its
# definition (a "general-purpose"-shaped agent) silently INHERITS the parent's
# model — burning the expensive model on work that a cheaper one could do.
#
# Codex policy: named semantic roles must resolve project-first, then globally,
# to a custom agent TOML that pins both model and model_reasoning_effort. A
# project profile deliberately shadows a same-named global profile, even when
# incomplete. Ad-hoc/default agents are denied by default because the hook
# cannot safely infer role instructions from task prose.
#
# Claude policy: preserve the existing explicit-model or pinned-agent gate.
#
# The inherit-by-default list is deliberately small and overridable per-project
# via SUBAGENT_MODEL_GUARD_INHERIT_TYPES (comma-separated) so a project can add
# its own unpinned custom agent types without waiting on a package release.
#
# Fail-open: missing jq, empty stdin, or malformed JSON all exit 0 with no
# output. A broken guard must never block all delegation.

command -v jq >/dev/null 2>&1 || exit 0

payload="$(cat 2>/dev/null || true)"
[[ -z "$payload" ]] && exit 0

tool=""
model=""
reasoning_effort=""
subagent_type=""
is_codex="false"
cwd=""
{
  IFS= read -r tool || true
  IFS= read -r model || true
  IFS= read -r reasoning_effort || true
  IFS= read -r subagent_type || true
  IFS= read -r is_codex || true
  IFS= read -r cwd || true
} < <(
  printf '%s' "$payload" | jq -r '
    (.tool_name // ""),
    (if (.tool_input|type)=="object" then (.tool_input.model // "") else "" end),
    (if (.tool_input|type)=="object" then (.tool_input.reasoning_effort // .tool_input.model_reasoning_effort // "") else "" end),
    (if (.tool_input|type)=="object" then (.tool_input.agent_type // .tool_input.subagent_type // "") else "" end),
    (if (.tool_input|type)=="object" then
      ((.tool_input | has("agent_type")) or (.tool_input | has("task_name")) or
       (.tool_input | has("fork_turns")) or (.tool_input | has("reasoning_effort")))
     else false end),
    (.cwd // "")
  ' 2>/dev/null
)

# Agent and Task are both observed as tool_name values for subagent spawns
# across harnesses; anything else is not a spawn this guard cares about.
case "$tool" in
  Agent|Task) ;;
  *) exit 0 ;;
esac

[[ "$subagent_type" == "null" ]] && subagent_type=""

deny() {
  jq -cn --arg reason "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}' 2>/dev/null || true
  exit 0
}

toml_string() {
  local path="$1" key="$2"
  local line rhs quote value remainder c escaped i

  # Agent profiles only need scalar metadata, so keep this parser bounded and
  # dependency-free while accepting TOML's basic/literal string delimiters.
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^[[:space:]]*${key}[[:space:]]*= ]] || continue

    rhs="${line#*=}"
    rhs="${rhs#"${rhs%%[![:space:]]*}"}"
    [[ -n "$rhs" ]] || continue
    quote="${rhs:0:1}"
    [[ "$quote" == '"' || "$quote" == "'" ]] || continue

    value=""
    escaped=0
    i=1
    while (( i < ${#rhs} )); do
      c="${rhs:$i:1}"
      if [[ "$quote" == '"' && "$escaped" == 1 ]]; then
        # Keep unknown escapes intact; profile identifiers only use the two
        # escapes that affect delimiter parsing, but valid TOML still passes.
        case "$c" in
          '"'|\\) value="${value}${c}" ;;
          *) value="${value}\\${c}" ;;
        esac
        escaped=0
      elif [[ "$quote" == '"' && "$c" == \\ ]]; then
        escaped=1
      elif [[ "$c" == "$quote" ]]; then
        remainder="${rhs:$((i + 1))}"
        remainder="${remainder#"${remainder%%[![:space:]]*}"}"
        [[ -z "$remainder" || "${remainder:0:1}" == "#" ]] || break
        printf '%s\n' "$value"
        return 0
      else
        value="${value}${c}"
      fi
      i=$((i + 1))
    done
  done < "$path"
  return 0
}

find_named_profile() {
  local directory="$1" wanted="$2" profile candidate
  [[ -d "$directory" ]] || return 1
  for profile in "$directory"/*.toml; do
    [[ -f "$profile" ]] || continue
    candidate="$(toml_string "$profile" name)"
    if [[ "$candidate" == "$wanted" ]]; then
      printf '%s\n' "$profile"
      return 0
    fi
  done
  return 1
}

find_codex_profile() {
  local wanted="$1" directory parent profile codex_home
  directory="$cwd"
  [[ -n "$directory" && -d "$directory" ]] || directory="$PWD"

  while [[ -n "$directory" ]]; do
    profile="$(find_named_profile "$directory/.codex/agents" "$wanted" || true)"
    if [[ -n "$profile" ]]; then
      printf '%s\n' "$profile"
      return 0
    fi
    [[ "$directory" == "/" ]] && break
    parent="${directory%/*}"
    [[ -n "$parent" ]] || parent="/"
    [[ "$parent" == "$directory" ]] && break
    directory="$parent"
  done

  codex_home="${CODEX_HOME:-${HOME}/.codex}"
  find_named_profile "$codex_home/agents" "$wanted"
}

# Enumerate every installed Codex agent profile reachable from cwd (project
# ancestry) plus CODEX_HOME/agents, deduplicating by name. Emits at most 12
# entries sorted alphabetically, one per line in the form
# "name (model/effort)" or just "name" when the profile lacks those fields.
# Pure bash — no declare -A, no nested functions, compatible with bash 3.2+.
list_installed_profiles() {
  local directory parent codex_home p profile_name model_val effort_val
  local seen_names raw_entries entry count

  seen_names=""   # newline-separated list of already-emitted names
  raw_entries=""  # collected "name\tentry" lines for sort+cap

  directory="$cwd"
  [[ -n "$directory" && -d "$directory" ]] || directory="$PWD"

  _collect_dir() {
    local dir="$1"
    [[ -d "$dir" ]] || return 0
    for p in "$dir"/*.toml; do
      [[ -f "$p" ]] || continue
      profile_name="$(toml_string "$p" name)"
      [[ -n "$profile_name" ]] || continue
      # Skip names already collected (project profiles shadow global ones).
      printf '%s\n' "$seen_names" | grep -qxF "$profile_name" && continue
      seen_names="${seen_names}${profile_name}
"
      model_val="$(toml_string "$p" model)"
      effort_val="$(toml_string "$p" model_reasoning_effort)"
      if [[ -n "$model_val" && -n "$effort_val" ]]; then
        raw_entries="${raw_entries}${profile_name}	${profile_name} (${model_val}/${effort_val})
"
      elif [[ -n "$model_val" ]]; then
        raw_entries="${raw_entries}${profile_name}	${profile_name} (${model_val})
"
      else
        raw_entries="${raw_entries}${profile_name}	${profile_name}
"
      fi
    done
  }

  while [[ -n "$directory" ]]; do
    _collect_dir "$directory/.codex/agents"
    [[ "$directory" == "/" ]] && break
    parent="${directory%/*}"
    [[ -n "$parent" ]] || parent="/"
    [[ "$parent" == "$directory" ]] && break
    directory="$parent"
  done

  codex_home="${CODEX_HOME:-${HOME}/.codex}"
  _collect_dir "$codex_home/agents"

  # Sort by name column and cap at 12; emit only the display column.
  count=0
  while IFS='	' read -r _ entry; do
    [ "$count" -ge 12 ] && break
    printf '%s\n' "$entry"
    count=$((count + 1))
  done < <(printf '%s' "$raw_entries" | sort)
}

if [[ "$is_codex" == "true" ]]; then
  if [[ -z "$subagent_type" || "$subagent_type" == "default" ]]; then
    if [[ "${SUBAGENT_MODEL_GUARD_ALLOW_AD_HOC:-0}" == "1" \
      && -n "$model" && "$model" != "null" \
      && -n "$reasoning_effort" && "$reasoning_effort" != "null" ]]; then
      exit 0
    fi
    # Build the catalog-driven deny message by enumerating installed profiles
    # so the recommendation reflects what the project actually has available.
    catalog_list="$(list_installed_profiles)"
    if [[ -n "$catalog_list" ]]; then
      deny "Codex agent selection blocked: choose a configured agent_type instead of default/ad-hoc delegation. Choose a configured agent_type from the installed catalog: $(printf '%s' "$catalog_list" | paste -sd ', ' -). Pick the profile whose role best matches the task. Each selected profile must pin both model and model_reasoning_effort."
    else
      deny "Codex agent selection blocked: choose a configured agent_type instead of default/ad-hoc delegation. No installed agent profiles were found. Define a project or global agent profile in .codex/agents/ that pins model and model_reasoning_effort, then retry with its name as agent_type."
    fi
  fi

  profile="$(find_codex_profile "$subagent_type" || true)"
  if [[ -z "$profile" ]]; then
    deny "Codex agent selection blocked: agent_type '$subagent_type' has no project or global custom profile. Choose an available semantic agent whose profile pins model and model_reasoning_effort; do not fall back to an inherited/default agent."
  fi

  profile_model="$(toml_string "$profile" model)"
  profile_effort="$(toml_string "$profile" model_reasoning_effort)"
  if [[ -z "$profile_model" || -z "$profile_effort" ]]; then
    deny "Codex agent selection blocked: '$profile' shadows lower-precedence profiles but does not pin both model and model_reasoning_effort. Regenerate it from its package agent-models.yml, then retry with the semantic agent_type."
  fi
  exit 0
fi

[[ -n "$model" && "$model" != "null" ]] && exit 0

# Agent types with no pinned `model:` field in their definition — an
# unspecified spawn rides whatever model the parent session is running.
inherit_types="${SUBAGENT_MODEL_GUARD_INHERIT_TYPES:-general-purpose,Explore,Plan,claude,fork}"

is_inherit_type() {
  local needle="$1" item
  local IFS=,
  for item in $inherit_types; do
    # trim surrounding whitespace so "a, b, c" style overrides still match
    item="${item#"${item%%[![:space:]]*}"}"
    item="${item%"${item##*[![:space:]]}"}"
    [[ "$item" == "$needle" ]] && return 0
  done
  return 1
}

if [[ -n "$subagent_type" ]] && ! is_inherit_type "$subagent_type"; then
  exit 0
fi

read -r -d '' reason <<'EOF' || true
This agent type inherits the session model. Re-issue the Agent call with an explicit model:
- haiku — mechanical work: CI watching/shepherding, log triage, batched gh/git operations, file sweeps, formatting
- sonnet — bounded coding, standard research, PR fix rounds, doc writing, test authoring
- opus or omit-after-deliberation — deep/adversarial research, architecture, cross-cutting synthesis, judge/verification passes (to inherit the top-tier session model intentionally, pass the session's model name explicitly)

Effort is not enforceable per-call (this hook cannot see a `tool_input.effort` field). For reusable agents, pin `effort:` in the agent definition frontmatter (low for mechanical lanes, high+ for verification/judge lanes). Workflow scripts may pass effort per agent() call.
EOF

deny "$reason"
