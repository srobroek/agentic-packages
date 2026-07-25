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
| Data extraction | snapshot (structured accessibility data, fast), screenshot (visual, slow), evaluate JS |
| Tabs | open, close, list, switch |
| Diagnostics | console messages, network requests |

## Common Workflows

**Extract information**: navigate -> wait -> snapshot -> parse -> return findings

**Fill and submit form**: navigate -> fill each field -> click submit -> wait -> snapshot to verify

**Search and extract**: navigate -> fill search query -> press Enter or click search -> wait -> snapshot results

## Rules

- Snapshot by default; screenshot only when the check is visual
- Get all data from one page load before navigating elsewhere; batch navigate -> snapshot -> extract
- Use specific selectors (`button[data-testid='submit']`) over vague text matching
- Report findings concisely; do not dump raw HTML
- When extraction stalls, report what was tried and the page state rather than re-trying the same call
- If a page requires login, ask the user for credentials or an alternative approach
