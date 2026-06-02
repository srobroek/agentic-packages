#!/usr/bin/env bash
# D2 diagram validation hook
# Checks for common issues after D2 file writes
# Triggered on Write/Edit of *.d2 files

set -euo pipefail

FILE="${CLAUDE_FILE:-}"
if [[ -z "$FILE" || ! "$FILE" == *.d2 ]]; then
  exit 0
fi

if [[ ! -f "$FILE" ]]; then
  exit 0
fi

WARNINGS=""

# Check for custom colors when theme should handle them
if grep -qE 'style\.(fill|font-color|stroke):.*"#' "$FILE" 2>/dev/null; then
  COLOR_COUNT=$(grep -cE 'style\.(fill|font-color|stroke):.*"#' "$FILE" 2>/dev/null || echo "0")
  if [[ "$COLOR_COUNT" -gt 0 ]]; then
    WARNINGS="${WARNINGS}D2 Quality: Found ${COLOR_COUNT} custom color declarations. Consider using a D2 theme instead (--theme N) for consistent contrast. Custom colors may conflict with theme handling.\n"
  fi
fi

# Check for dark backgrounds with potentially unreadable text
if grep -qE 'fill:.*"#[0-4]' "$FILE" 2>/dev/null; then
  WARNINGS="${WARNINGS}D2 Quality: Dark fill colors detected. Ensure text contrast is sufficient (light text on dark backgrounds).\n"
fi

# Check for missing direction
if ! grep -q '^direction:' "$FILE" 2>/dev/null; then
  WARNINGS="${WARNINGS}D2 Quality: No 'direction:' set. Consider adding 'direction: right' (ER/architecture) or 'direction: down' (flowcharts).\n"
fi

# Check for very large diagrams without elk layout
NODE_COUNT=$(grep -cE '^\s*\w+:.*\{' "$FILE" 2>/dev/null || echo "0")
if [[ "$NODE_COUNT" -gt 20 ]]; then
  if ! grep -q 'layout-engine: elk' "$FILE" 2>/dev/null; then
    WARNINGS="${WARNINGS}D2 Quality: ${NODE_COUNT} nodes detected. Consider using ELK layout (layout-engine: elk) for better edge routing in complex diagrams.\n"
  fi
fi

# Check for font-size overrides (theme should handle)
if grep -qE 'font-size:' "$FILE" 2>/dev/null; then
  WARNINGS="${WARNINGS}D2 Quality: Custom font-size detected. D2 themes handle font sizes -- custom overrides may conflict.\n"
fi

if [[ -n "$WARNINGS" ]]; then
  echo -e "$WARNINGS"
fi
