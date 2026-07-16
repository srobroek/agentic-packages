#!/usr/bin/env bash
set -euo pipefail

payload="$(cat 2>/dev/null || true)"
command -v jq >/dev/null 2>&1 || exit 0

cwd="$(printf '%s' "$payload" | jq -r '.cwd // empty' 2>/dev/null || true)"
[[ -n "$cwd" && "$cwd" != "null" && -d "$cwd" ]] || cwd="$PWD"

repo_root="$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null || true)"
[[ -n "$repo_root" ]] || exit 0
cd "$repo_root"

selected_file=".agents/hooks/quality-languages"
selected=""
if [[ -f "$selected_file" ]]; then
  selected="$(tr '\n' ' ' < "$selected_file" | tr ',' ' ')"
elif [[ -n "${AGENTIC_QUALITY_LANGS:-}" ]]; then
  selected="${AGENTIC_QUALITY_LANGS//,/ }"
else
  [[ -f go.mod ]] && selected="$selected go"
  [[ -f pyproject.toml ]] && selected="$selected python"
  [[ -f Cargo.toml ]] && selected="$selected rust"
  [[ -f package.json ]] && selected="$selected ts"
fi
[[ -n "${selected// }" ]] || exit 0

has_lang() {
  local wanted="$1"
  printf ' %s ' "$selected" | grep -Eq " (all|$wanted) "
}

lang_for_file() {
  local file="$1"
  case "$file" in
    *.go) has_lang go && printf 'go' ;;
    *.py|*.pyi) has_lang python && printf 'python' ;;
    *.rs|Cargo.toml) has_lang rust && printf 'rust' ;;
    *.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs|*.vue|*.svelte)
      if has_lang ts || has_lang typescript || has_lang javascript; then
        printf 'ts'
      fi
      ;;
  esac
}

tool="$(printf '%s' "$payload" | jq -r '.tool_name // .tool // empty' 2>/dev/null || true)"
patch_text=""
file_path="$(printf '%s' "$payload" | jq -r '.tool_input.file_path // .tool_input.path // empty' 2>/dev/null || true)"

case "$tool" in
  apply_patch|functions.apply_patch)
    patch_text="$(printf '%s' "$payload" | jq -r '
      if (.tool_input | type) == "string" then
        .tool_input
      else
        .tool_input.command // .tool_input.patch // .tool_input.input // .input // empty
      end
    ' 2>/dev/null || true)"
    ;;
esac

tmp_files="$(mktemp)"
trap 'rm -f "$tmp_files"' EXIT

if [[ -n "$patch_text" && "$patch_text" != "null" ]]; then
  printf '%s\n' "$patch_text" |
    sed -nE 's/^\*\*\* (Update|Add) File: (.*)$/\2/p' >> "$tmp_files"
elif [[ -n "$file_path" && "$file_path" != "null" ]]; then
  printf '%s\n' "$file_path" >> "$tmp_files"
fi

edited_files=()
while IFS= read -r l; do
  [[ -n "$l" ]] && edited_files+=("$l")
done < <(
  while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    lang="$(lang_for_file "$file")"
    [[ -n "$lang" ]] || continue
    printf '%s\n' "$file"
  done < "$tmp_files" | sort -u
)

[[ "${#edited_files[@]}" -gt 0 ]] || exit 0

changed_lines=0
if [[ -n "$patch_text" && "$patch_text" != "null" ]]; then
  changed_lines="$(printf '%s\n' "$patch_text" | grep -Ec '^[-+][^-+]' || true)"
