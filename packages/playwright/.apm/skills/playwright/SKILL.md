---
name: playwright
description: Use when automating a browser (navigate, click, fill forms, verify UI). Routes to the token-cheap CLI or the stateful MCP server.
---

# Playwright browser automation

The CLI and the MCP server reach the same Playwright engine and differ by two
orders of magnitude in context cost. Pick deliberately.

Measured on the same docs page: `playwright-cli goto` returned **402 bytes**
because it writes the accessibility snapshot to a file and hands back a path,
where the MCP `browser_navigate` inlines the tree, **33,011 bytes** for that
page. The snapshot is not lost; it is on disk, greppable, and `find` searches it
for a fraction of the cost of reading it.

Both interfaces do the full range of interaction: click, type, fill, check,
select, drag, upload, dialogs, key presses. The CLI keeps browser state across
separate invocations, so a multi-step flow works without a resident session.

## Route by task

MUST Default to the CLI (`playwright-cli`) for anything that reads a page,
  drives a scripted flow, or verifies a result. That covers most testing.

MUST Use the MCP server when the loop needs the model to reason over page
  structure turn by turn: exploratory automation with no known selectors,
  self-healing a test whose targets moved, or a long autonomous session where
  losing the page context between calls would cost more than the snapshot does.
  Upstream states this split directly, and it is the one case where paying for
  the inlined tree is correct.

NOT Reach for the MCP server merely because a task involves clicking. The CLI
  clicks. The distinction is whether the MODEL needs the whole tree in context,
  not whether the task changes the page.

## CLI

```bash
playwright-cli open https://example.test          # or `goto` on an open browser
playwright-cli find "Sign in"                     # search the snapshot, get a ref
playwright-cli click e21                          # act on the ref
playwright-cli fill e8 "buy milk"
playwright-cli snapshot                           # writes a file, returns the path
playwright-cli eval "() => document.title"
playwright-cli close
```

MUST Locate elements with `find` rather than a full `snapshot`. `find` returns
  matching nodes with surrounding context and their refs, which is what a click
  needs; a full snapshot returns the page.

MUST Read the written snapshot with `rg` when a broad question needs it. The
  path is in the command's output. Reading the whole file back into context
  discards the reason for using the CLI.

DEFAULT Headless. Pass `--headed` to `open` to watch it.

DEFAULT One session. `-s=<name>` runs an independent browser, and
  `PLAYWRIGHT_CLI_SESSION` sets it for a whole agent run. `--persistent` keeps
  the profile on disk across browser restarts.

Install with `npm install -g @playwright/cli@latest`, and
`playwright-cli install --skills` to register its own skill files. With neither,
`playwright-cli --help` is self-describing.

## MCP

Available when installed by `mcp-playwright`. Do not pass `--snapshot-mode none`
to shrink it: refs come from snapshots, so that flag removes the ability to click
anything and leaves an interface that can only look.

MUST Prefer `browser_find` over `browser_snapshot` to locate a node, then a
  depth-limited `browser_snapshot` if more structure is genuinely needed.
MUST Prefer `browser_snapshot` over `browser_take_screenshot` unless the check is
  visual. A screenshot costs image tokens and cannot be searched.

## Rules for both

MUST Batch per page load: navigate once, then extract everything that page
  answers before moving on.
MUST Target elements by ref or a stable selector (`button[data-testid=submit]`)
  rather than vague text.
MUST Report findings, not raw page data.
NOT Re-issue an identical failing call. Report what was tried and the page state.
NOT Guess credentials. Ask for them or for another route.
