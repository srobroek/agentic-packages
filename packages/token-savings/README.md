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
| Claude Code | `PostToolUse` | `Bash` | `repomix-map.py refresh` |
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

Measured savings on allowlisted commands: `git log -50` 87% fewer bytes,
`git log --stat -20` 94%. Truncation is marked inline (`[+N lines omitted]`) and
a tee log path is named, so a shortened result is visibly shortened.

This package deliberately does not install rtk's own `rtk hook claude`. Measured on
0.43.0 it rewrites commands whose output is machine-parsed:

- `rtk git status --porcelain` preserves every line but drops the trailing
  newline, so `| wc -l` under-counts by one.
- `rtk grep` returned 25 of 400 matching lines.

Both behaviors are right for a model reading output and wrong for a pipeline
parsing it, and rtk cannot tell them apart because the difference is in the
caller's intent. So the allowlist names what is safe instead: `git log`, `diff`,
`show`, `blame`, `gh pr|issue|run`, `cargo`, `kubectl`, `docker ps`, `ruff
check`, `tsc`, `eslint`. Pipelines, redirection, command substitution,
machine-format flags (`--porcelain`, `--json`, `--format=`, `-c`), `grep`/`rg`,
`wc`, and `curl` are never rewritten.

Realized savings are bounded by tool choice: the hook sees only `Bash`, so
native `Read`, `Grep`, and `Glob` never reach it. `rtk discover` found the
largest local misses to be `rg -n` and `cat -n`, shell spellings of tools the
agent is separately steered to use natively. Measure before assuming this is a
large lever.

Telemetry is off by default in 0.43.0 (`rtk telemetry status` reports `consent:
never asked`). Upstream's configuration doc shows `enabled = true`; the binary
disagrees, and the binary is what runs. `RTK_TELEMETRY_DISABLED=1` overrides any
stored consent.

`RTK_DISABLED=1` leaves hook rewriting untouched; it affects only the rtk
process itself. To run an A/B baseline, remove the hook rather than setting that
variable.

## Repository structure map

`repomix --no-files` emits the directory tree with no file contents. On a
741-file repository that is 6,093 tokens against 1,022,188 for a full pack, a
168x reduction, which is small enough to hand an agent at session start.

`--compress` is not the lever it appears to be: Tree-sitter signature extraction
removed 8% on source files and 1.4% repository-wide, because the bulk is test
fixtures and cached artifacts rather than function bodies.

The map is written under `XDG_STATE_HOME`, refreshed when HEAD moves, and
deduped with an atomic lockdir. `TOKEN_SAVINGS_MAP_BUDGET` (default 8000 tokens)
decides whether the map is inlined or merely named: a 4,124-file repository maps
to ~31k tokens, and paying that on every session would cost more than the
exploration it saves. Over budget, the hook tells the agent to `rg` the file.

`refresh` runs on every Bash call, so it rejects commands that cannot have moved
HEAD by testing the raw payload bytes before parsing JSON. That bail costs one interpreter start and no filesystem work.

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
| `token-optimizer` | No. PolyForm Noncommercial 1.0.0 is incompatible with this repository's Apache-2.0. Its runtime archive-and-retrieve idea is Claude-only anyway: Codex `PostToolUse` cannot replace a tool result. |
| `graphify` | Not wired by default. Its own benchmark reports accuracy (70.8% to 82.0% key-fact coverage) at ~140k tokens per query and never states the grep baseline's token cost, so the token claim is unverifiable from published data. Overlaps Serena and a code graph. Worth a separate A/B on resource use: it is tree-sitter parse-to-file with no resident daemon, against Serena's 4 processes at 95 MB RSS and 522 MB of bundled language servers. |
| `rtk curl` | Excluded from the allowlist, having passed an 89 KB HTML page through unchanged. |

## Web content

The fetcher MCP already runs Readability and returns markdown, measured 89%
smaller than raw HTML, so the compression is already present.
`trafilatura --markdown` reached 93% if a CLI is preferred.

For Playwright, prefer targeted extraction over a full snapshot on read-only
content: `ariaSnapshot` measured 21.8 KB against 7.3 KB for `innerText` on the
same page. Use `browser_find` to locate a node, then a depth-limited
`browser_snapshot`.

## Tests

```bash
uv run --no-project --with pytest pytest -q packages/token-savings/tests/
```

110 tests, weighted toward the negative cases: every command shape the rtk
guard must refuse, every payload that must fail open, the budget gate and HEAD
dedupe, and the comparison verdicts that must decline to call a delta real.
