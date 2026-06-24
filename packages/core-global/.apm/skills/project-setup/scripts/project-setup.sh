#!/usr/bin/env bash
# shellcheck shell=bash
# project-setup — universal project scaffold
#
# Creates standard directory structure, git repo, GitHub remote,
# universal pre-commit hooks, agent quality markers, skeleton configs.
# Language-agnostic.
#
# Usage:
#   project-setup.sh --name <name> --org <owner> [options]
#
# Options:
#   --name        Project name (required)
#   --org         GitHub owner/org (required)
#   --dir         Project directory (default: current dir)
#   --description Project description for GitHub repo
#   --license     License type (default: apache-2.0)
#   --speckit     Initialize speckit + shared workflows/extensions
#   --spec-mode   Spec mode: none, lightweight, full (default: none)
#   --speckit-integration Integration to use for speckit init (default: codex)
#   --speckit-script Script type to use for speckit init (default: sh)
#   --public      Make GitHub repo public (default: private)
#   --no-repo     Skip GitHub repo creation
#   --no-git      Skip git init (repo already exists)
#   --layout      Project layout: single, monorepo (default: single)
#   --monorepo    Alias for --layout monorepo
#   --target      Capability target directory; repeatable (apps/web, services/api, etc.)
#   --just        Create justfile
#   --mise        Create mise.toml
#   --moon        Create .moon workspace scaffold
#   --apm-install Install APM package after writing apm.yml (default)
#   --no-apm-install Skip APM install/finalizers
#   --apm-compile Compile Codex steering after APM install (default)
#   --no-apm-compile Skip APM compile
#   --no-compile-claude Skip Claude steering compile
#   --marketplace-repo Repository for the srobroek-agentic APM marketplace (default: srobroek/agentic-packages)
#   --marketplace-name Local marketplace name (default: srobroek-agentic)
#   --skip-marketplace-register Do not register/update the srobroek-agentic marketplace
#   --agentic-packages Base package dependency (default: core@srobroek-agentic)
#   --apm-dependency Extra APM dependency to add to apm.yml; repeatable
#   --selected-bundle Bundle recommended/selected for this project; repeatable
#   --selected-agent Agent recommended/selected for this project; repeatable
#   --selected-skill Skill recommended/selected for this project; repeatable
#   --selected-mcp MCP server/package recommended/selected for this project; repeatable
#   --lang        Language overlay: ts, rust, python, go (chains to setup-{lang}.sh)
#   --lang-args   Extra args to pass to setup-{lang}.sh (quoted string)
#   --quality-lang Language whose agent before-commit quality hook should run; repeatable
#   --help        Show this help

set -euo pipefail

# --- Defaults ---
PROJECT_NAME=""
ORG=""
PROJECT_DIR="."
DESCRIPTION=""
LICENSE="apache-2.0"
INIT_SPECKIT=false
SPEC_MODE="none"
SPECKIT_INTEGRATION="codex"
SPECKIT_SCRIPT_TYPE="sh"
PUBLIC=false
CREATE_REPO=true
INIT_GIT=true
LAYOUT="single"
# Note: not named LANG to avoid clobbering the exported locale variable.
OVERLAY_LANG=""
LANG_ARGS=""
TARGETS=()
USE_JUST=false
USE_MISE=false
USE_MOON=false
APM_INSTALL=true
APM_COMPILE=true
COMPILE_CLAUDE=true
MARKETPLACE_REPO="srobroek/agentic-packages"
MARKETPLACE_NAME="srobroek-agentic"
REGISTER_MARKETPLACE=true
AGENTIC_PACKAGES_SOURCE="core@srobroek-agentic"
BASELINE_MCP_PACKAGES=(
    "mcp-codebase-memory@srobroek-agentic"
    "mcp-context7@srobroek-agentic"
    "mcp-package-version@srobroek-agentic"
    "mcp-repomix@srobroek-agentic"
)
EXTRA_APM_DEPENDENCIES=()
SELECTED_BUNDLES=()
SELECTED_AGENTS=()
SELECTED_SKILLS=()
SELECTED_MCP=()
QUALITY_LANGS=()
AGENTIC_TOOLS_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/agentic-tools"

