# token-savings

Context-cost reduction for Claude Code and Codex, plus the instrument that
decides whether a reduction happened.

Every figure below was measured locally. Where a tool's own numbers disagree
with what was measured, the measurement is reported and the tool's claim is
named as a claim.

## What it installs

| Client | Event | Matcher | Command |
| --- | --- | --- | --- |
| Claude Code | `SessionStart` | all starts | `repomix-map.py inject` |
| Claude Code | `PreToolUse` | `Bash` | `rtk-rewrite-guard.py` |
| Claude Code | `PostToolUse` | `Bash` | `repomix-map.py refresh`, `spill-tool-output.py` |
| Codex | `SessionStart` | `startup\|resume\|clear` | `repomix-map.py inject` |
| Codex | `PreToolUse` | `Bash` | `rtk-rewrite-guard.py` |
| Codex | `PostToolUse` | `Bash` | `repomix-map.py refresh` |

`rtk` and `repomix` are optional. Without them every hook exits 0 with no
output. `python3` is required.

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

- **`cost_weighted`, not `input_tokens`.** One session recorded 279 input tokens
  against 14.2M cache reads. Cache reads bill below fresh input but not at zero,
  so a tool judged on `input_tokens` looks transformative while changing nothing.
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

The spill hook reaches **21.7% of all tool bytes** without knowing which command
produced them, which is precisely why it covers the 76.7% rtk cannot.

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

A `Bash` result over 2 KB is replaced by its first 20 and last 30 lines plus a
path to the full text. The summary names the exact commands that recover any part
of it:

```
rg <pattern> /path/to/spill.txt
sed -n '43,242p' /path/to/spill.txt
wc -l /path/to/spill.txt
```

Retrieval is therefore plain Bash and works under both runtimes, even though the
compression half is Claude-only (`updatedToolOutput` is absent from Codex's
`PostToolUse` wire struct). Head AND tail are kept because for the shapes that
blow up -- test runs, builds, stack traces -- the verdict is in the last lines and
the invocation in the first, so most questions need no retrieval at all.

A failing command is never summarized: the error text is the thing worth reading.
Output under the threshold is untouched, a spilled result never nests, and the
store is pruned to 200 files and 7 days.

The threshold is tuned against 4,417 real tool results from a 4,107-file
repository's transcripts, where `Bash` owns 69% of all transcript bytes:

| Threshold | Head/tail | Spilled | Bytes saved | Share of all bytes |
| --- | --- | --- | --- | --- |
| 4 KB | 40/60 | 100 | 464,193 | 12% |
| 3 KB | 30/45 | 162 | 549,390 | 14% |
| **2 KB** | **20/30** | **285** | **794,965** | **21%** |
| 1 KB | 15/25 | 481 | 953,673 | 26% |
| 500 B | 10/15 | 587 | 1,145,952 | 31% |

The head and tail must shrink with the threshold: a 40/60 window is wider than
most 1 KB results, so it spills them for no gain. 2 KB at 20/30 is the choice.
Below it the window stops being useful rather than merely smaller -- at 500 B,
**1,069 of the spilled results fit entirely inside the head and tail**, so the
hook would rewrite them, add a retrieval footer, and hide nothing. A guard now
refuses any rewrite that would not shrink the result, so the threshold is safe to
lower without re-auditing the window.

The remaining bound is structural: **48% of transcript bytes live in results under
2 KB**, a long tail no size threshold reaches.

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

## Repository structure map

`repomix --no-files` emits the directory tree with no file contents. On a
741-file repository that is 6,093 tokens against 1,022,188 for a full pack, a
168x reduction, which is small enough to hand an agent at session start.

`--compress` is not the lever it appears to be. Measured repository-wide it
removes **21%** (10,365,403 to 8,166,829 tokens) against the 70% its
documentation claims, because it extracts Tree-sitter signatures from code while
markdown and JSON go untouched. It also regresses on comment-dense files, where
doc comments duplicate around the elision markers.

**A pack is cheap, which is the opposite of what this hook originally assumed.**
Measured on repomix 1.17.0: a full pack of 4,107 files is 1.65s, of 1,269 files
1.30s, and the `--no-files` map is 1.26s to 3.18s depending on the tree, so the
map is sometimes *slower* than the pack it replaces. repomix has no cache either
(two identical runs: 2.27s, 2.49s). The saving here is CONTEXT, not time. The
cost-avoidance machinery that the "packing is expensive" premise bought (a
detached re-exec, a lockdir, a 120-second timeout) has been removed; the
HEAD-marker gate stays because skipping redundant work is still right and costs
one file read.

The map is written under `XDG_STATE_HOME`, refreshed when HEAD moves, and
deduped with an atomic lockdir. `TOKEN_SAVINGS_MAP_BUDGET` (default 8000 tokens)
decides whether the map is inlined or merely named: a 4,124-file repository maps
to ~31k tokens, and paying that on every session would cost more than the
exploration it saves. Over budget, the hook tells the agent to `rg` the file.

`refresh` runs on every Bash call, so it rejects commands that cannot have moved
HEAD by testing the raw payload bytes before parsing JSON. That bail costs one
interpreter start and no filesystem work.

### Defects this found in `mcp-repomix`

That package's `repomix.xml` refresh hook has never produced a snapshot on any
local repository, for three independent reasons:

1. It passed `--directory`, which repomix 1.11.1 rejects with `unknown option`.
   Fixed here; the directory is positional.
2. It refuses unless `repomix.xml` is gitignored, and it is not gitignored in any
   local repository. This package writes outside the tree instead, so no
   `.gitignore` edit is required and no working tree is dirtied.
3. The installed hook still points at `repomix-refresh-snapshot.sh` after the
   shell-to-Python port renamed it. That is install drift, repaired by
   `apm install --force`.

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

162 tests, weighted toward the negative cases: every command shape the rtk
guard must refuse, every payload that must fail open, the budget gate and HEAD
dedupe, and the comparison verdicts that must decline to call a delta real.
