#!/bin/bash
# Claude Code notification script
# Sends macOS notification that opens the terminal when clicked
# Only notifies when the terminal is NOT in the foreground
# No-op on Linux — notifications are macOS-only

# No-op on Linux
[ "$(uname)" != "Darwin" ] && exit 0

# Read JSON input from stdin (Claude Code passes notification data this way)
INPUT=$(cat)

# Parse JSON fields using jq
MESSAGE=$(echo "$INPUT" | jq -r '.message // empty')
TITLE=$(echo "$INPUT" | jq -r '.title // empty')
NOTIFICATION_TYPE=$(echo "$INPUT" | jq -r '.notification_type // empty')

# Fallback to environment variable or default
MESSAGE="${MESSAGE:-${CLAUDE_NOTIFICATION_TITLE:-Needs attention}}"

# Use __CFBundleIdentifier if available (set by macOS for GUI apps)
if [[ -n "$__CFBundleIdentifier" ]]; then
    BUNDLE_ID="$__CFBundleIdentifier"
else
    # Fallback: determine bundle ID based on terminal
    case "${TERM_PROGRAM:-}" in
        zed)
            BUNDLE_ID="dev.zed.Zed"
            ;;
        ghostty)
            BUNDLE_ID="com.mitchellh.ghostty"
            ;;
        WezTerm)
            BUNDLE_ID="com.github.wez.wezterm"
            ;;
        iTerm.app)
            BUNDLE_ID="com.googlecode.iterm2"
            ;;
        Apple_Terminal)
            BUNDLE_ID="com.apple.Terminal"
            ;;
        vscode)
            BUNDLE_ID="com.microsoft.VSCode"
            ;;
        *)
            BUNDLE_ID=""
            ;;
    esac
fi

# Check if the SAME terminal running Claude is in foreground - skip notification if so
# Only suppress for the exact app running Claude, not all terminals/IDEs
FRONTMOST=$(osascript -e 'tell application "System Events" to get bundle identifier of first process whose frontmost is true' 2>/dev/null)

if [[ -n "$BUNDLE_ID" && "$FRONTMOST" == "$BUNDLE_ID" ]]; then
    exit 0
fi

# Get app name for subtitle
APP_NAME="${TERM_PROGRAM:-Terminal}"
[[ "$__CFBundleIdentifier" == *"-Preview"* ]] && APP_NAME="$APP_NAME Preview"

# Build subtitle with notification type if available
SUBTITLE="$APP_NAME"
[[ -n "$TITLE" ]] && SUBTITLE="$APP_NAME · $TITLE"

# Build the terminal-notifier command
ARGS=(
    -title "Claude Code"
    -subtitle "$SUBTITLE"
    -message "$MESSAGE"
    -sound default
    -group "claude-code-$(date +%s%N)"
)

# Add activate flag if we know the bundle ID
if [[ -n "$BUNDLE_ID" ]]; then
    ARGS+=(-activate "$BUNDLE_ID")
fi

terminal-notifier "${ARGS[@]}"
