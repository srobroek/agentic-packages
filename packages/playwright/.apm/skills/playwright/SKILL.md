---
name: playwright
description: Use when automating browser tasks — navigate, click, fill forms, and test web interfaces via Playwright MCP tooling.
---

# Playwright Browser Automation

Automate browser tasks using a Playwright MCP server.

## Available Operations

| Category | Operations |
|----------|-----------|
| Navigation | navigate to URL, go back/forward, wait for load |
| Interaction | click, fill inputs, select dropdowns, hover, press keys, drag, file upload |
| Data extraction | snapshot (structured, fast), screenshot (visual, slow), evaluate JS |
| Tabs | open, close, list, switch |
| Diagnostics | console messages, network requests |

## Common Workflows

**Extract information**: navigate -> wait -> snapshot -> parse -> return findings

**Fill and submit form**: navigate -> fill each field -> click submit -> wait -> snapshot to verify

**Search and extract**: navigate -> fill search query -> press Enter or click search -> wait -> snapshot results

## Error Handling

- **Timeout**: increase wait time or verify page loaded
- **Element not found**: verify selector, page structure may have changed
- **Navigation failed**: check URL, may need authentication

If after 3 attempts the agent cannot get the information: report what was tried, suggest alternatives, ask the user for guidance.

## Rules

- Use snapshots, not screenshots -- snapshots return structured accessibility data fast; take a screenshot only when visual verification is needed
- Get all data from one page load before navigating elsewhere; batch navigate -> snapshot -> extract
- Use specific selectors (`button[data-testid='submit']`) over vague text matching
- Close the browser when done
- Report findings concisely; do not dump raw HTML
- If a page requires login, ask the user for credentials or an alternative approach
