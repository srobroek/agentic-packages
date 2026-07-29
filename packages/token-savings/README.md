# token-savings

Context-cost reduction for Claude Code and Codex, plus the instrument that
decides whether a reduction happened.

Every figure below was measured locally. Where a tool's own numbers disagree
with what was measured, the measurement is reported and the tool's claim is
named as a claim.

## What it installs

| Client | Event | Matcher | Command |
| --- | --- | --- | --- |
| Both | `PreToolUse` | `Bash` | `rtk-rewrite-guard.py`, `repomix-read-guard.py` |
| Both | `PreToolUse` | `Read` | `repomix-read-guard.py` |
| Claude Code | `PostToolUse` | `Bash` | `spill-tool-output.py` |
| Claude Code | `PostToolUse` | `Read` | `read-truncation-notice.py` |

The `PostToolUse` spill hook is Claude-only: Codex's `PostToolUse` wire struct
carries no `updatedToolOutput`, so it cannot rewrite a tool result. Retrieval from
a spill file is plain Bash, so the recovery half works on both.

`rtk` and `repomix` are optional; without them every hook exits 0 with no output.
`python3` is required. Nothing here generates a repomix pack: that is `repomix`
reading a committed `repomix.config.json`, invoked by `wt post-start` or by hand.
The package filters, spills, guards, and measures.

## The measurement instrument

`tokenmeter.py` reads the `usage` block the API returned on each assistant turn
from the transcript JSONL, including the per-subagent `.output` transcripts.

```bash
python3 .apm/skills/token-savings/scripts/tokenmeter.py measure <transcript.jsonl>
python3 .apm/skills/token-savings/scripts/tokenmeter.py compare --markdown \
  --baseline runs/off/ --treatment runs/on/
```

`compare` reports per-metric medians, per-run ranges, and whether the arms'
ranges separate. It refuses a confident verdict below three runs per arm, and
warns when turn count rises even if tokens fell.

These two choices come from measurements that would otherwise mislead:

- **`cost_weighted`, not `input_tokens`.** Across 23 local sessions, 97.5% of
  input-side tokens were cache reads and fresh input was 0.00%. Cache reads bill
  below fresh input but not at zero, so a tool judged on `input_tokens` looks
  transformative while changing nothing.
- **Subagents count.** One session attributed 45 subagents and 92 turns that a
  main-thread-only reading missed entirely. Orchestration relocates cost.

Self-reported savings are excluded on purpose. `rtk gain` estimates tokens as
`bytes / 4` with no tokenizer and compares its own captured output against its
own filtered output for the same run, so it cannot observe a follow-up command
caused by over-filtering. `rtk session` reported 54% adoption for a session that
had used rtk in 8 of its 74 shell calls.

## rtk routing

The `PreToolUse` guard prefixes `rtk` onto commands on an allowlist, at the
command position so a leading `FOO=1` stays environment for the target rather
than an argument to rtk.

Every allowlist entry was verified by running the command twice, natively and
through rtk, and diffing what survived. `rtk-verify.py` in the skill re-runs that
sweep against whatever rtk version is installed:

```bash
python3 .apm/skills/token-savings/scripts/rtk-verify.py --markdown
```

Verified on rtk 0.44.1. `| tail -50` is the idiom the agent uses today and is the
honest competing baseline, so it is reported alongside:

| Command | Native | rtk | `\| tail -50` | Saved | Verdict |
| --- | --- | --- | --- | --- | --- |
| `pytest` (30 passing) | 464 | 18 | 464 | 96% | routed |
| `grep -n` (400 matches) | 17384 | 1173 | 2200 | 93% | routed, recoverable |
| `cargo test` (failing) | 379 | 38 | 264 | 90% | routed |
| `cargo clippy` (warnings) | 684 | 88 | 567 | 87% | routed |
| `ls -la` | 459 | 66 | 459 | 86% | routed |
| `pytest` (30 failing) | 11450 | 1823 | 3026 | 84% | routed, recoverable |
| `wc -l` | 15 | 4 | 15 | 73% | routed |
| `ruff check` | 761 | 395 | 761 | 48% | routed |
| `cargo build` | 188 | 100 | 72 | 47% | routed |
| `uv run pytest` (failing) | 11418 | 6377 | 3026 | 44% | routed |
| `git show` | 443 | 352 | 443 | 21% | routed |
| `git log --oneline` | 1416 | 1416 | 1416 | 0% | routed, no gain |
| `git log` (unbounded) | 4465 | 810 | 1477 | 82% | **refused** |
| `find -name` | 3180 | 569 | 884 | 82% | **refused** |
| `git status --porcelain` | 13 | 12 | 13 | 8% | **refused** |