run_apm() {
    if [ -z "${GITHUB_APM_PAT:-}" ] && command -v gh >/dev/null 2>&1; then
        GITHUB_APM_PAT="$(gh auth token 2>/dev/null || true)"
        if [ -n "$GITHUB_APM_PAT" ]; then
            export GITHUB_APM_PAT
        fi
    fi

    if command -v apm >/dev/null 2>&1; then
        apm "$@"
    elif command -v mise >/dev/null 2>&1 && mise which apm >/dev/null 2>&1; then
        mise exec -- apm "$@"
    elif command -v uv >/dev/null 2>&1; then
        uv tool run --from apm-cli apm "$@"
    else
        return 127
    fi
}

fail_if_codex_protected_paths_are_readonly() {
    local blocked=()
    local path

    for path in .git .codex .agents; do
        if [ -e "$path" ] && [ ! -w "$path" ]; then
            blocked+=("$path")
        fi
    done

    if [ "${#blocked[@]}" -eq 0 ]; then
        return 0
    fi

    {
        echo "Error: project setup cannot write protected bootstrap paths:"
        printf '  - %s\n' "${blocked[@]}"
        echo ""
        echo "Codex workspace-write protects .git, .codex, and .agents as read-only."
        echo "Rerun this exact setup executor outside the sandbox with approval:"
        echo '  sandbox_permissions = "require_escalated"'
        echo "Use a justification that project setup writes protected bootstrap paths."
    } >&2
    exit 1
}

# --- Parse args ---
while [[ $# -gt 0 ]]; do
    case $1 in
        --name)        PROJECT_NAME="$2"; shift 2 ;;
        --org)         ORG="$2"; shift 2 ;;
        --dir)         PROJECT_DIR="$2"; shift 2 ;;
        --description) DESCRIPTION="$2"; shift 2 ;;
        --license)     LICENSE="$2"; shift 2 ;;
        --speckit)     INIT_SPECKIT=true; shift ;;
        --spec-mode)   SPEC_MODE="$2"; shift 2 ;;
        --speckit-integration) SPECKIT_INTEGRATION="$2"; shift 2 ;;
        --speckit-script) SPECKIT_SCRIPT_TYPE="$2"; shift 2 ;;
        --public)      PUBLIC=true; shift ;;
        --no-repo)     CREATE_REPO=false; shift ;;
        --no-git)      INIT_GIT=false; shift ;;
        --layout)      LAYOUT="$2"; shift 2 ;;
        --monorepo)    LAYOUT="monorepo"; shift ;;
        --target)      TARGETS+=("$2"); shift 2 ;;
        --just)        USE_JUST=true; shift ;;
        --mise)        USE_MISE=true; shift ;;
        --moon)        USE_MOON=true; shift ;;
        --apm-install) APM_INSTALL=true; shift ;;
        --no-apm-install) APM_INSTALL=false; shift ;;
        --apm-compile) APM_COMPILE=true; shift ;;
        --no-apm-compile) APM_COMPILE=false; shift ;;
        --compile-claude) COMPILE_CLAUDE=true; shift ;;
        --no-compile-claude) COMPILE_CLAUDE=false; shift ;;
        --marketplace-repo) MARKETPLACE_REPO="$2"; shift 2 ;;
        --marketplace-name) MARKETPLACE_NAME="$2"; shift 2 ;;
        --skip-marketplace-register) REGISTER_MARKETPLACE=false; shift ;;
        --agentic-packages) AGENTIC_PACKAGES_SOURCE="$2"; shift 2 ;;
        --apm-dependency) EXTRA_APM_DEPENDENCIES+=("$2"); shift 2 ;;
        --selected-bundle) SELECTED_BUNDLES+=("$2"); shift 2 ;;
        --selected-agent) SELECTED_AGENTS+=("$2"); shift 2 ;;
        --selected-skill) SELECTED_SKILLS+=("$2"); shift 2 ;;
        --selected-mcp) SELECTED_MCP+=("$2"); shift 2 ;;
        --lang)        OVERLAY_LANG="$2"; shift 2 ;;
        --lang-args)   LANG_ARGS="$2"; shift 2 ;;
        --quality-lang) QUALITY_LANGS+=("$2"); shift 2 ;;
        --help)
            sed -n '3,/^$/p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

if [ -z "$PROJECT_NAME" ]; then
    echo "Error: --name is required" >&2
    exit 1
fi

if [ -z "$ORG" ] && $CREATE_REPO; then
    echo "Error: --org is required (or use --no-repo)" >&2
    exit 1
fi

