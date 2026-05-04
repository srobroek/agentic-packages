#!/usr/bin/env bash
set -euo pipefail

payload="$(cat || true)"
[ -z "$payload" ] && exit 0

script_dir="$(cd "$(dirname "$0")" && pwd)"
package_root="$(cd "$script_dir/../../.." && pwd)"
cwd="${PWD:-$(pwd)}"

allow_project_local=false
if [ -f "$cwd/apm.yml" ] && grep -Eq 'allow_project_local_agentic_assets:[[:space:]]*true' "$cwd/apm.yml"; then
  allow_project_local=true
fi

extract_paths() {
  printf '%s' "$payload" | jq -r '
    .tool_input.file_path?,
    .tool_input.path?,
    .tool_input.paths[]?,
    .tool_input.notebook_path?,
    .tool_input.edits[]?.file_path?,
    .tool_input.command?
    | select(type == "string")
  ' 2>/dev/null || true
}

blocked_regex='(^|/)(\.codex/(agents|hooks|plugins|skills)(/|$)|\.claude/(agents|commands|hooks|rules|skills)(/|$)|\.agents/skills(/|$)|dotfiles/dot_codex/(agents|hooks|plugins|private_rules)(/|$)|dotfiles/dot_codex/hooks\.json$|dotfiles/dot_codex/symlink_config\.toml$|dotfiles/external-managed/codex/(config\.toml|rules/)|dotfiles/dot_claude/(agents|commands|hooks|workflows)(/|$)|dotfiles/dot_claude/private_(managed-)?settings\.json\.tmpl$|dotfiles/\.chezmoitemplates/claude(/|$)|dotfiles/modify_dot_claude\.json\.tmpl$|dotfiles/external-managed/config/agentic-tools/(skills|hooks|steering|project-setup)(/|$))'

mcp_config_regex='(^|/)(\.codex/config\.toml|\.claude/settings[^/]*\.json|dotfiles/external-managed/codex/config\.toml|dotfiles/dot_claude/private_(managed-)?settings\.json\.tmpl)$'

blocked_hit=""
while IFS= read -r item; do
  [ -z "$item" ] && continue

  if printf '%s' "$item" | grep -Eq "$blocked_regex"; then
    blocked_hit="$item"
  elif printf '%s' "$item" | grep -Eq "$mcp_config_regex" && printf '%s' "$payload" | grep -Eq 'mcp_servers|mcpServers|"mcp"|\[mcp_servers'; then
    blocked_hit="$item"
  else
    continue
  fi

  case "$blocked_hit" in
    "$package_root"/*|"$package_root")
      blocked_hit=""
      continue
      ;;
  esac

  if $allow_project_local; then
    blocked_hit=""
    continue
  fi

  break
done < <(extract_paths)

if [ -n "$blocked_hit" ]; then
  cat >&2 <<MSG
Shared agentic assets are APM-managed. Edit the source in agentic-packages/.apm,
then reinstall/compile the package. Blocked target: $blocked_hit

If this is truly project-local, document it in apm.yml with:
  x-agentic:
    allow_project_local_agentic_assets: true
MSG
  exit 2
fi

exit 0
