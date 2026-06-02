#!/usr/bin/env bash
# Hook: SessionStart -- clean build artifacts from orphaned worktrees
# async: true -- runs in background, doesn't block session startup
#
# Worktree naming convention: /tmp/claude-worktrees/{repo}/worktree-{PID}
# A worktree is orphaned when its PID is no longer running.
# Only cleans build artifacts (target/, node_modules/, .venv/, etc.),
# does NOT remove the worktree directory itself (git worktree prune handles that).

INPUT=$(cat)
AGENT_ID=$(echo "$INPUT" | jq -r '.agent_id // empty')
[ -n "$AGENT_ID" ] && exit 0  # Skip in subagents

WORKTREE_BASE="/tmp/claude-worktrees"
[ -d "$WORKTREE_BASE" ] || exit 0

# Also check /private/tmp (macOS symlink)
for base in "$WORKTREE_BASE" "/private$WORKTREE_BASE"; do
    [ -d "$base" ] || continue

    for worktree in "$base"/*/worktree-*; do
        [ -d "$worktree" ] || continue

        # Extract PID from directory name (worktree-{PID})
        dirname=$(basename "$worktree")
        pid="${dirname#worktree-}"

        # Skip if PID is not numeric
        [[ "$pid" =~ ^[0-9]+$ ]] || continue

        # Skip if PID is still running (active session)
        if kill -0 "$pid" 2>/dev/null; then
            continue
        fi

        # PID is dead -- this worktree is orphaned. Clean build artifacts.

        # Rust
        if [ -f "$worktree/Cargo.toml" ]; then
            cargo clean --manifest-path "$worktree/Cargo.toml" 2>/dev/null
        fi

        # Node (top-level and nested workspaces)
        for nm in "$worktree"/node_modules "$worktree"/*/node_modules; do
            [ -d "$nm" ] && rm -r "$nm" 2>/dev/null
        done

        # Python
        [ -d "$worktree/.venv" ] && rm -r "$worktree/.venv" 2>/dev/null
        find "$worktree" -type d -name __pycache__ -exec rm -r {} + 2>/dev/null

        # Go
        [ -f "$worktree/go.mod" ] && (cd "$worktree" && go clean -cache 2>/dev/null)

        # .NET
        if [ -d "$worktree/bin" ] && [ -d "$worktree/obj" ]; then
            rm -r "$worktree/bin" "$worktree/obj" 2>/dev/null
        fi

        # Java/Kotlin (Gradle)
        if [ -d "$worktree/build" ] && { [ -f "$worktree/build.gradle" ] || [ -f "$worktree/build.gradle.kts" ]; }; then
            rm -r "$worktree/build" 2>/dev/null
        fi

        # Java (Maven)
        if [ -d "$worktree/target" ] && [ -f "$worktree/pom.xml" ]; then
            rm -r "$worktree/target" 2>/dev/null
        fi

        # Swift
        if [ -d "$worktree/.build" ] && [ -f "$worktree/Package.swift" ]; then
            rm -r "$worktree/.build" 2>/dev/null
        fi
    done

    # Break after first match to avoid processing /tmp and /private/tmp twice
    break
done

exit 0