case "$LAYOUT" in
    single|monorepo) ;;
    *) echo "Error: --layout must be single or monorepo" >&2; exit 1 ;;
esac

case "$SPEC_MODE" in
    none|lightweight|full) ;;
    *) echo "Error: --spec-mode must be none, lightweight, or full" >&2; exit 1 ;;
esac

if $INIT_SPECKIT; then
    SPEC_MODE="full"
fi

# Resolve to absolute path
mkdir -p "$PROJECT_DIR"
PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"
cd "$PROJECT_DIR"

fail_if_codex_protected_paths_are_readonly

echo "=== Project Setup: $PROJECT_NAME ==="
echo "Directory: $PROJECT_DIR"

# --- Step 1: Git init ---
if $INIT_GIT; then
    if [ ! -d .git ]; then
        echo "Initializing git..."
        git init
    else
        echo "Git already initialized"
    fi
fi

# --- Step 2: GitHub repo ---
if $CREATE_REPO; then
    VISIBILITY="--private"
    $PUBLIC && VISIBILITY="--public"

    # Prefer the gh-api.py wrapper; fall back to plain gh when absent.
    GH_CMD=()
    if command -v gh-api.py >/dev/null 2>&1; then
        GH_CMD=(gh-api.py gh)
    elif [ -x "$AGENTIC_TOOLS_DIR/github/gh-api.py" ]; then
        GH_CMD=("$AGENTIC_TOOLS_DIR/github/gh-api.py" gh)
    elif command -v gh >/dev/null 2>&1; then
        GH_CMD=(gh)
    fi

    if [ "${#GH_CMD[@]}" -eq 0 ]; then
        echo "  WARN: neither gh-api.py nor gh found; skipping GitHub repo creation"
    elif "${GH_CMD[@]}" repo view "$ORG/$PROJECT_NAME" >/dev/null 2>&1; then
        echo "GitHub repo $ORG/$PROJECT_NAME already exists"
    else
        echo "Creating GitHub repo $ORG/$PROJECT_NAME..."
        DESC_FLAG=""
        [ -n "$DESCRIPTION" ] && DESC_FLAG="--description=$DESCRIPTION"
        "${GH_CMD[@]}" repo create "$ORG/$PROJECT_NAME" $VISIBILITY ${DESC_FLAG:+"$DESC_FLAG"} --source . --push=false \
            || echo "  WARN: GitHub repo creation failed; create $ORG/$PROJECT_NAME manually"
    fi

    # Ensure remote is set
    if ! git remote get-url origin >/dev/null 2>&1; then
        echo "Adding origin remote..."
        git remote add origin "https://github.com/$ORG/$PROJECT_NAME.git"
    fi
fi

# --- Step 3: Directory structure ---
echo "Creating directory structure..."
DIRS=(
    ".codex"
    ".agents/hooks"
    ".github/workflows"
    "docs/architecture"
    "docs/decisions"
    "docs/research"
    "docs/runbooks"
    "docs/product"
    "docs/engineering"
    "docs/operations"
    "docs/api"
    "specs"
    "infrastructure/environments"
    "infrastructure/terraform/modules"
    "infrastructure/terraform/stacks"
    "infrastructure/terraform/environments"
    "tests"
    "scripts"
    "assets"
    "archive"
)

if [ "$LAYOUT" = "monorepo" ] && [ "${#TARGETS[@]}" -eq 0 ]; then
    TARGETS=(
        "apps"
        "services"
        "functions"
        "workers"
        "libs/domain"
        "libs/application"
        "libs/adapters"
        "libs/config"
        "libs/testing"
        "libs/ui"
        "libs/types"
        "packages"
        "schemas"
        "data/shared"
        "tools"
    )
fi

for target in "${TARGETS[@]}"; do
    DIRS+=("$target")
done

for dir in "${DIRS[@]}"; do
    mkdir -p "$dir"
    [ -f "$dir/.gitkeep" ] || touch "$dir/.gitkeep"
done

# --- Step 3b: APM marketplace registration ---
if $REGISTER_MARKETPLACE; then
    if run_apm --version >/dev/null 2>&1; then
        SETUP_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
        APM_DISCOVER="$SETUP_SCRIPT_DIR/apm-discover.sh"
        if [ -x "$APM_DISCOVER" ]; then
            "$APM_DISCOVER"
        else
            echo "Registering/updating APM marketplace: $MARKETPLACE_NAME ($MARKETPLACE_REPO)"
            run_apm marketplace add "$MARKETPLACE_REPO" --name "$MARKETPLACE_NAME" || run_apm marketplace update "$MARKETPLACE_NAME" || true
            run_apm marketplace browse "$MARKETPLACE_NAME" || true
        fi
    else
        echo "  WARN: apm not found; install APM before using marketplace dependencies"
    fi