"Recoverable" means rtk truncated but named a tee log that still contains
everything: a 30-failure pytest run showed 10 failures, and all 30 were retrievable
from the path it printed. The refusals lose information with no way back:

- **`git log` unbounded** returns 10 of 25 commits with no omission marker and no
  tee log, so the agent cannot tell it is reading a prefix of the history. Only
  `--oneline` (verified lossless at 25 of 25) or an explicit count (`-5`, `-n 20`,
  `--max-count=5`) is routed. `--stat` and `--graph` were on the allowlist until
  measurement showed they truncate to 10 as well.
- **`find`** dropped four of six directories entirely, announcing `+130 more` with
  a correct total and no path to recover the omitted entries.
- **`git status --porcelain`** keeps every line but drops the trailing newline, so
  `| wc -l` under-counts by one and a shell `read -r` loop loses the last record.

Both defects persist in 0.44.1, so this is the shape of the tool rather than a
stale bug. **rtk's own `rtk hook claude` is deliberately not installed**, because
it rewrites all of the above indiscriminately.

Also never routed: pipelines, redirection, command substitution, machine-format
flags (`--porcelain`, `--json`, `--format=`, `--numstat`), `curl`, and the
mutating `gh` subverbs. `gh pr merge` and `gh pr create` were being routed until
replaying real history caught it: the allowlist keys on the first two tokens
(`gh pr`), which cannot see the third, so a mutating-subverb blocklist now runs
after it. Flags whose meaning depends on the command are per-command: `-q` is
machine-quiet to git and merely terse to pytest, and banning it globally refused
`uv run pytest -q`.

### Expect a small effect, and measure it in bytes

Command counts flatter rtk. What costs context is BYTES, and on a 4,107-file
repository's real history the guard routes **3.6% of all `Bash` output bytes**
(114 of 3,350 calls; routed commands are only 1.1x larger than average, so the
two measures agree).

Where the rest goes:

| Share of Bash bytes | Reason it is out of reach |
| --- | --- |
| **76.7%** | **a tool rtk has no filter for** (`wt`, `bd`, `jq`, `rg`, `head`, `python3`) |
| 10.3% | `;` chain with no routable segment |
| 3.8% | pipes into a parser |
| 3.6% | routed today |
| 3.1% | other |
| 2.2% | `&&` chain (exit-status control flow) |
| 0.3% | heredoc |

**Steering agents toward "more filterable" commands is not worth it.** Fixing
every chain, heredoc, and parser pipe would lift rtk to **23.3% of Bash bytes at
most**, because the remaining 76.7% is tools it cannot filter at all. The twenty
largest outputs in that history are `head -100 <file>`, `wt list`,
`bd ready --json`, `rg -rn`, and `python3` heredocs; rtk has a filter for none of
them. Constraining how agents write shell commands would distort real work for a
ceiling still under a quarter.

The spill hook covers the 76.7% rtk cannot, because it never looks at which
command produced the output. Replaying that transcript history against its logic
puts it at 21.7% of all tool bytes. **Read that as an upper bound.** Claude Code
truncates Bash output natively into a `<persisted-output>` block, so the replay
figure also credits this hook for the largest results, which the native path takes
first.

The native default is between 24 KB and 31 KB, measured by reading what reached
the model rather than what any tool reported:

| raw output | native default | with `BASH_MAX_OUTPUT_LENGTH=2000` |
|---|---|---|
| 18,892 B | untouched | truncated |
| 23,892 B | untouched | truncated |
| 31,393 B | truncated to 2,246 B | truncated |
| 223,522 B | truncated to 2,247 B | truncated |

So this hook owns everything from 1 KB to about 30 KB, which is most real output.

### Why `BASH_MAX_OUTPUT_LENGTH=2000` is not a replacement

Lowering the native threshold to 2 KB covers the same range, and it is worse,
because native keeps the HEAD and this keeps head 20 **and tail 30**. A test run,
a build, and a stack trace all put the verdict in the last lines.

Measured on a 20,704-byte test log whose only failure is on the second-to-last
line, asking which test failed:

