---
name: web-fetch
description: Use when information must be retrieved from the web or a specific URL.
---

# Web Fetch

Use this skill when information must be fetched from the web.

## Tool Selection

| Need | Tool |
|------|------|
| GitHub data | `gh` CLI |
| Known REST API | `curl` |
| Library docs | context7 MCP |
| Static webpage | Simple web fetch |
| JS-heavy / fetch fails | Rich fetch with browser rendering |

## Rules

- Prefer official sources for product or API questions.
- Start with the lowest-overhead fetch path.
- On 403 or bot-block from simple fetch, retry with richer fetch immediately.
- Summarize results scoped to the user question. Do not dump raw content.

## References

- Read `references/tool-selection.md` for detailed fetch tool comparison and options
