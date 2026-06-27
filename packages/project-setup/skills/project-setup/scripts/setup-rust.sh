#!/usr/bin/env bash
# shellcheck shell=bash
# setup-rust — Rust project overlay
#
# Adds Rust tooling to a project scaffolded by project-setup.sh.
#
# Usage:
#   setup-rust.sh [options]
#
# Options:
#   --workspace   Initialize as cargo workspace
#   --esp         Use esp-idf toolchain (espup)
#   --help        Show this help

set -euo pipefail

WORKSPACE=false
ESP=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --workspace) WORKSPACE=true; shift ;;
        --esp)       ESP=true; shift ;;
        --help)
            sed -n '3,/^$/p' "$0" | sed -E 's/^#[[:space:]]?//'
            exit 0
            ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

echo "=== Rust Setup ==="
echo "Workspace: $WORKSPACE"
echo "ESP-IDF: $ESP"

# --- Step 1: Cargo init ---
if [ ! -f Cargo.toml ]; then
    if $WORKSPACE; then
        echo "Initializing cargo workspace..."
        cat > Cargo.toml <<'TOML'
[workspace]
resolver = "2"
members = []

[workspace.dependencies]
TOML
    else
        echo "Initializing cargo project..."
        cargo init .
    fi
else
    echo "Cargo.toml already exists"
fi

# --- Step 2: Rust toolchain ---
if $ESP; then
    if [ ! -f rust-toolchain.toml ]; then
        echo "Creating ESP rust-toolchain.toml..."
        cat > rust-toolchain.toml <<'TOML'
[toolchain]
channel = "esp"
TOML
    fi
else
    if [ ! -f rust-toolchain.toml ]; then
        echo "Creating rust-toolchain.toml..."
        cat > rust-toolchain.toml <<'TOML'
[toolchain]
channel = "stable"
components = ["rustfmt", "clippy"]
TOML
    fi
fi

# --- Step 3: Clippy config ---
if [ ! -f clippy.toml ]; then
    echo "Creating clippy.toml..."
    cat > clippy.toml <<'TOML'
too-many-arguments-threshold = 8
type-complexity-threshold = 350
TOML
fi

# --- Step 4: rustfmt config ---
if [ ! -f rustfmt.toml ]; then
    echo "Creating rustfmt.toml..."
    cat > rustfmt.toml <<'TOML'
edition = "2021"
max_width = 100
use_small_heuristics = "Max"
TOML
fi

# --- Step 5: Append Rust gitignore via gitnr ---
write_rust_gitignore_fallback() {
    cat >> .gitignore <<'GITIGNORE'

# Rust
debug
target
**/*.rs.bk
*.pdb
GITIGNORE
}

if ! grep -q '/target' .gitignore 2>/dev/null; then
    echo "Appending Rust gitignore..."
    # gitnr may be installed but still fail (network, template lookup). Capture
    # its output to a temp file and only append on success; otherwise fall back
    # to a static block so a present-but-failing gitnr never leaves a broken or
    # truncated .gitignore.
    _gi_tmp="$(mktemp "${TMPDIR:-/tmp}/gitignore.XXXXXX")"
    if command -v gitnr >/dev/null 2>&1 && gitnr create gh:Rust > "$_gi_tmp" && [ -s "$_gi_tmp" ]; then
        printf '\n' >> .gitignore
        cat "$_gi_tmp" >> .gitignore
    else
        echo "  WARN: gitnr unavailable or failed; using static Rust .gitignore"
        write_rust_gitignore_fallback
    fi
    rm -f "$_gi_tmp"
fi

# --- Step 6: Append Rust pre-commit hooks (fmt at commit, clippy at push) ---
if [ -f .pre-commit-config.yaml ] && ! grep -q 'doublify/pre-commit-rust' .pre-commit-config.yaml; then
    echo "Adding Rust pre-commit hooks..."
    cat >> .pre-commit-config.yaml <<'PCYAML'

  - repo: https://github.com/doublify/pre-commit-rust
    rev: v1.0
    hooks:
      - id: fmt
      - id: clippy
        stages: [pre-push]
PCYAML
fi

echo ""
echo "=== Rust setup complete ==="