else
  content="$(printf '%s' "$payload" | jq -r '
    .tool_input.content //
    .tool_input.new_string //
    ([.tool_input.edits[]?.new_string] | join("\n")) //
    empty
  ' 2>/dev/null || true)"
  if [[ -n "$content" && "$content" != "null" ]]; then
    changed_lines="$(printf '%s\n' "$content" | wc -l | tr -d ' ')"
  else
    changed_lines=$(( ${#edited_files[@]} * 20 ))
  fi
fi

repo_hash="$(printf '%s' "$repo_root" | md5sum 2>/dev/null | awk '{print $1}' || true)"
[[ -n "$repo_hash" ]] || repo_hash="$(printf '%s' "$repo_root" | md5 -q 2>/dev/null || true)"
[[ -n "$repo_hash" ]] || exit 0

state_dir="/tmp/agentic-quality-advisory-$repo_hash"
mkdir -p "$state_dir"
files_state="$state_dir/files"
lines_state="$state_dir/lines"
last_advice="$state_dir/last-advice"

touch "$files_state"
printf '%s\n' "${edited_files[@]}" >> "$files_state"
sort -u "$files_state" -o "$files_state"

previous_lines=0
if [[ -f "$lines_state" ]]; then
  previous_lines="$(cat "$lines_state" 2>/dev/null || echo 0)"
fi
[[ "$previous_lines" =~ ^[0-9]+$ ]] || previous_lines=0
total_lines=$(( previous_lines + changed_lines ))
printf '%s\n' "$total_lines" > "$lines_state"

file_count="$(wc -l < "$files_state" | tr -d ' ')"
line_threshold="${AGENTIC_QUALITY_ADVISORY_LINES:-120}"
file_threshold="${AGENTIC_QUALITY_ADVISORY_FILES:-5}"
cooldown="${AGENTIC_QUALITY_ADVISORY_COOLDOWN_SECONDS:-300}"
now="$(date +%s)"
last=0
if [[ -f "$last_advice" ]]; then
  last="$(cat "$last_advice" 2>/dev/null || echo 0)"
fi
[[ "$last" =~ ^[0-9]+$ ]] || last=0

if (( total_lines < line_threshold && file_count < file_threshold )); then
  exit 0
fi

if (( now - last < cooldown )); then
  exit 0
fi

files_preview="$(sed -n '1,10p' "$files_state" | paste -sd ', ' -)"
extra_count=$(( file_count - 10 ))
if (( extra_count > 0 )); then
  files_preview="$files_preview, +$extra_count more"
fi

suggestions=()
go_files="$(grep -E '\.go$' "$files_state" | sed -n '1,8p' | paste -sd ' ' - || true)"
py_files="$(grep -E '\.pyi?$' "$files_state" | sed -n '1,8p' | paste -sd ' ' - || true)"
rs_changed=false
if grep -qE '\.rs$|Cargo\.toml$' "$files_state"; then
  rs_changed=true
fi
ts_files="$(grep -E '\.(ts|tsx|js|jsx|mjs|cjs|vue|svelte)$' "$files_state" | sed -n '1,8p' | paste -sd ' ' - || true)"

[[ -n "$go_files" ]] && suggestions+=("gofmt -w $go_files")
[[ -n "$py_files" ]] && suggestions+=("ruff check --fix $py_files && ruff format $py_files")
[[ "$rs_changed" == true ]] && suggestions+=("cargo fmt --all")
[[ -n "$ts_files" ]] && suggestions+=("biome check --write $ts_files")

suggestion_text=""
if [[ "${#suggestions[@]}" -gt 0 ]]; then
  suggestion_text=" Suggested targeted checks: $(printf '%s; ' "${suggestions[@]}" | sed 's/; $//')."
fi

langs=""
while IFS= read -r file; do
  lang="$(lang_for_file "$file")"
  [[ -n "$lang" ]] && langs="$langs $lang"
done < "$files_state"
langs="$(printf '%s\n' $langs | sort -u | paste -sd ', ' -)"

message="QUALITY ADVISORY: Significant selected-language edits detected ($file_count file(s), approx $total_lines changed line(s)). Before committing, run checks on the edited files only where practical.$suggestion_text Languages: ${langs:-selected}. Files: $files_preview"

printf '%s\n' "$now" > "$last_advice"
: > "$files_state"
printf '0\n' > "$lines_state"

jq -n --arg ctx "$message" '{
  hookSpecificOutput: {
    hookEventName: "PostToolUse",
    additionalContext: $ctx
  }
}'

exit 0
