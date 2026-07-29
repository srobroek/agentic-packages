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
default in 0.44.1 (`consent: never asked`), and `rtk telemetry disable` or
`RTK_TELEMETRY_DISABLED=1` keeps it off. Run `rtk-configure.py` to set
`tee.mode = "always"`, so a truncated-but-SUCCESSFUL command still leaves a
recovery log; the default covers only failures.

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

Expect a SMALL effect, measured by BYTES rather than by command count. On a
4,107-file repository's real history, the guard routes 3.6% of all `Bash` output
bytes. Attributing the rest:

| Share of Bash bytes | Reason it is out of reach |
| --- | --- |
| 76.7% | a tool rtk has no filter for (`wt`, `bd`, `jq`, `rg`, `head`, `python3`) |
| 10.3% | `;` chain with no routable segment |
| 3.8% | pipes into a parser |
| 3.6% | **routed today** |
| 3.1% | other |
| 2.2% | `&&` chain (exit-status control flow) |
| 0.3% | heredoc |

NOT Steer agents away from heredocs or chained commands to raise this. Fixing
  EVERY chain, heredoc, and parser pipe would lift rtk to 23.3% of Bash bytes at
  most, because the remaining 76.7% is tools it cannot filter at all. The top 20
  outputs by size are `head -100 <file>`, `wt list`, `bd ready --json`, `rg -rn`,
  and `python3` heredocs -- none of which rtk has a filter for. Steering would
  distort how agents work for a ceiling that is still under a quarter.
MUST Prefer the spill hook for output volume. It reaches 21.7% of ALL tool bytes
  without knowing which command produced them, which is why it covers the 76.7%
  rtk structurally cannot.

The hook also sees only `Bash`, so native `Read`, `Grep`, and `Glob` bypass it.

## Repository structure map, not a full pack

MUST Use the structure map to locate files, then read or search the file itself.
  A full `repomix` pack of a 741-file repository is 1,022,188 tokens; the
  `--no-files` map of the same repository is 6,093, a 168x reduction.
NOT Rely on `--compress` for a size win. Tree-sitter signature extraction
  removed 8% on source files and 1.4% repository-wide, because the bulk is test
  fixtures and cached artifacts.
DEFAULT `TOKEN_SAVINGS_MAP_BUDGET` (8000 tokens) decides inline versus pointer. A
  4,107-file repository maps to 31,299 tokens against 10,365,403 for a full pack
  of the same tree (331x), but 31k injected every session costs more than the
  exploration it saves, so over budget the hook names the file instead.

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
  2 KB is replaced by its first 20 and last 30 lines plus a path. The summary
  names the exact `rg`, `sed`, and `wc -l` invocations that recover any part of
  it, so retrieval needs no special tool and works under both runtimes even
  though the compression is Claude-only.
DEFAULT 2 KB with a 20/30-line window, tuned on 4,429 real tool results: it
  reaches 21.7% of all tool bytes. The window must shrink WITH the threshold --
  at 500 bytes, 1,069 spilled results fit entirely inside a 20/30 window, so the
  hook would rewrite them and hide nothing. A guard refuses any rewrite that
  would not shrink the result.
NOT Expect a failing command to be summarized. A nonzero exit is passed through
  whole, because the error text is the thing worth reading.

## Hook surface limit

A `PostToolUse` hook cannot compress tool output portably. Claude accepts
`updatedToolOutput`; Codex's `PostToolUse` wire struct has no such field and
rejects `updatedMCPToolOutput`, so it may only ADD context. Rewriting the
command in `PreToolUse` via `updatedInput` works on both.