| | native at 2 KB | this hook |
|---|---|---|
| tool calls | 4 (`Bash`, then `Read`) | 2 (`Bash`) |
| tool-result bytes | 26,456 | **1,798** |
| answered correctly | yes | yes |

Both answered. Native answered by reading the spill file back, so the truncation
bought nothing and cost a round trip: 26,456 bytes against 1,798, worse than the
20,704-byte raw output it replaced. The tail is what makes the difference between
a summary that answers the question and a pointer that defers it.

Run `rtk-configure.py` (in the skill) to set `tee.mode = "always"`, so rtk keeps
a recovery log for every filtered command rather than only failed ones. The
default covers failures, which is the wrong half: a SUCCESSFUL `pytest` showing 10
of 30 failures is precisely when the rest is wanted. Note the limit measured on
0.44.1 -- the `git log` filter never tees under either mode, so unbounded
`git log` stays unrecoverable and the guard refuses it regardless. rtk's TOML
parser also requires every field of a section it reads, so a partial override
(`[tee]` with only `mode`) is rejected and silently falls back to defaults; the
script writes complete sections.

Telemetry is off by default in 0.44.1 (`rtk telemetry status` reports `consent:
never asked`). Upstream's configuration doc shows `enabled = true`; the binary
disagrees, and the binary is what runs. `RTK_TELEMETRY_DISABLED=1` overrides any
stored consent.

`RTK_DISABLED=1` leaves hook rewriting untouched; it affects only the rtk process
itself. To run an A/B baseline, remove the hook rather than setting that variable.

## Oversized output goes to disk

A `Bash` result over 1 KB is replaced by its first 15 and last 25 lines plus a
path to the full text. The path is bound once to `$F`, and the footer is two
lines:

```
F="/path/to/spill.txt"  # do not re-run
sed -n '18,217p' "$F"  # rg <pat> "$F"
```

Retrieval is therefore plain Bash and works under both runtimes, even though the
compression half is Claude-only (`updatedToolOutput` is absent from Codex's
`PostToolUse` wire struct). Head AND tail are kept because for the shapes that
blow up -- test runs, builds, stack traces -- the verdict is in the last lines and
the invocation in the first, so most questions need no retrieval at all.

A failing command is never summarized: the error text is the thing worth reading.
Output under the threshold is untouched, a spilled result never nests, and the
store is pruned to 200 files and 7 days.

### The footer sets the floor on the threshold

Overhead is fixed per spill, so it decides how small a result can usefully be
summarized. An earlier footer repeated the spill path four times, once in the
header and once per retrieval command, at 85 bytes each:

| Footer | Overhead | Path repeats |
| --- | --- | --- |
| three named commands, path in each | 555 B | 4 |
| path bound to `$F`, prose retained | 206 B | 1 |
| **current** | **174 B** | **1** |

At 555 bytes a 1 KB threshold spends more than half its budget on the footer. At
174 it does not, which is what makes 1 KB viable. The path is now 85 of those 174
bytes, so the remaining prose is 89 and there is little left to cut.

`# do not re-run` survives the trimming deliberately. Re-running the command is
the failure this hook exists to prevent, and its side effects have already
happened once.

Verified in a live session: asked for a value sitting mid-output in a 12,536-byte
test log, the agent read `$F`, ran `grep` against it, and answered from the file.
Total tool-result bytes for the run were 1,094.

### Threshold, re-tuned on 32,957 results across 651 repositories

Counting only the sub-native band this hook can claim, and excluding results
already shaped by a hook or the native cap:

| Threshold | Head/tail | Spilled | Bytes saved | Share of sub-native bytes |
| --- | --- | --- | --- | --- |
| 2 KB | 20/30 | 3,487 | 8,578,237 | 25.6% |
| **1 KB** | **15/25** | **6,165** | **10,614,207** | **31.7%** |
| 1 KB | 10/20 | 6,791 | 12,379,880 | 37.0% |
| 500 B | 10/15 | 7,994 | 12,898,559 | 38.6% |

Saved bytes keep rising, so bytes alone would pick the bottom row. What stops it is
how much of a spilled result stays readable. At 15/25 the median spill leaves 62%
of its lines visible and the 10th percentile 38%; at 10/20 those fall to 50% and
29%, making a third of spills mostly hidden for another five points. 500 B adds
0.9 points over 1 KB at 10/20 and spills 1,200 more results to get there.

A guard refuses any rewrite that would not shrink the result, so no configuration
can make a result larger.

