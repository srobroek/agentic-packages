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

is_read_only_shell_command() {
  local command="$1"

  # Shell payloads are command strings, not file edits. A command that only
  # READS a managed asset (list a skill dir, cat a hook, run an installed skill
  # script) must not be blocked -- the guard exists to stop the agent from
  # MUTATING managed assets, not from inspecting or invoking them. We prove a
  # command is read-only by requiring EVERY pipeline/list segment to lead with a
  # known reader; anything unproven is blocked. Editing still fails through the
  # write tools and the mutating-shell rejects below.
  #
  # BSD-sed / bash-3.2 safe: no GNU-only \n-in-replacement, no process
  # substitution in the splitter.

  # 1. Command or process substitution can run anything ($(...), `...`, <(...),
  #    >(...)) -- we cannot prove the outer command is a reader, so reject.
  #    Parameter expansion ($VAR, ${VAR}) is fine and intentionally NOT matched.
  if printf '%s' "$command" | grep -Eq '\$\(|`|<\(|>\('; then
    return 1
  fi

  # 2. Strip harmless fd plumbing (2>&1, >&2, redirects to /dev/null) so it does
  #    not read as a write or split a segment, then reject any surviving > / >>:
  #    a real write redirection to a file.
  local sanitized
  sanitized="$(printf '%s' "$command" \
    | sed -E 's#&>[[:space:]]*/dev/null##g' \
    | sed -E 's#[0-9]*>>?[[:space:]]*/dev/null##g' \
    | sed -E 's/[0-9]*>&[0-9]//g')"
  if printf '%s' "$sanitized" | grep -Eq '>>?'; then
    return 1
  fi

  # 3. In-place sed rewrites file content.
  if printf '%s' "$command" | grep -Eq '(^|[[:space:]])sed[[:space:]].*(-i|--in-place)([[:space:]]|=|$)'; then
    return 1
  fi

  # 4. find with an action primary can execute or delete -- not read-only.
  if printf '%s' "$command" | grep -Eq '(^|[[:space:]])find([[:space:]]|$)' \
     && printf '%s' "$command" | grep -Eq '[[:space:]]-(exec|execdir|ok|okdir|delete|fprint|fprintf|fls|fput)([[:space:]]|$)'; then
    return 1
  fi

  # 5. Every segment (split on | ; & && ||) must lead with a known reader. &&/||
  #    become two adjacent delimiters -> an empty middle segment, which is
  #    skipped, so a single tr on |;& covers the two-char operators too.
  local seg first normalized
  normalized="$(printf '%s' "$sanitized" | tr '|;&' '\n')"
  while IFS= read -r seg; do
    # Trim leading whitespace, an optional `env` prefix, and any VAR=val prefixes.
    seg="$(printf '%s' "$seg" | sed -E 's/^[[:space:]]+//; s/^env[[:space:]]+//; s/^([A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*[[:space:]]+)*//')"
    [ -z "$seg" ] && continue
    first="$(printf '%s' "$seg" | sed -E 's/[[:space:]].*$//')"
    first="${first##*/}"  # /usr/bin/grep -> grep
    case "$first" in
      cat|sed|head|tail|less|more|bat|rg|grep|egrep|fgrep|fd|find|ls|eza|tree|wc|jq|yq|stat|file|pwd|realpath|readlink|echo|printf|test|\[|true|false|dirname|basename|sort|uniq|cut|column|diff|comm)
        continue
        ;;
      python|python[0-9]|python[0-9].[0-9]|python[0-9].[0-9][0-9]|node|bash|sh)
        # Interpreters are allowed only when RUNNING A SCRIPT FILE -- never
        # inline code (-c/-e/--command) or stdin (a bare `-`). Invoking an
        # installed skill/tool script is the intended read path; `bash -c 'rm …'`
        # is not.
        if printf '%s' "$seg" | grep -Eq '(^|[[:space:]])--?(c|e|command)([[:space:]]|=|$)|(^|[[:space:]])-([[:space:]]|$)'; then
          return 1
        fi
        continue
        ;;
    esac
    return 1
  done <<EOF
$normalized
EOF

  return 0
}

blocked_regex='(^|/)(\.codex/(agents|hooks|plugins|skills)(/|$|[[:space:]])|\.claude/(agents|commands|hooks|rules|skills)(/|$|[[:space:]])|\.agents/skills(/|$|[[:space:]])|dotfiles/dot_codex/(agents|hooks|plugins|private_rules)(/|$|[[:space:]])|dotfiles/dot_codex/hooks\.json$|dotfiles/dot_codex/symlink_config\.toml$|dotfiles/external-managed/codex/(config\.toml|rules/)|dotfiles/dot_claude/(agents|commands|hooks|workflows)(/|$|[[:space:]])|dotfiles/dot_claude/private_(managed-)?settings\.json\.tmpl$|dotfiles/\.chezmoitemplates/claude(/|$|[[:space:]])|dotfiles/modify_dot_claude\.json\.tmpl$|dotfiles/external-managed/config/agentic-tools/(skills|hooks|steering|project-setup)(/|$|[[:space:]]))'

mcp_config_regex='(^|/)(\.codex/config\.toml|\.claude/settings[^/]*\.json|dotfiles/external-managed/codex/config\.toml|dotfiles/dot_claude/private_(managed-)?settings\.json\.tmpl)$'

shell_command="$(printf '%s' "$payload" | jq -r '.tool_input.command? // empty' 2>/dev/null || true)"
if [ -n "$shell_command" ] && is_read_only_shell_command "$shell_command"; then
  exit 0
fi

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
