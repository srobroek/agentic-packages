---
x-lint:
  allow: [prose-format.ProseBlock]
  reason: "the rule bodies are MUST/NOT directives carrying the measurement that justifies each one; splitting the evidence away from its rule is what makes a rule get ignored"
---

# Token savings

Context-cost reduction, and how to tell whether a reduction is real. Every
figure here was measured on this machine rather than taken from a tool's README.

## Measure before believing

MUST Judge a token-saving change with `tokenmeter.py` (this package's skill),
  which reads the `usage` block the API returned per turn. A tool's self-report
  is not evidence: `rtk gain` estimates tokens as `bytes / 4` with no tokenizer,
  and compares its own captured output against its own filtered output for the
  same run, so it cannot see a follow-up command caused by over-filtering.
MUST Judge compression on `cost_weighted`, not `input_tokens`. Cache reads bill
  below fresh input but not at zero, and they dominate: a measured session showed
  279 input tokens against 14.2M cache reads.
MUST Count subagent cost. Orchestration relocates cost rather than removing it.
MUST Require 3+ runs per arm and separated per-run ranges. Agent runs are
  nondeterministic; a two-run A/B measures variance.
NOT Trust `rtk session` adoption percentages. It reported 54% adoption for a
  session that had used rtk in 8 of 74 shell calls, while `rtk discover` reported
  27 rtk commands across all history.

## Prompt caching is the largest existing lever

MUST Preserve the stable prompt prefix. Savings under Claude come mostly from
  cache hits, so a change that rewrites conversation history fights the biggest
  free lever available. A proxy-based compressor (headroom, tamp) rewrites that
  history; headroom issue #2438 measures a 2-7x cost INCREASE from defeating
  caching in both of its modes.
NOT Chain two lossy rewriters. Run at most one.

## rtk: allowlist, never blanket rewrite

`rtk` filters command output. It is installed by mise; telemetry is OFF by
default in 0.43.0 (`consent: never asked`), and `rtk telemetry disable` or
`RTK_TELEMETRY_DISABLED=1` keeps it off.

MUST Route only commands whose filtered output was verified to be a faithful,
  shorter rendering. This package's `rtk-rewrite-guard.py` holds the allowlist.
NOT Install `rtk hook claude` (rtk's own blanket PreToolUse handler). Measured on
  0.43.0 it rewrites machine-parsed commands: `rtk git status --porcelain` drops
  the TRAILING NEWLINE, so `| wc -l` under-counts by one, and `rtk grep` returned
  25 of 400 matching lines. Both are correct for a model reading output and wrong
  for a parsed pipeline, and rtk cannot distinguish them because the difference
  is in the caller's intent.
NOT Route `curl` through rtk for HTML. It is JSON-oriented and passed an 89 KB
  page through byte for byte.

Expect a SMALL effect, and do not let the allowlist imply otherwise. Replaying
24,725 real `Bash` calls from local transcripts, 94% contain a pipe, redirect,
chain, or command substitution, and the guard refuses every one of those because
a filtered rendering feeding another process can change a result. Of the 1,161
distinct non-pipeline commands, the guard routes 26. The hook also sees only
`Bash`, so native `Read`, `Grep`, and `Glob` bypass it entirely.

That measurement is the reason to keep the guard narrow rather than to widen it:
the commands rtk could additionally reach are the compound ones where filtering
is unsafe.

## Repository structure map, not a full pack

MUST Use the structure map to locate files, then read or search the file itself.
  A full `repomix` pack of a 741-file repository is 1,022,188 tokens; the
  `--no-files` map of the same repository is 6,093, a 168x reduction.
NOT Rely on `--compress` for a size win. Tree-sitter signature extraction
  removed 8% on source files and 1.4% repository-wide, because the bulk is test
  fixtures and cached artifacts.
DEFAULT `TOKEN_SAVINGS_MAP_BUDGET` (8000 tokens) decides inline versus pointer. A
  large repository maps to ~31k tokens, which costs more injected every session
  than the exploration it saves.

## Web content

MUST Prefer the fetcher MCP for pages. It already runs Readability and returns
  markdown, measured at 89% smaller than raw HTML, so the compression is present
  rather than missing. `trafilatura --markdown` reached 93% when a CLI is wanted.
MUST Drive the browser through `playwright-cli` rather than the MCP server for
  scripted flows and verification. The CLI writes the accessibility snapshot to a
  file and returns its path, measured at 402 bytes against 33,011 that the MCP
  server inlines for the same page, and it still clicks, fills, uploads, and
  keeps state across invocations. Reserve the MCP server for loops that need the
  model reasoning over page structure turn by turn (exploratory automation,
  self-healing tests). See the `playwright` skill for the routing table.
NOT Pass `--snapshot-mode none` to shrink the MCP server. Element refs come from
  snapshots, so it removes the ability to interact and leaves an interface that
  can only look.

## Oversized tool output goes to disk

MUST Read the spill file rather than re-running the command. A `Bash` result over
  12 KB is replaced by its first 40 and last 60 lines plus a path, measured at
  80% smaller on a 24 KB test dump. The summary names the exact `rg`, `sed`, and
  `wc -l` invocations that recover any part of it, so retrieval needs no special
  tool and works under both runtimes even though the compression is Claude-only.
NOT Expect a failing command to be summarized. A nonzero exit is passed through
  whole, because the error text is the thing worth reading.

## Hook surface limit

A `PostToolUse` hook cannot compress tool output portably. Claude accepts
`updatedToolOutput`; Codex's `PostToolUse` wire struct has no such field and
rejects `updatedMCPToolOutput`, so it may only ADD context. Rewriting the
command in `PreToolUse` via `updatedInput` works on both.