The remaining bound is structural: results under 1 KB hold 7.9 MB of the corpus's
33.5 MB, and no size threshold reaches them.

### rtk and the spill hook compose rather than collide

They act at different points, so double-filtering is not a risk. rtk rewrites the
COMMAND in `PreToolUse`; the spill hook then sees whatever that command actually
printed. Measured on the same 3,350 real Bash results:

| | Results | Bytes |
| --- | --- | --- |
| rtk only | 103 | 48,431 |
| spill only | 278 | 1,220,138 |
| both would fire | 11 | 43,423 |

The overlap is 0.33% of results, and in practice it is smaller still: rtk usually
shrinks output BELOW the 2 KB threshold, so the spill hook then declines. A
`cargo clippy --workspace` that returned 6,773 bytes natively came back as 30
after rtk, and the largest rtk-filtered output measured was 1,765 bytes.

Where both do fire, they nest safely. Forcing the case (8,141 bytes of
rtk-filtered warnings) produced a 4,748-byte summary keeping the first and last
warning, a recovery path, and exactly one `[token-savings]` marker. The hook
refuses to re-spill an already-spilled result, so a marker can never stack.

## `Read` truncates silently, so the hook says so

`Read` on a file past its token cap returns a prefix and reports nothing. Measured
on a 118,893-byte, 4,001-line file: the result carried lines 1 to 2,860, with no
`<persisted-output>` block and no notice. Asked afterwards, the model reported
reading all 4,001 lines, which is what the result looks like from inside the
transcript. This is silent loss, the same class as rtk returning 10 of 25 commits
unmarked.

The hook payload carries what the result withholds. `tool_response.file` holds
`numLines`, `totalLines`, `startLine`, and `truncatedByTokenCap`, and that flag is
`True` on a truncated read and absent on a complete one, so
`read-truncation-notice.py` reads the runtime's verdict instead of guessing from a
size threshold.

It appends `additionalContext` and never rewrites the result. The content is not
the problem, the missing notice is, so nothing is substituted and a wrong guess
cannot lose data. Asked whether it had seen the whole file, the same prompt and
model answered:

| | answer |
| --- | --- |
| without the hook | "read all 4001 lines" |
| with the hook | "I saw lines 1 through 2,860 ... did not see all of them" |

`Glob` and `Grep` also reach `PostToolUse`, and both report their own truncation,
so neither carries a hook. `Glob` returns `truncated` and `countIsComplete`. `Grep`
was checked against the same failure that `Read` had: a `head_limit=20` over 500
matches returned `numLines=20`, `totalLines=500`, and an `appliedLimit` field, AND
the result the model saw ended with `[Showing results with pagination = limit: 20]`.
Asked afterwards, the model answered "you saw the first 20 matches ... roughly 4%",
so the cap is visible where `Read`'s was not.

## Repository pack, searched not read

A repomix pack of a 4,107-file repository is **6,349,248 tokens across 26 MB**,
roughly six context windows. Reading it cannot succeed. Searching it is genuinely
good: one file instead of a tree walk, **0.023s** to list every path under a
directory against 0.126s for the equivalent `rg` over the live tree, and faithful
(16 unique symbol matches in the pack against 16 live).

So a `PreToolUse` guard denies the read and names the search.

| Denied | Allowed |
| --- | --- |
| `Read` on a pack | `rg` / `grep` / `awk` / `sed` / `jq` / `wc` on a pack |
| any `mcp__*` file reader | `cat pack \| rg x` (a search; the reader is plumbing) |
| `cat` `bat` `less` `more` `nl` `open` | a pack under 40 KB (readable on purpose) |
| **`head` and `tail`, at any count** | any normal source file |
| `head -20 pack \| rg x` | |

`head`/`tail` are denied outright rather than allowed under a line limit. A prefix
of a pack is arbitrary, not a sample: `head -20` returned 3,023 bytes covering 7
unrelated file openings, while `rg -o 'path="[^"]*"'` answers the question that
motivates the peek -- what files exist -- completely and for less. Banning both
also removes the arbitrary-limit argument (why 200 lines and not 500).

The readable threshold is **40 KB**, roughly 10,000 tokens. It was 400 KB and that
was far too generous: half a context window spent by accident on an artifact whose
entire purpose is to be searched. A test asserts the constant stays small, because
a permissive threshold quietly defeats the guard.

