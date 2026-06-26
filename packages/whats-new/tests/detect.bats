#!/usr/bin/env bats
#
# Tests for whats-new's scripts/detect.sh (offline dependency enumeration).
# Portability floor: bash 3.2.57 + BSD sed/grep/awk.
# Run with: bats packages/whats-new/tests/detect.bats

setup() {
  SCRIPT="${BATS_TEST_DIRNAME}/../.apm/skills/whats-new/scripts/detect.sh"
  PROJ="$(mktemp -d "${BATS_TMPDIR:-/tmp}/whats-new-proj.XXXXXX")"
}

teardown() {
  rm -rf "$PROJ"
}

run_detect() {
  run /bin/bash "$SCRIPT" "$PROJ"
}

# --- portability floor ------------------------------------------------------

@test "detect.sh parses under /bin/bash (bash 3.2)" {
  run /bin/bash -n "$SCRIPT"
  [ "$status" -eq 0 ]
}

# --- empty / bad input ------------------------------------------------------

@test "empty project: no rows, reports zero, exit 0" {
  run_detect
  [ "$status" -eq 0 ]
  [[ "$output" == *"0 dependency declaration(s) found"* ]]
  [[ "$output" == *"No supported manifest"* ]]
}

@test "non-existent target directory: exit 2" {
  run /bin/bash "$SCRIPT" "${PROJ}/nope"
  [ "$status" -eq 2 ]
}

# --- node -------------------------------------------------------------------

@test "package.json deps + devDeps are emitted with npm ecosystem" {
  cat >"${PROJ}/package.json" <<'JSON'
{
  "name": "demo",
  "dependencies": { "react": "^18.2.0", "left-pad": "1.3.0" },
  "devDependencies": { "typescript": "~5.4.0" }
}
JSON
  run_detect
  [ "$status" -eq 0 ]
  [[ "$output" == *"npm"$'\t'"react"$'\t'"^18.2.0"* ]]
  [[ "$output" == *"npm"$'\t'"left-pad"$'\t'"1.3.0"* ]]
  [[ "$output" == *"npm"$'\t'"typescript"$'\t'"~5.4.0"* ]]
}

# --- python -----------------------------------------------------------------

@test "requirements.txt: pins, ranges, bare names; comments skipped" {
  cat >"${PROJ}/requirements.txt" <<'REQ'
requests==2.31.0
flask>=3.0
# a comment line
numpy
-r other.txt
REQ
  run_detect
  [ "$status" -eq 0 ]
  [[ "$output" == *"pypi"$'\t'"requests"$'\t'"==2.31.0"* ]]
  [[ "$output" == *"pypi"$'\t'"flask"$'\t'">=3.0"* ]]
  [[ "$output" == *"pypi"$'\t'"numpy"$'\t'"?"* ]]
  # The -r include directive must not become a dependency row.
  [[ "$output" != *"other.txt"* ]]
}

@test "pyproject.toml poetry-style deps; python itself skipped" {
  cat >"${PROJ}/pyproject.toml" <<'TOML'
[tool.poetry.dependencies]
python = "^3.11"
requests = "^2.28"
TOML
  run_detect
  [ "$status" -eq 0 ]
  [[ "$output" == *"pypi"$'\t'"requests"$'\t'"^2.28"* ]]
  [[ "$output" != *$'\t'"python"$'\t'* ]]
}

# --- rust -------------------------------------------------------------------

@test "Cargo.toml: plain and table-form versions" {
  cat >"${PROJ}/Cargo.toml" <<'TOML'
[package]
name = "demo"

[dependencies]
serde = "1.0"
tokio = { version = "1.36", features = ["full"] }
TOML
  run_detect
  [ "$status" -eq 0 ]
  [[ "$output" == *"cargo"$'\t'"serde"$'\t'"1.0"* ]]
  [[ "$output" == *"cargo"$'\t'"tokio"$'\t'"1.36"* ]]
}

# --- go ---------------------------------------------------------------------

@test "go.mod: require block and single-line require; indirect kept" {
  cat >"${PROJ}/go.mod" <<'GOMOD'
module example.com/m

go 1.22

require (
	github.com/spf13/cobra v1.8.0
	golang.org/x/text v0.14.0 // indirect
)

require github.com/stretchr/testify v1.9.0
GOMOD
  run_detect
  [ "$status" -eq 0 ]
  [[ "$output" == *"go"$'\t'"github.com/spf13/cobra"$'\t'"v1.8.0"* ]]
  [[ "$output" == *"go"$'\t'"golang.org/x/text"$'\t'"v0.14.0"* ]]
  [[ "$output" == *"go"$'\t'"github.com/stretchr/testify"$'\t'"v1.9.0"* ]]
}

# --- ruby / php -------------------------------------------------------------

@test "Gemfile: gem with and without version" {
  cat >"${PROJ}/Gemfile" <<'GEM'
source "https://rubygems.org"
gem "rails", "~> 7.1"
gem "puma"
GEM
  run_detect
  [ "$status" -eq 0 ]
  [[ "$output" == *"rubygems"$'\t'"rails"$'\t'"~> 7.1"* ]]
  [[ "$output" == *"rubygems"$'\t'"puma"$'\t'"?"* ]]
}

@test "composer.json: require block; php and ext-* skipped" {
  cat >"${PROJ}/composer.json" <<'JSON'
{
  "require": {
    "php": ">=8.1",
    "ext-json": "*",
    "monolog/monolog": "^3.0"
  }
}
JSON
  run_detect
  [ "$status" -eq 0 ]
  [[ "$output" == *"packagist"$'\t'"monolog/monolog"$'\t'"^3.0"* ]]
  [[ "$output" != *$'\t'"php"$'\t'* ]]
  [[ "$output" != *"ext-json"* ]]
}

# --- multi-ecosystem --------------------------------------------------------

@test "jq-less fallback: line-parses one-per-line package.json (PATH without jq)" {
  # Force the heuristic path by running with a PATH that excludes jq. npm writes
  # package.json one dependency per line, which the fallback parser handles.
  cat >"${PROJ}/package.json" <<'JSON'
{
  "name": "demo",
  "dependencies": {
    "react": "^18.2.0",
    "left-pad": "1.3.0"
  }
}
JSON
  # A minimal stub bin dir with the real coreutils the script needs but no jq.
  stub="$(mktemp -d "${BATS_TMPDIR:-/tmp}/whats-new-nojq.XXXXXX")"
  for t in bash sed grep awk printf cat; do
    src="$(command -v "$t" 2>/dev/null || true)"
    [ -n "$src" ] && ln -s "$src" "${stub}/${t}" 2>/dev/null || true
  done
  run env PATH="${stub}" /bin/bash "$SCRIPT" "$PROJ"
  rm -rf "$stub"
  [ "$status" -eq 0 ]
  [[ "$output" == *"npm"$'\t'"react"$'\t'"^18.2.0"* ]]
  [[ "$output" == *"npm"$'\t'"left-pad"$'\t'"1.3.0"* ]]
}

@test "polyglot repo: counts every ecosystem found" {
  : >"${PROJ}/package.json"
  printf '{ "dependencies": { "a": "1.0.0" } }\n' >"${PROJ}/package.json"
  printf 'requests==2.31.0\n' >"${PROJ}/requirements.txt"
  run_detect
  [ "$status" -eq 0 ]
  [[ "$output" == *"npm"$'\t'"a"* ]]
  [[ "$output" == *"pypi"$'\t'"requests"* ]]
}
