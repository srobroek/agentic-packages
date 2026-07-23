#!/usr/bin/env bash
#
# dep-update/detect.sh: enumerate the project's declared dependencies and their
# pinned/declared versions, across ecosystems, WITHOUT network access.
#
# Portability floor: bash 3.2.57 + BSD sed/grep/awk (stock macOS). No jq
# required; parsing is best-effort and line-oriented (jq used when available
# for the node path for robustness).
#
# Output: one "ecosystem<TAB>name<TAB>version" line per dependency found, then
# a short summary on stderr. Version is the lockfile-pinned string verbatim;
# resolving it to a registry latest is the research step's job.
#
# Ecosystems covered: npm/pnpm/yarn (node), pip/uv/poetry (python),
# cargo (rust), go, ruby (Gemfile), php (composer.json).
#
# Usage: detect.sh [project-dir]   (defaults to the current directory)
#
# TWIN: packages/whats-new/.apm/skills/whats-new/scripts/detect.sh
# Keep both byte-identical except this header block.

set -uo pipefail

emit() { printf '%s\t%s\t%s\n' "$1" "$2" "$3"; }
note() { printf '%s\n' "$*" >&2; }

found=0

# --- node ------------------------------------------------------------------

scan_node() {
  [ -f package.json ] || return 0
  # Prefer jq for a JSON manifest: exact, and robust to inline-object form
  # ({ "a": "1", "b": "2" }) that a line parser misses. Fall back to a line
  # heuristic only when jq is absent.
  if command -v jq >/dev/null 2>&1; then
    local pair name ver
    while IFS= read -r pair; do
      name=${pair%%$'\t'*}
      ver=${pair#*$'\t'}
      [ -n "$name" ] || continue
      emit "npm" "$name" "${ver:-?}"
      found=$((found + 1))
    done <<EOF
$(jq -r '
  [ (.dependencies // {}), (.devDependencies // {}),
    (.peerDependencies // {}), (.optionalDependencies // {}) ]
  | add // {} | to_entries[] | .key + "\t" + (.value|tostring)
' package.json 2>/dev/null)
EOF
    return 0
  fi
  # --- jq-less fallback: heuristic line parse of the *Dependencies blocks ---
  local in_deps=0 line key ver
  while IFS= read -r line; do
    case "$line" in
      *'"dependencies"'*|*'"devDependencies"'*|*'"peerDependencies"'*|*'"optionalDependencies"'*)
        in_deps=1; continue ;;
    esac
    if [ "$in_deps" -eq 1 ]; then
      case "$line" in
        *'}'*) in_deps=0; continue ;;
      esac
      # "  \"left-pad\": \"^1.3.0\","  ->  key=left-pad ver=^1.3.0
      key=$(printf '%s\n' "$line" | sed -n 's/^[[:space:]]*"\([^"]*\)"[[:space:]]*:.*/\1/p')
      ver=$(printf '%s\n' "$line" | sed -n 's/^[[:space:]]*"[^"]*"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
      if [ -n "$key" ]; then
        emit "npm" "$key" "${ver:-?}"
        found=$((found + 1))
      fi
    fi
  done < package.json
}

# --- python ----------------------------------------------------------------

scan_python() {
  # uv.lock: "name = ..." lines inside [[package]] blocks (best-effort).
  if [ -f uv.lock ]; then
    local in_pkg=0 pkg_name pkg_ver line
    pkg_name=""; pkg_ver=""
    while IFS= read -r line; do
      case "$line" in
        '[[package]]'*)
          # Emit the previous package if complete.
          if [ -n "$pkg_name" ] && [ -n "$pkg_ver" ]; then
            emit "pypi" "$pkg_name" "$pkg_ver"
            found=$((found + 1))
          fi
          pkg_name=""; pkg_ver=""; in_pkg=1 ;;
        'name = "'*)
          [ "$in_pkg" -eq 1 ] || continue
          pkg_name=$(printf '%s\n' "$line" | sed -n 's/^name = "\([^"]*\)".*/\1/p') ;;
        'version = "'*)
          [ "$in_pkg" -eq 1 ] || continue
          pkg_ver=$(printf '%s\n' "$line" | sed -n 's/^version = "\([^"]*\)".*/\1/p') ;;
      esac
    done < uv.lock
    # Emit the last package.
    if [ -n "$pkg_name" ] && [ -n "$pkg_ver" ]; then
      emit "pypi" "$pkg_name" "$pkg_ver"
      found=$((found + 1))
    fi
    return 0
  fi

  # poetry.lock: name/version pairs.
  if [ -f poetry.lock ]; then
    local in_pkg=0 pkg_name pkg_ver line
    pkg_name=""; pkg_ver=""
    while IFS= read -r line; do
      case "$line" in
        '[[package]]'*)
          if [ -n "$pkg_name" ] && [ -n "$pkg_ver" ]; then
            emit "pypi" "$pkg_name" "$pkg_ver"
            found=$((found + 1))
          fi
          pkg_name=""; pkg_ver=""; in_pkg=1 ;;
        'name = "'*)
          [ "$in_pkg" -eq 1 ] || continue
          pkg_name=$(printf '%s\n' "$line" | sed -n 's/^name = "\([^"]*\)".*/\1/p') ;;
        'version = "'*)
          [ "$in_pkg" -eq 1 ] || continue
          pkg_ver=$(printf '%s\n' "$line" | sed -n 's/^version = "\([^"]*\)".*/\1/p') ;;
      esac
    done < poetry.lock
    if [ -n "$pkg_name" ] && [ -n "$pkg_ver" ]; then
      emit "pypi" "$pkg_name" "$pkg_ver"
      found=$((found + 1))
    fi
    return 0
  fi

  # requirements.txt: "pkg==1.2.3" / "pkg>=1.0" / "pkg".
  if [ -f requirements.txt ]; then
    local line name ver
    while IFS= read -r line; do
      line=$(printf '%s\n' "$line" | sed 's/#.*//' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
      [ -n "$line" ] || continue
      case "$line" in -*|.*|/*) continue ;; esac   # skip -r/-e/paths
      name=$(printf '%s\n' "$line" | sed -E 's/[][<>=!~ ].*//')
      ver=$(printf '%s\n' "$line" | sed -E 's/^[^][<>=!~]*//')
      [ -n "$name" ] || continue
      emit "pypi" "$name" "${ver:-?}"
      found=$((found + 1))
    done < requirements.txt
    return 0
  fi

  # pyproject.toml: [project] dependencies and [tool.poetry.dependencies].
  if [ -f pyproject.toml ]; then
    local line name ver
    while IFS= read -r line; do
      case "$line" in
        *'='*'"'*)   # poetry style:  requests = "^2.28"
          name=$(printf '%s\n' "$line" | sed -n 's/^[[:space:]]*\([A-Za-z0-9._-]*\)[[:space:]]*=.*/\1/p')
          ver=$(printf '%s\n' "$line" | sed -n 's/.*"\([^"]*\)".*/\1/p')
          case "$name" in python|''|'['*) continue ;; esac
          [ -n "$name" ] && { emit "pypi" "$name" "${ver:-?}"; found=$((found + 1)); }
          ;;
      esac
    done < pyproject.toml
  fi
}

