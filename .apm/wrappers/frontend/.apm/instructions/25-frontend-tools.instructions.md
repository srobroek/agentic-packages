---
description: Frontend tool routing including Playwright browser automation
applyTo: "**/*"
---

## Browser Testing — Playwright MCP

Use Playwright MCP for:
- Visual verification of UI changes (navigate, snapshot, screenshot)
- Form interaction testing (fill, click, select)
- Responsive design checks (browser_resize)
- Console error detection (browser_console_messages)
- Network request verification (browser_network_requests)

Workflow: start dev server → navigate to page → verify with snapshot/screenshot.

Always verify UI changes in the browser before reporting completion.

## Do NOT Use Playwright For

- API testing — use curl or fetch via terminal
- Static analysis — use TypeScript compiler, ESLint via terminal
- Component unit tests — use test runner directly
- Performance benchmarks — use lighthouse CLI
