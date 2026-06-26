#!/usr/bin/env bash
# shellcheck shell=bash
# setup-ts — TypeScript project overlay
#
# Adds TypeScript tooling to a project scaffolded by project-setup.sh.
#
# Usage:
#   setup-ts.sh [options]
#
# Options:
#   --pkg-manager   bun|pnpm (default: bun)
#   --framework     nuxt|vite|plain (default: plain)
#   --sst           Add SST for AWS deployment
#   --help          Show this help

set -euo pipefail

PKG_MANAGER="bun"
FRAMEWORK="plain"
ADD_SST=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --pkg-manager) PKG_MANAGER="${2:?--pkg-manager needs a value}"; shift 2 ;;
        --framework)   FRAMEWORK="${2:?--framework needs a value}"; shift 2 ;;
        --sst)         ADD_SST=true; shift ;;
        --help)
            sed -n '3,/^$/p' "$0" | sed -E 's/^#[[:space:]]?//'
            exit 0
            ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

# Validate
case "$PKG_MANAGER" in
    bun|pnpm) ;;
    *) echo "Error: --pkg-manager must be bun or pnpm" >&2; exit 1 ;;
esac

case "$FRAMEWORK" in
    nuxt|vite|plain) ;;
    *) echo "Error: --framework must be nuxt, vite, or plain" >&2; exit 1 ;;
esac

echo "=== TypeScript Setup ==="
echo "Package manager: $PKG_MANAGER"
echo "Framework: $FRAMEWORK"
echo "SST: $ADD_SST"

# --- Helper: run pkg manager ---
pkg() {
    case "$PKG_MANAGER" in
        bun)  bun "$@" ;;
        pnpm) pnpm "$@" ;;
    esac
}

pkgx() {
    case "$PKG_MANAGER" in
        bun)  bunx "$@" ;;
        pnpm) pnpm dlx "$@" ;;
    esac
}

# --- Step 1: Framework scaffold ---
case "$FRAMEWORK" in
    nuxt)
        if [ ! -f nuxt.config.ts ]; then
            echo "Scaffolding Nuxt 3..."
            pkgx nuxi@latest init . --force --packageManager "$PKG_MANAGER"
        else
            echo "Nuxt already scaffolded"
        fi
        ;;
    vite)
        if [ ! -f vite.config.ts ]; then
            echo "Scaffolding Vite + Vue..."
            pkgx create-vite . --template vue-ts
        else
            echo "Vite already scaffolded"
        fi
        ;;
    plain)
        if [ ! -f package.json ]; then
            echo "Initializing package.json..."
            case "$PKG_MANAGER" in
                bun)  bun init -y ;;
                pnpm) pnpm init ;;
            esac
        else
            echo "package.json already exists"
        fi

        # Ensure TypeScript
        if [ ! -f tsconfig.json ]; then
            echo "Adding TypeScript..."
            pkg add --dev typescript
            cat > tsconfig.json <<'TSCONFIG'
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true,
    "outDir": "./dist"
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"]
}
TSCONFIG
            mkdir -p src
        fi
        ;;
esac

# --- Step 2: Install dependencies ---
echo "Installing dependencies..."
pkg install

# --- Step 3: SST ---
if $ADD_SST; then
    echo "Adding SST..."
    pkg add --dev sst

    if [ ! -f sst.config.ts ]; then
        pkgx sst init || echo "  WARN: sst init failed — run interactively"
    else
        echo "sst.config.ts already exists"
    fi

    # Add SST to .gitignore if not present
    if ! grep -q '\.sst' .gitignore 2>/dev/null; then
        printf '\n# SST\n.sst\n' >> .gitignore
    fi
fi

# --- Step 4: Append TS/Node gitignore via gitnr ---
write_node_gitignore_fallback() {
    cat >> .gitignore <<'GITIGNORE'

# Node
node_modules
dist
*.tsbuildinfo
logs
*.log
GITIGNORE
}

if ! grep -q 'node_modules' .gitignore 2>/dev/null; then
    echo "Appending Node gitignore..."
    # gitnr may be installed but still fail (network, template lookup). Capture
    # its output to a temp file and only append on success; otherwise fall back
    # to a static block so a present-but-failing gitnr never leaves a broken or
    # truncated .gitignore.
    _gi_tmp="$(mktemp "${TMPDIR:-/tmp}/gitignore.XXXXXX")"
    if command -v gitnr >/dev/null 2>&1 && gitnr create gh:Node > "$_gi_tmp" && [ -s "$_gi_tmp" ]; then
        printf '\n' >> .gitignore
        cat "$_gi_tmp" >> .gitignore
    else
        echo "  WARN: gitnr unavailable or failed; using static Node .gitignore"
        write_node_gitignore_fallback
    fi
    rm -f "$_gi_tmp"
fi

# Framework-specific extras not covered by gh:Node
case "$FRAMEWORK" in
    nuxt)
        if ! grep -q '\.nitro' .gitignore 2>/dev/null; then
            cat >> .gitignore <<'GITIGNORE'

# Nuxt extras
.nitro
.data
GITIGNORE
        fi
        ;;
esac

# --- Step 5: Append biome + prettier pre-commit hooks ---
if [ -f .pre-commit-config.yaml ] && ! grep -q 'biomejs/pre-commit' .pre-commit-config.yaml; then
    echo "Adding biome pre-commit hook..."
    cat >> .pre-commit-config.yaml <<'PCYAML'

  - repo: https://github.com/biomejs/pre-commit
    rev: v0.6.1
    hooks:
      - id: biome-check
        args: [--write]
PCYAML
fi

if [ -f .pre-commit-config.yaml ] && ! grep -q 'rbubley/mirrors-prettier' .pre-commit-config.yaml; then
    echo "Adding prettier pre-commit hook (markdown + yaml)..."
    cat >> .pre-commit-config.yaml <<'PCYAML'

  - repo: https://github.com/rbubley/mirrors-prettier
    rev: v3.3.3
    hooks:
      - id: prettier
        types_or: [markdown, yaml]
PCYAML
fi

echo ""
echo "=== TypeScript setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Let the agent update AGENTS.md with architecture and workflow details"
echo "  2. Let the agent update justfile with project-specific commands"
echo "  3. Let the agent add language-specific pre-commit hooks"
