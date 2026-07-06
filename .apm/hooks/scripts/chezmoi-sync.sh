#!/bin/bash
# Advisory chezmoi hook (PostToolUse: Edit, Write, MultiEdit).
#
# ADVISORY ONLY -- this hook performs NO git operations and NO `chezmoi add`.
# It never commits, never pushes, never stages. Its entire job is to tell the
# AGENT when an edit touches chezmoi-managed state, and to surface what is
# pending in the chezmoi source repo so the agent can commit/push DELIBERATELY
# on its own branch. Automatic commit+push used to fight deliberate branch work
# and `git add -A` could sweep unrelated changes into a commit; both are gone.

# Read JSON from stdin and extract file_path
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

HOME_DIR="$HOME"

# Exit if no file provided or doesn't exist
[ -z "$FILE" ] && exit 0
[ ! -f "$FILE" ] && exit 0

# Resolve to absolute path
FILE="$(cd "$(dirname "$FILE")" && pwd)/$(basename "$FILE")"

# Fast exit: only process files under $HOME, excluding project dirs
case "$FILE" in
    "$HOME_DIR/personal/"*|"$HOME_DIR/work/"*|"$HOME_DIR/Projects/"*)
        exit 0 ;; # project files, not chezmoi-managed
    "$HOME_DIR/"*)
        ;; # home directory file, may be chezmoi-managed -- continue
    *)
        exit 0 ;; # outside home entirely, skip
esac

CHEZMOI_SOURCE="$(chezmoi source-path 2>/dev/null)"
[ -z "$CHEZMOI_SOURCE" ] && exit 0