# --- rust ------------------------------------------------------------------

scan_rust() {
  [ -f Cargo.toml ] || return 0
  local in_deps=0 line name ver
  while IFS= read -r line; do
    case "$line" in
      '[dependencies]'*|'[dev-dependencies]'*|'[build-dependencies]'*) in_deps=1; continue ;;
      '['*) in_deps=0; continue ;;
    esac
    [ "$in_deps" -eq 1 ] || continue
    case "$line" in
      *'='*)
        name=$(printf '%s\n' "$line" | sed -n 's/^[[:space:]]*\([A-Za-z0-9._-]*\)[[:space:]]*=.*/\1/p')
        # version = "1.2" OR { version = "1.2", ... }
        ver=$(printf '%s\n' "$line" | sed -n 's/.*version[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p')
        [ -n "$ver" ] || ver=$(printf '%s\n' "$line" | sed -n 's/^[^=]*=[[:space:]]*"\([^"]*\)".*/\1/p')
        [ -n "$name" ] && { emit "cargo" "$name" "${ver:-?}"; found=$((found + 1)); }
        ;;
    esac
  done < Cargo.toml
}

# --- go --------------------------------------------------------------------

scan_go() {
  [ -f go.mod ] || return 0
  # require lines: single "require mod v1.2.3" or a "require ( ... )" block.
  local in_block=0 line mod ver
  while IFS= read -r line; do
    case "$line" in
      'require ('*) in_block=1; continue ;;
      ')'*) [ "$in_block" -eq 1 ] && in_block=0; continue ;;
      'require '*)
        mod=$(printf '%s\n' "$line" | awk '{print $2}')
        ver=$(printf '%s\n' "$line" | awk '{print $3}')
        [ -n "$mod" ] && { emit "go" "$mod" "${ver:-?}"; found=$((found + 1)); }
        continue ;;
    esac
    if [ "$in_block" -eq 1 ]; then
      mod=$(printf '%s\n' "$line" | awk '{print $1}')
      ver=$(printf '%s\n' "$line" | awk '{print $2}')
      case "$mod" in ''|//*) continue ;; esac
      emit "go" "$mod" "${ver:-?}"
      found=$((found + 1))
    fi
  done < go.mod
}