fi

if $USE_MISE && [ ! -f mise.toml ]; then
    echo "Creating mise.toml..."
    cat > mise.toml <<'MISE'
[tools]
jq = "latest"

[tasks]
MISE
fi

if $USE_MOON; then
    mkdir -p .moon
    if [ ! -f .moon/workspace.yml ]; then
        echo "Creating .moon/workspace.yml..."
        cat > .moon/workspace.yml <<'MOON'
projects:
  - "apps/*"
  - "services/*"
  - "functions/*/*"
  - "workers/*/*"
  - "libs/*"
  - "packages/*"
  - "tools/*"
MOON
    fi
fi

# --- Step 4: Clear macOS provenance xattr on .git/ ---
# macOS SIP applies com.apple.provenance to files created by sandboxed processes.
# This blocks git worktree operations (index.lock creation fails).
# Clearing upfront prevents issues when Claude Code uses worktrees later.
if [ -d .git ] && command -v xattr >/dev/null 2>&1; then
    echo "Clearing macOS provenance xattr on .git/..."
    sudo -n xattr -c -r .git/ 2>/dev/null || echo "  WARN: xattr clear failed — run 'sudo xattr -c -r .git/' manually if worktree git operations fail"
fi

# --- Step 5: Pre-commit config (universal hooks only) ---
if [ ! -f .pre-commit-config.yaml ]; then
    echo "Creating .pre-commit-config.yaml (universal hooks)..."
    cat > .pre-commit-config.yaml <<'PRECOMMIT'
exclude: '^(\.specify/|specs/)'

repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: check-added-large-files
      - id: check-json
      - id: check-toml
      - id: check-yaml
      - id: detect-private-key
      - id: end-of-file-fixer
      - id: trailing-whitespace

  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.24.3
    hooks:
      - id: gitleaks

  - repo: https://github.com/crate-ci/typos
    rev: v1.32.0
    hooks:
      - id: typos
        args: [--force-exclude]

  - repo: https://github.com/alexander-bauer/cocogitto-pre-commit
    rev: v0.1.0
    hooks:
      - id: cocogitto-verify
        stages: [commit-msg]
PRECOMMIT
else
    echo ".pre-commit-config.yaml already exists"
fi

# --- Step 6: Skeleton AGENTS.md files ---
if [ ! -f AGENTS.md ]; then
    echo "Creating skeleton AGENTS.md..."
    if [ "$LAYOUT" = "monorepo" ]; then
        cat > AGENTS.md <<'AGENTSMD'
# PROJECT_NAME

<!-- PROJECT DESCRIPTION: to be filled by agent -->

## Agent Guidance

<!-- CODEx/AGENTS GUIDANCE: to be filled by agent -->

## AGENTS Layering

