#!/usr/bin/env bats
# Tests for the mcp-package-version advisory hooks.
# Portability floor: bash 3.2.57 + BSD coreutils (stock macOS).
# Run with: bats packages/mcp-package-version/tests/mcp-package-version.bats

setup() {
  SCRIPTS="${BATS_TEST_DIRNAME}/../scripts"
  PKGVER="${SCRIPTS}/pkg-version-warn.sh"
  PKGFILE="${SCRIPTS}/package-file-warn.sh"
}

# ---------------------------------------------------------------------------
# pkg-version-warn.sh -- leading-token anchoring
# ---------------------------------------------------------------------------

@test "pkg-version: 'echo pip install' is suppressed (substring, not a command)" {
  run bash "$PKGVER" <<<'{"tool_input":{"command":"echo pip install foo"}}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "pkg-version: grep with embedded 'npm install' is suppressed" {
  run bash "$PKGVER" <<<'{"tool_input":{"command":"grep \"npm install\" file.txt"}}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "pkg-version: real 'pip install' fires the PyPI advisory" {
  run bash "$PKGVER" <<<'{"tool_input":{"command":"pip install requests"}}'
  [ "$status" -eq 0 ]
  echo "$output" | jq . >/dev/null
  [[ "$output" == *"PyPI"* ]]
}

@test "pkg-version: 'uv pip install' fires the PyPI advisory" {
  run bash "$PKGVER" <<<'{"tool_input":{"command":"uv pip install requests"}}'
  [ "$status" -eq 0 ]
  echo "$output" | jq . >/dev/null
  [[ "$output" == *"PyPI"* ]]
}

@test "pkg-version: leading whitespace before 'npm install' still fires" {
  run bash "$PKGVER" <<<'{"tool_input":{"command":"   npm install left-pad"}}'
  [ "$status" -eq 0 ]
  echo "$output" | jq . >/dev/null
}

@test "pkg-version: 'cargo add' is intentionally silent" {
  run bash "$PKGVER" <<<'{"tool_input":{"command":"cargo add serde"}}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "pkg-version: string-form tool_input does not throw and fires" {
  run bash "$PKGVER" <<<'{"tool_input":"pnpm add left-pad"}'
  [ "$status" -eq 0 ]
  echo "$output" | jq . >/dev/null
}

@test "pkg-version: empty stdin exits silently" {
  run bash "$PKGVER" <<<''
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "pkg-version: unrelated command exits silently" {
  run bash "$PKGVER" <<<'{"tool_input":{"command":"ls -la"}}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# ---------------------------------------------------------------------------
# package-file-warn.sh -- old_string must not be treated as a path
# ---------------------------------------------------------------------------

@test "pkg-file: Edit whose old_string mentions package.json is NOT flagged" {
  # file_path is a .ts source; old_string text mentions package.json.
  run bash "$PKGFILE" <<<'{"tool_input":{"file_path":"src/index.ts","old_string":"package.json"}}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "pkg-file: editing a real package.json fires" {
  run bash "$PKGFILE" <<<'{"tool_input":{"file_path":"/repo/package.json"}}'
  [ "$status" -eq 0 ]
  echo "$output" | jq . >/dev/null
  [[ "$output" == *"package.json"* ]]
}

@test "pkg-file: Cargo.toml fires" {
  run bash "$PKGFILE" <<<'{"tool_input":{"file_path":"/repo/Cargo.toml"}}'
  [ "$status" -eq 0 ]
  echo "$output" | jq . >/dev/null
}

@test "pkg-file: no file_path exits silently" {
  run bash "$PKGFILE" <<<'{"tool_input":{}}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "pkg-file: empty stdin exits silently" {
  run bash "$PKGFILE" <<<''
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}