`TOKEN_SAVINGS_ALLOW_PACK_READ=1` steps the guard aside when the whole pack
genuinely is what you want. A deny with no escape hatch is a guard that gets
deleted the first time it is wrong, and the denial names the override so the model
can act rather than just be blocked.

The denial also names the extraction that answers "show me one file":

```bash
awk '/<file path="src\/main.rs">/,/<\/file>/' repomix-full.xml
```

That works because XML's `</file>` close tag is self-delimiting. It is the one
place the output format matters: markdown's boundary depends on the next
`## File:` heading existing. On size the formats are identical (61,244 tokens for
xml against 61,249 for markdown), so choose for filterability.

### Generating it

`repomix` reads a committed `repomix.config.json`, so the package ships no
wrapper. Filter by PATH there before any content flag:

| Approach | 1,269-file repo | 4,107-file repo |
| --- | --- | --- |
| `--ignore` only | -21.1% | -33.5% |
| `--include` code+prose | -14.9% | -28.3% |
| `--include` CODE only | -61.2% | -59.0% |
| **`--include` + `--ignore`** | **-29.2%** | **-39.7%** |

Code-only is the biggest cut and the wrong default: it discards every README,
spec, and ADR, which is most of what a fresh session needs. Pairing the two also
fails safe, since an allowlist alone silently drops a language nobody listed.

`scripts/repomix-tune.py --repo <path>` re-derives all of this against whatever
repomix version is installed, so none of it has to be trusted. Running it on a
repository where graphify had been used found `graphify-out/` was **38% of the
entire pack** -- an index of an index -- which took that repository from a 14.9%
reduction to 87%.

## Tools evaluated and declined

| Tool | Verdict |
| --- | --- |
| `headroom` | No. Issue #2438 measures a 2-7x cost increase from defeating prompt caching in both modes. #789 (skill output compressed away) is open. Web tools are hardcoded verbatim-excluded with no subtractive key, so "compress web output" needs patching `config.py`. |
| `tamp` | No. Same proxy shape as headroom, so they collide. No per-tool or per-content filtering, only a global 1-9 level. `textpress` (L7+) posts content to OpenRouter. 86 stars, zero GitHub releases, and npm-declared MIT that GitHub cannot detect from any LICENSE file. |
| `token-optimizer` | No. PolyForm Noncommercial 1.0.0 is incompatible with this repository's Apache-2.0. Its runtime archive-and-retrieve idea is implemented here instead (see above), Claude-only for the same wire-struct reason. |
| `graphify` | Not wired by default, but worth a separate trial. `graphify update` rebuilt a 741-file repo in 7.4s and a 4,124-file repo in 55s (53,453 nodes) fully locally, so a post-commit hook is viable. Two caveats measurement surfaced: the FIRST build is not local (plain `graphify .` tried to send 468 files to AWS Bedrock), and it writes a 60 MB `graphify-out/` into the repo that is not gitignored. Its own benchmark reports accuracy (70.8% to 82.0% key-fact coverage) at ~140k tokens per query and never states the grep baseline's token cost, so the token claim is unverifiable from published data. Overlaps Serena and a code graph. Worth a separate A/B on resource use: it is tree-sitter parse-to-file with no resident daemon, against Serena's 4 processes at 95 MB RSS and 522 MB of bundled language servers. |
| `rtk curl` | Excluded from the allowlist, having passed an 89 KB HTML page through unchanged. |

## Web content

The fetcher MCP already runs Readability and returns markdown, measured 89%
smaller than raw HTML, so the compression is already present.
`trafilatura --markdown` reached 93% if a CLI is preferred.

For the browser, the interface choice dominates: `playwright-cli goto` returned
**402 bytes** on a docs page because it writes the accessibility snapshot to a
file and hands back the path, where the MCP server inlines the tree at **33,011
bytes** for the same page. The CLI still clicks, fills, uploads, and keeps state
across separate invocations, so it covers scripted flows and verification. The
`playwright` skill carries the routing table; the MCP server stays for loops that
need the model reasoning over page structure turn by turn. `--snapshot-mode none`
is not a shortcut: element refs come from snapshots, so it removes the ability to
interact at all.

## Tests

```bash
uv run --no-project --with pytest pytest -q packages/token-savings/tests/
```

242 tests, weighted toward the negative cases: every command shape the rtk
guard must refuse, every payload that must fail open, the budget gate and HEAD
dedupe, and the comparison verdicts that must decline to call a delta real.