- This root \`AGENTS.md\` applies to the whole repository unless a deeper file overrides it.
- Put repo-wide workflow, architecture, tool, and source-of-truth guidance here.
- Add nested \`AGENTS.md\` files only for subtrees that need materially different rules.
- Prefer subtree placement over invented path metadata.

## Codex Project Settings

- Project and subfolder Codex overrides live in `.codex/config.toml`.
- MCP servers for this repo or subtree should be declared under `mcp_servers.<name>` in `.codex/config.toml`.
- Keep repo-specific Codex settings here and leave user-global defaults in `~/.codex/config.toml`.

## Architecture

<!-- ARCHITECTURE: to be filled by agent based on project setup -->

## Monorepo Structure

| Path | Contents |
|------|----------|
| \`apps/\` | User-facing app surfaces |
| \`services/\` | Long-lived backend deployables |
| \`functions/\` | Serverless handlers, nested by platform |
| \`workers/\` | Background jobs and consumers, nested by platform |
| \`libs/\` | Internal shared code by architectural role |
| \`packages/\` | Published or independently versioned packages |
| \`schemas/\` | Shared/public contracts |
| \`data/\` | Shared data assets where no single owner exists |
| \`docs/\` | Project-wide documentation |
| \`specs/\` | Feature specifications |
| \`infrastructure/\` | Shared platform and IaC |
| \`tests/\` | Cross-package integration and E2E tests |
| \`tools/\` | Maintained CLIs, generators, and repo tooling |
| \`scripts/\` | Thin repo automation |
| \`assets/\` | Static files |
| \`archive/\` | Archived/superseded material |

## Packages

<!-- PACKAGES: to be filled as packages are added -->

## Build & Run

<!-- BUILD COMMANDS: to be filled by agent after language setup -->

## Repo

- **Branch strategy**: feature branches off main, squash merge
AGENTSMD
    else
        cat > AGENTS.md <<'AGENTSMD'
# PROJECT_NAME

<!-- PROJECT DESCRIPTION: to be filled by agent -->

## Agent Guidance

<!-- CODEX/AGENTS GUIDANCE: to be filled by agent -->

## AGENTS Layering

- This root \`AGENTS.md\` applies to the whole repository unless a deeper file overrides it.
- Put repo-wide workflow, architecture, tool, and source-of-truth guidance here.
- Add nested \`AGENTS.md\` files only for subtrees that need materially different rules.
- Prefer subtree placement over invented path metadata.

## Codex Project Settings

- Project and subfolder Codex overrides live in `.codex/config.toml`.
- MCP servers for this repo or subtree should be declared under `mcp_servers.<name>` in `.codex/config.toml`.
- Keep repo-specific Codex settings here and leave user-global defaults in `~/.codex/config.toml`.

## Architecture

<!-- ARCHITECTURE: to be filled by agent based on project setup -->

## Path Mapping

| Path | Contents |
|------|----------|
| \`api/contracts/\` | API contracts, OpenAPI fragments |
| \`docs/\` | Documentation, ADRs |
| \`specs/\` | Feature specifications (speckit) |
| \`research/\` | Technology decisions, alternatives analysis |
| \`infra/\` | Infrastructure config |
| \`tests/\` | Integration and E2E tests |
| \`scripts/\` | Build tooling, automation |
| \`assets/\` | Static files |

## Build & Run

<!-- BUILD COMMANDS: to be filled by agent after language setup -->

## Repo

- **GitHub**: ORG/PROJECT_NAME
- **Branch strategy**: feature branches off main, squash merge
AGENTSMD
    fi
else
    echo "AGENTS.md already exists"
fi

# APM owns scoped specs steering and Claude rules. Do not create specs/AGENTS.md
# or CLAUDE.md by default; they are generated only when explicitly requested by
# APM compile targets.

# --- Step 7: Project Codex config scaffold ---
mkdir -p .codex
if [ ! -f .codex/config.toml ]; then
    echo "Creating project-scoped .codex/config.toml..."
    cat > .codex/config.toml <<'CODEXCONFIG'
# Project or subfolder-scoped Codex overrides.
# Keep global defaults in ~/.codex/config.toml and place repo-specific
# overrides here when the repository needs different behavior.

# Example MCP server entry:
# [mcp_servers.context7]
# command = "npx"
# args = ["-y", "@upstash/context7-mcp"]

# Add project-local Codex settings below as needed.
CODEXCONFIG
else
    echo ".codex/config.toml already exists"
fi

# --- Step 8: Skeleton justfile ---
if $USE_JUST && [ ! -f justfile ]; then
    echo "Creating skeleton justfile..."
    cat > justfile <<'JUSTFILE'
default:
    @just --list

# Run tests
test:
    @echo "TODO: configure test command"

# Lint and format
lint:
    pre-commit run --all-files

# Build
build:
    @echo "TODO: configure build command"

# Start dev server
dev:
    @echo "TODO: configure dev command"

# Clean build artifacts
clean:
    @echo "TODO: configure clean command"
JUSTFILE
else
    $USE_JUST && echo "justfile already exists"
fi

# --- Step 9: License ---
if [ ! -f LICENSE ]; then
    echo "Creating LICENSE ($LICENSE)..."
    YEAR="$(date +%Y)"
    AUTHOR="$(git config user.name 2>/dev/null || echo 'AUTHOR')"
    case "$LICENSE" in
        apache-2.0|apache)
            cat > LICENSE <<APACHE
                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to the Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by the Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding any notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS

   Copyright $YEAR $AUTHOR

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
APACHE
            ;;
        mit)
            cat > LICENSE <<MIT_LICENSE
MIT License

Copyright (c) $YEAR $AUTHOR

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
MIT_LICENSE
            ;;
        *)
            echo "  WARN: Unknown license '$LICENSE' — skipping"
            ;;
    esac
else
    echo "LICENSE already exists"
fi

# --- Step 10: .gitignore (universal via gitnr) ---
if [ ! -f .gitignore ]; then
    write_minimal_gitignore() {
        echo "  WARN: creating minimal .gitignore"
        cat > .gitignore <<'GITIGNORE'
.DS_Store
Thumbs.db
.idea
.vscode/*
!.vscode/settings.json
!.vscode/tasks.json
!.vscode/launch.json
!.vscode/extensions.json
*~
*.bak
*.orig
*.tmp
GITIGNORE
    }

    echo "Creating .gitignore via gitnr..."
    if command -v gitnr >/dev/null 2>&1; then
        if ! gitnr create \
            ghg:macOS ghg:Linux ghg:Windows \
            ghg:JetBrains ghg:VisualStudioCode ghg:Vim \
            ghg:Backup ghg:Patch ghg:GPG \
            --save; then
            echo "  WARN: gitnr failed; falling back to minimal .gitignore"
            write_minimal_gitignore
        fi
    else
        echo "  WARN: gitnr not found"
        write_minimal_gitignore
    fi

    # Append project-specific entries not covered by gitnr templates
    cat >> .gitignore <<'CUSTOM'

# Environment
.env
.env.*
!.env.example

# Fastembed
.fastembed_cache

# Repomix local snapshots
repomix.xml
repomix.md
repomix.json
repomix.txt
CUSTOM
else
    echo ".gitignore already exists"
fi

if ! grep -q '^repomix\.xml$' .gitignore 2>/dev/null; then
    cat >> .gitignore <<'CUSTOM'

# Repomix local snapshots
repomix.xml
repomix.md
repomix.json
repomix.txt
CUSTOM
fi

# --- Step 10: Specify / Speckit ---
if [ "$SPEC_MODE" = "lightweight" ]; then
    echo "Spec mode: lightweight"
    mkdir -p specs
fi

if [ "$SPEC_MODE" = "full" ]; then
    # The speckit package owns the entire spec-kit setup flow (scaffold,
    # catalog, extensions, workflows) and its runtime orchestration. Install it
    # first, then delegate to its setup-speckit.sh. project-setup carries no
    # speckit logic of its own -- if the package can't be installed we hard-fail
    # rather than fall back to a divergent inline copy.
    if ! run_apm --version >/dev/null 2>&1; then
        echo "Error: --spec-mode full requires apm to install the speckit package" >&2
        echo "  Install apm, or rerun without --speckit / --spec-mode full." >&2
        exit 1
    fi

    echo "Installing speckit package (required for spec-mode full)..."
    if ! run_apm install --target claude,codex,agent-skills "speckit@${MARKETPLACE_NAME}"; then
        echo "Error: failed to install speckit@${MARKETPLACE_NAME}" >&2
        exit 1
    fi

    SETUP_SPECKIT="$(find apm_modules -path '*/speckit-setup/scripts/setup-speckit.sh' -print -quit 2>/dev/null || true)"
    if [ -z "$SETUP_SPECKIT" ] || [ ! -f "$SETUP_SPECKIT" ]; then
        echo "Error: speckit package installed but setup-speckit.sh not found under apm_modules" >&2
        exit 1
    fi

    # No --force: setup-speckit.sh skips re-scaffolding when .specify/ already
    # exists but still (idempotently) ensures extensions + workflows. This
    # matches the prior behaviour of only running `specify init` on a fresh dir.
    echo "Running speckit setup via the speckit package..."
    bash "$SETUP_SPECKIT" \
        --integration "$SPECKIT_INTEGRATION" \
        --script "$SPECKIT_SCRIPT_TYPE"
fi

# --- Step 10b: APM install / compile ---
find_agentic_script() {
    local script_name="$1"
    find apm_modules \( -path "*/skills/.apm/scripts/$script_name" -o -path "*/agentic-packages/.apm/scripts/$script_name" \) -print -quit 2>/dev/null || true
}

if $APM_INSTALL; then
    APM_PACKAGES=("$AGENTIC_PACKAGES_SOURCE")
    if [ "${#BASELINE_MCP_PACKAGES[@]}" -gt 0 ]; then
        APM_PACKAGES+=("${BASELINE_MCP_PACKAGES[@]}")
    fi
    # Qualify bare names from --selected-bundle / --selected-agent /
    # --selected-skill / --selected-mcp with @$MARKETPLACE_NAME. Callers may
    # also supply pre-qualified <name>@<marketplace> entries; preserve those
    # as-is. --apm-dependency keeps its existing pre-qualified contract.
    for _sel in "${SELECTED_BUNDLES[@]+"${SELECTED_BUNDLES[@]}"}" \
                "${SELECTED_AGENTS[@]+"${SELECTED_AGENTS[@]}"}" \
                "${SELECTED_SKILLS[@]+"${SELECTED_SKILLS[@]}"}" \
                "${SELECTED_MCP[@]+"${SELECTED_MCP[@]}"}"; do
        if [[ "$_sel" == *@* ]]; then
            APM_PACKAGES+=("$_sel")
        else
            APM_PACKAGES+=("${_sel}@${MARKETPLACE_NAME}")
        fi
    done
    if [ "${#EXTRA_APM_DEPENDENCIES[@]}" -gt 0 ]; then
        APM_PACKAGES+=("${EXTRA_APM_DEPENDENCIES[@]}")
    fi
    if run_apm --version >/dev/null 2>&1; then
        echo "Installing APM package primitives..."
        run_apm install --target claude,codex,agent-skills "${APM_PACKAGES[@]}"
    else
        echo "  WARN: apm not found; run 'apm install --target claude,codex,agent-skills ${APM_PACKAGES[*]}' manually"
    fi
fi

if $APM_COMPILE; then
    if run_apm --version >/dev/null 2>&1; then
        echo "Compiling Codex steering..."
        run_apm compile --target codex
        if $COMPILE_CLAUDE; then
            echo "Compiling Claude steering..."
            run_apm compile --target claude
        fi
    else
        echo "  WARN: apm not found; run 'apm compile --target codex' manually"
    fi
fi

if $APM_INSTALL; then
    if run_apm list 2>/dev/null | grep -q 'patch-agentic-tools'; then
        echo "Patching runtime agents..."
        run_apm run patch-agentic-tools
    else
        PATCH_SCRIPT="$(find_agentic_script patch-runtime-agents.py)"
        if [ -n "$PATCH_SCRIPT" ]; then
            echo "Patching runtime agents..."
            python3 "$PATCH_SCRIPT" --all
        else
            echo "  WARN: patch-runtime-agents.py not found under apm_modules"
        fi
    fi

    if run_apm list 2>/dev/null | grep -q 'audit-agentic-tools'; then
        echo "Auditing installed agentic assets..."
        run_apm run audit-agentic-tools
    else
        AUDIT_SCRIPT="$(find_agentic_script audit-agentic-assets.py)"
        if [ -n "$AUDIT_SCRIPT" ]; then
            echo "Auditing installed agentic assets..."
            python3 "$AUDIT_SCRIPT"
        else
            echo "  WARN: audit-agentic-assets.py not found under apm_modules"
        fi
    fi
fi

# --- Step 11: Language overlay ---
if [ -n "$OVERLAY_LANG" ]; then
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    LANG_SCRIPT="$SCRIPT_DIR/setup-${OVERLAY_LANG}.sh"

    if [ -x "$LANG_SCRIPT" ]; then
        echo ""
        echo "Running language overlay: setup-${OVERLAY_LANG}.sh..."
        # shellcheck disable=SC2086
        "$LANG_SCRIPT" $LANG_ARGS
    else
        echo "  WARN: $LANG_SCRIPT not found or not executable"
    fi
fi

if [ -n "$OVERLAY_LANG" ] && [ "${#QUALITY_LANGS[@]}" -eq 0 ]; then
    QUALITY_LANGS+=("$OVERLAY_LANG")
fi

if [ "${#QUALITY_LANGS[@]}" -gt 0 ]; then
    mkdir -p .agents/hooks
    printf '%s\n' "${QUALITY_LANGS[@]}" | sort -u > .agents/hooks/quality-languages
    echo "Configured agent quality hook languages: ${QUALITY_LANGS[*]}"
fi

echo ""
echo "=== Project setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Run/verify APM install and Codex compile if not already done"
echo "  2. Let the agent flesh out project-specific skeletons"
echo "  3. Make initial commit"
