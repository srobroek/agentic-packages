#!/usr/bin/env bash
set -euo pipefail

input="$(cat)"

git rev-parse --git-dir &>/dev/null || exit 0

is_main_branch() {
  local branch_name="$1"
  [[ "$branch_name" == "main" || "$branch_name" == "master" || "$branch_name" == "develop" ]]
}

detect_active_feature_worktree() {
  local current_pwd
  current_pwd="$(pwd)"
  local worktree_data
  worktree_data="$(git worktree list --porcelain 2>/dev/null || true)"
  [[ -n "$worktree_data" ]] || return 1

  local worktree_path=""
  local worktree_branch=""
  local candidate_count=0
  local candidate_path=""
  local candidate_branch=""
  local candidate_dirty=""

  while IFS= read -r line; do
    if [[ "$line" == worktree\ * ]]; then
      worktree_path="${line#worktree }"
      worktree_branch=""
      continue
    fi

    if [[ "$line" == branch\ refs/heads/* ]]; then
      worktree_branch="${line#branch refs/heads/}"

      if [[ "$worktree_path" != "$current_pwd" ]] && [[ -n "$worktree_branch" ]] && ! is_main_branch "$worktree_branch"; then
        candidate_count=$((candidate_count + 1))
        candidate_path="$worktree_path"
        candidate_branch="$worktree_branch"

        if [[ -n "$(git -C "$worktree_path" status --porcelain 2>/dev/null)" ]]; then
          candidate_dirty="dirty"
        else
          candidate_dirty="clean"
        fi
      fi
    fi
  done <<< "$worktree_data"

  if [[ "$candidate_count" -eq 1 ]]; then
    printf '%s\t%s\t%s\n' "$candidate_branch" "$candidate_path" "$candidate_dirty"
    return 0
  fi

  return 1
}

list_feature_worktrees() {
  local current_pwd
  current_pwd="$(pwd)"
  local worktree_data
  worktree_data="$(git worktree list --porcelain 2>/dev/null || true)"
  [[ -n "$worktree_data" ]] || return 1

  local worktree_path=""
  local worktree_branch=""
  local found_any=false

  while IFS= read -r line; do
    if [[ "$line" == worktree\ * ]]; then
      worktree_path="${line#worktree }"
      worktree_branch=""
      continue
    fi

    if [[ "$line" == branch\ refs/heads/* ]]; then
      worktree_branch="${line#branch refs/heads/}"

      if [[ "$worktree_path" != "$current_pwd" ]] && [[ -n "$worktree_branch" ]] && ! is_main_branch "$worktree_branch"; then
        found_any=true

        local worktree_dirty="clean"
        if [[ -n "$(git -C "$worktree_path" status --porcelain 2>/dev/null)" ]]; then
          worktree_dirty="dirty"
        fi

        printf '%s\t%s\t%s\n' "$worktree_branch" "$worktree_path" "$worktree_dirty"
      fi
    fi
  done <<< "$worktree_data"

  [[ "$found_any" == true ]]
}

prompt_matches_branch() {
  local branch_name="$1"
  local lowered_prompt="$2"
  local branch_keywords
  branch_keywords="$(printf '%s' "$branch_name" | sed 's/^[a-z]*\///' | tr '-' ' ' | tr '_' ' ' | tr '[:upper:]' '[:lower:]')"

  for keyword in $branch_keywords; do
    if [[ ${#keyword} -gt 2 ]] && printf '%s' "$lowered_prompt" | grep -q "$keyword"; then
      return 0
    fi
  done

  return 1
}

user_prompt="$(printf '%s' "$input" | jq -r '.prompt // empty' 2>/dev/null || true)"
if [[ -z "$user_prompt" || ${#user_prompt} -lt 10 ]]; then
  exit 0
fi

prompt_lower="$(printf '%s' "$user_prompt" | tr '[:upper:]' '[:lower:]')"

if printf '%s' "$prompt_lower" | grep -qE '^(what|how|why|where|when|which|who|explain|show|find|list|describe|tell|can you|does|is there|are there)'; then
  exit 0
fi

if printf '%s' "$prompt_lower" | grep -qE '(commit|push|pull|merge|rebase|checkout|branch|stash|cherry-pick|/quick-commit|/commit)'; then
  exit 0
fi

if printf '%s' "$prompt_lower" | grep -qE '^(next|continue|resume|proceed|go ahead|carry on)\b'; then
  exit 0
fi

current_branch="$(git branch --show-current 2>/dev/null)"
is_main=false

if is_main_branch "$current_branch"; then
  is_main=true
fi

uncommitted="$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
feature_branches="$(git branch --list 2>/dev/null | grep -v -E '^\*?\s*(main|master|develop)$' | tr -d ' *' | head -5 | tr '\n' ' ')"

if [[ "$is_main" == true ]]; then
  if active_worktree="$(detect_active_feature_worktree)"; then
    active_branch="$(printf '%s' "$active_worktree" | cut -f1)"
    active_path="$(printf '%s' "$active_worktree" | cut -f2)"
    active_dirty="$(printf '%s' "$active_worktree" | cut -f3)"
    if prompt_matches_branch "$active_branch" "$prompt_lower"; then
      context="WORKTREE_CONTEXT: protected '$current_branch'; likely worktree '$active_branch' ($active_dirty). Use it only if the request is for that branch."
    else
      context="WORKTREE_CONTEXT: protected '$current_branch'; feature worktree '$active_branch' exists ($active_dirty). Stay on '$current_branch' unless the request clearly names that branch."
    fi

    jq -n --arg ctx "$context" '{
      hookSpecificOutput: {
        hookEventName: "UserPromptSubmit",
        additionalContext: $ctx
      }
    }'
    exit 0
  fi

  if feature_worktrees="$(list_feature_worktrees)"; then
    worktree_lines="$(printf '%s\n' "$feature_worktrees" | awk -F '\t' '{printf "%s (%s), ", $1, $3}' | sed 's/, $//')"
    context="WORKTREE_CONTEXT: protected '$current_branch'; feature worktrees: $worktree_lines. Stay here unless the request clearly names one; run git worktree list for paths if needed."

    jq -n --arg ctx "$context" '{
      hookSpecificOutput: {
        hookEventName: "UserPromptSubmit",
        additionalContext: $ctx
      }
    }'
    exit 0
  fi

  context="BRANCH_WARNING: You're on '$current_branch' (protected branch).

Before making changes, consider creating a feature branch:
- git checkout -b feat/<description>
- git checkout -b fix/<description>

Existing branches: $feature_branches
Uncommitted files: $uncommitted"

  jq -n --arg ctx "$context" '{
    hookSpecificOutput: {
      hookEventName: "UserPromptSubmit",
      additionalContext: $ctx
    }
  }'
  exit 0
fi

cooldown_dir="/tmp/codex-branch-hooks"
mkdir -p "$cooldown_dir"
cache_file="$cooldown_dir/branch-check-$(pwd | md5 2>/dev/null || echo "$(pwd)" | md5sum | cut -d" " -f1)"

if [[ -f "$cache_file" ]]; then
  last_time="$(cat "$cache_file")"
  now="$(date +%s)"
  diff="$((now - last_time))"
  if [[ "$diff" -lt 60 ]]; then
    exit 0
  fi
fi
date +%s > "$cache_file"

match_found=false
if prompt_matches_branch "$current_branch" "$prompt_lower"; then
  match_found=true
fi

if [[ "$match_found" == true ]]; then
  exit 0
fi

feature_prefix="$(printf '%s' "$current_branch" | grep -oE '^[0-9]+' || true)"
if [[ -n "$feature_prefix" ]] && printf '%s' "$prompt_lower" | grep -q "$feature_prefix"; then
  exit 0
fi

is_complex=false
if printf '%s' "$prompt_lower" | grep -qE '\b(implement|add|create|build|refactor|fix|update|change|modify|remove|delete|integrate|migrate|convert|rewrite)\b'; then
  if [[ ${#user_prompt} -gt 50 ]]; then
    is_complex=true
  fi
fi

if printf '%s' "$prompt_lower" | grep -qE '(^[0-9]+\.|, and |; |then )'; then
  is_complex=true
fi

if printf '%s' "$prompt_lower" | grep -qE '\b(feature|functionality|component|module|system|service|api|endpoint|handler|controller|model|view)\b'; then
  is_complex=true
fi

if [[ "$is_complex" == true ]]; then
  context="BRANCH_CONTEXT: Current branch '$current_branch' does not obviously match the request.

Request: ${user_prompt:0:80}...

If the request clearly belongs to this branch, continue without asking.
Ask only if the branch/worktree is genuinely ambiguous or switching would be safer.

Existing feature branches: $feature_branches
Uncommitted files: $uncommitted"

  jq -n --arg ctx "$context" '{
    hookSpecificOutput: {
      hookEventName: "UserPromptSubmit",
      additionalContext: $ctx
    }
  }'
fi