# Check if file is in ~/.config or is a dot file/directory in ~
is_config_file() {
    local file="$1"

    # Check if in ~/.config
    if [[ "$file" == "$HOME_DIR/.config/"* ]]; then
        return 0
    fi

    # Check if it's a dot file directly in ~ (not in subdirectory)
    local relative="${file#$HOME_DIR/}"
    if [[ "$relative" == .* ]] && [[ "$relative" != */* ]]; then
        return 0
    fi

    # Check if it's inside a dot directory directly in ~
    if [[ "$relative" == .*//* ]]; then
        local top_dir="${relative%%/*}"
        if [[ "$top_dir" == .* ]]; then
            return 0
        fi
    fi

    return 1
}

# Ignore common non-config dot files/directories
is_ignored() {
    local file="$1"
    local relative="${file#$HOME_DIR/}"

    # Get top-level directory or file name
    local top="${relative%%/*}"

    # Ignore chezmoi source directory itself
    if [[ "$file" == "$CHEZMOI_SOURCE"* ]]; then
        return 0
    fi

    # Common ignored patterns
    case "$top" in
        .Trash|.cache)
            return 0
            ;;
        .npm|.pnpm|.bun|.cargo/registry|.cargo/git)
            return 0
            ;;
        .node_modules|node_modules)
            return 0
            ;;
        .DS_Store|.localized|.CFUserTextEncoding)
            return 0
            ;;
        .zsh_history|.bash_history|.fish_history|.python_history)
            return 0
            ;;
        .lesshst|.wget-hsts|.viminfo)
            return 0
            ;;
        .Spotlight-V100|.fseventsd|.TemporaryItems)
            return 0
            ;;
        .cups|.dropbox|.gradle|.m2|.ivy2)
            return 0
            ;;
    esac

    # Ignore .local entirely (state, cache, share - including chezmoi source)
    if [[ "$relative" == ".local/"* ]]; then
        return 0
    fi

    # Ignore lock files and temp files
    case "$file" in
        *.lock|*.swp|*.swo|*~|*.bak|*.tmp)
            return 0
            ;;
    esac

    return 1
}

# Check if file is in chezmoi source (already managed)
get_chezmoi_source_path() {
    local file="$1"
    chezmoi source-path "$file" 2>/dev/null
}

# Check if the source file is a template
is_template() {
    local source_path="$1"
    if [[ "$source_path" == *.tmpl ]]; then
        return 0
    fi
    return 1
}

# Read-only: show what is currently uncommitted in the chezmoi source repo, so
# the agent knows exactly what a deliberate commit would include. NO staging,
# NO commit, NO push -- `git status` is inspection only. `git -C` avoids any
# `cd` side effect on the caller.
chezmoi_pending_advisory() {
    local repo="$CHEZMOI_SOURCE"
    # chezmoi source-path points at the source dir; the git repo is its root.
    git -C "$repo" rev-parse --git-dir >/dev/null 2>&1 || return 0
    local pending
    pending="$(git -C "$repo" status --short 2>/dev/null)"
    [ -z "$pending" ] && return 0
    cat << EOF
<chezmoi-commit-advisory>
Your edit changed chezmoi-managed dotfile state. This hook does NOT auto-commit
or auto-push -- you must handle it deliberately.

CHEZMOI SOURCE REPO: $repo

Uncommitted changes there right now (git status --short):
$pending

ACTION (when your current task is at a commit point):
  1. cd "$repo"  (or use git -C "$repo")
  2. Review: git -C "$repo" diff
  3. Stage ONLY the files you intend (never git add -A -- other unrelated
     dotfile changes may be pending, as shown above).
  4. Commit on an appropriate branch, then push deliberately (dgit for github.com).
Do this yourself; nothing is committed or pushed automatically.
</chezmoi-commit-advisory>
EOF
}

# Main logic
main() {
    # Direct edit to a chezmoi source file -- advise, show pending, do NOT commit.
    if [[ "$FILE" == "$CHEZMOI_SOURCE"* ]] || [[ "$FILE" == "$HOME_DIR/.local/share/chezmoi/"* ]]; then
        chezmoi_pending_advisory
        exit 0
    fi

    # Skip if not a config file
    if ! is_config_file "$FILE"; then
        exit 0
    fi

    # Skip if ignored
    if is_ignored "$FILE"; then
        exit 0
    fi

    # Check if file is tracked in chezmoi
    local source_path
    source_path=$(get_chezmoi_source_path "$FILE")

    if [ -n "$source_path" ] && [ -f "$source_path" ]; then
        # File is tracked in chezmoi
        if is_template "$source_path"; then
            # It's a template - editing the applied target is futile.
            cat << EOF
<chezmoi-template-warning>
STOP: This file is managed by chezmoi as a template.

TARGET_FILE: $FILE
TEMPLATE_FILE: $source_path

ACTION REQUIRED:
1. Your changes to $FILE will be OVERWRITTEN by chezmoi
2. Instead, edit the template: $source_path
3. Apply the same logical changes to the template file
4. After editing the template, run: chezmoi apply --include=$FILE

Do NOT continue editing the target file. Edit the template file instead.
</chezmoi-template-warning>
EOF
            exit 0
        else
            # Tracked non-template target: the edit landed on the applied copy,
            # not the source. Advise re-adding into source -- do NOT run it.
            cat << EOF
<chezmoi-readd-advisory>
This file is tracked by chezmoi; you edited the APPLIED target, not the source.

TARGET_FILE: $FILE
SOURCE_FILE: $source_path

To fold your change back into the source of truth (nothing is done for you):
  chezmoi re-add "$FILE"      # or edit $source_path directly
Then review/commit/push the chezmoi source repo deliberately (see below if pending).
EOF
            chezmoi_pending_advisory
            exit 0
        fi
    else
        # File not tracked - suggest adding if it looks like a config
        local basename
        basename=$(basename "$FILE")

        # Only suggest for likely config files
        case "$basename" in
            *.conf|*.config|*.cfg|*.ini|*.toml|*.yaml|*.yml|*.json|config|settings*)
                echo "💡 Config file not tracked by chezmoi: $FILE"
                echo "   To add: chezmoi add \"$FILE\""
                ;;
            .*rc|.*profile|.*env|.gitconfig|.gitignore)
                echo "💡 Config file not tracked by chezmoi: $FILE"
                echo "   To add: chezmoi add \"$FILE\""
                ;;
        esac
    fi
}

main
exit 0