# --- ruby ------------------------------------------------------------------

scan_ruby() {
  [ -f Gemfile ] || return 0
  local line name ver
  while IFS= read -r line; do
    case "$line" in
      *gem\ *)
        name=$(printf '%s\n' "$line" | sed -n "s/.*gem[[:space:]]*['\"]\\([^'\"]*\\)['\"].*/\\1/p")
        ver=$(printf '%s\n' "$line" | sed -n "s/.*gem[[:space:]]*['\"][^'\"]*['\"][[:space:]]*,[[:space:]]*['\"]\\([^'\"]*\\)['\"].*/\\1/p")
        [ -n "$name" ] && { emit "rubygems" "$name" "${ver:-?}"; found=$((found + 1)); }
        ;;
    esac
  done < Gemfile
}

# --- php -------------------------------------------------------------------

scan_php() {
  [ -f composer.json ] || return 0
  # Prefer jq (robust to inline-object form); platform reqs (php, ext-*, lib-*)
  # are not packages -- drop them.
  if command -v jq >/dev/null 2>&1; then
    local pair name ver
    while IFS= read -r pair; do
      name=${pair%%$'\t'*}
      ver=${pair#*$'\t'}
      case "$name" in php|ext-*|lib-*|''|*' '*) continue ;; esac
      emit "packagist" "$name" "${ver:-?}"
      found=$((found + 1))
    done <<EOF
$(jq -r '
  [ (.require // {}), (."require-dev" // {}) ] | add // {}
  | to_entries[] | .key + "\t" + (.value|tostring)
' composer.json 2>/dev/null)
EOF
    return 0
  fi
  # --- jq-less fallback ---
  local in_deps=0 line key ver
  while IFS= read -r line; do
    case "$line" in
      *'"require"'*|*'"require-dev"'*) in_deps=1; continue ;;
    esac
    if [ "$in_deps" -eq 1 ]; then
      case "$line" in *'}'*) in_deps=0; continue ;; esac
      key=$(printf '%s\n' "$line" | sed -n 's/^[[:space:]]*"\([^"]*\)"[[:space:]]*:.*/\1/p')
      ver=$(printf '%s\n' "$line" | sed -n 's/^[[:space:]]*"[^"]*"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
      case "$key" in php|ext-*|''|lib-*) continue ;; esac
      [ -n "$key" ] && { emit "packagist" "$key" "${ver:-?}"; found=$((found + 1)); }
    fi
  done < composer.json
}

# --- main ------------------------------------------------------------------

main() {
  local target="${1:-.}"
  if [ ! -d "$target" ]; then
    note "detect.sh: '$target' is not a directory"
    return 2
  fi
  cd "$target" || return 2

  scan_node
  scan_python
  scan_rust
  scan_go
  scan_ruby
  scan_php

  note ""
  note "detect: ${found} dependency declaration(s) found in ${target}"
  if [ "$found" -eq 0 ]; then
    note "No supported manifest found (package.json, uv.lock, poetry.lock,"
    note "requirements.txt, pyproject.toml, Cargo.toml, go.mod, Gemfile,"
    note "composer.json)."
  fi
  return 0
}

main "$@"
