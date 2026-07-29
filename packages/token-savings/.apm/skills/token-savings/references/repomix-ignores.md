# Repomix: what to exclude, and why the flags are not the lever

`--compress` looks like the answer and is not. Measured repository-wide with
repomix 1.17.0 it removes 21% (10,365,403 to 8,166,829 tokens) against the 70% its
documentation claims, because it extracts Tree-sitter signatures from code while
markdown and JSON go untouched, and it REGRESSES on comment-dense files where doc
comments duplicate around the elision markers.

Filtering by path does better, losslessly, because what dominates a pack is not
code. An allowlist and a blocklist cut different things, and compose:

| Approach | 1,269-file repo | 4,107-file repo |
| --- | --- | --- |
| default | 1,299,332 tokens | 10,365,403 tokens |
| `--ignore` only | -21.1% | -33.5% |
| `--include` code+prose | -14.9% | -28.3% |
| `--include` CODE only | **-61.2%** | **-59.0%** |
| **`--include` + `--ignore`** | **-29.2%** | **-39.7%** |

`--include` restricted to code extensions is the single biggest cut, and it is
the wrong default: it discards every README, spec, and ADR, which is most of what
a fresh session needs to understand WHY the code is shaped as it is. So the
shipped configuration admits prose and config in the allowlist, then uses the
blocklist to remove the generated and duplicated members of those same
extensions. A lockfile is `.yaml`; a CHANGELOG is `.md`.

Pairing them also fails safe. An allowlist alone silently drops a language nobody
thought to list; with both, a new extension shows up as noise to be measured
rather than as a file that vanished.

## What was actually eating the pack

Top consumers on the 4,107-file repository:

| File | Tokens | Share |
| --- | --- | --- |
| `assets/seed/seed.json` | 1,489,873 | **14.4%** |
| `apm.lock.yaml` | 141,772 | 1.4% |
| `impeccable/scripts/live-browser.js` (twice) | 221,224 | 2.2% |
| `local-branches.txt` | 82,154 | 0.8% |
| `apps/desktop/src/bindings/index.ts` | 99,667 | 1.0% |

One seed fixture was 14.4% of the entire pack. `live-browser.js` appeared TWICE
because `.agents/skills/` and `.claude/skills/` are duplicate trees. On the
1,269-file repository the profile differed -- `CHANGELOG.md` files and generated
`marketplace.json` led -- so the set below covers both shapes.

## The set

```
**/CHANGELOG.md
**/*.lock,**/*.lock.yaml,**/*.lock.json
**/pnpm-lock.yaml,**/Cargo.lock,**/uv.lock,**/package-lock.json,**/poetry.lock
**/.claude-plugin/marketplace.json,**/.agents/plugins/marketplace.json
**/assets/seed/**,**/fixtures/**,**/testdata/**,**/*.snap
**/messages/*.json,**/locales/**,**/i18n/**
**/bindings/index.ts,**/*.generated.*,**/generated/**
**/.agents/skills/**,**/.specify/extensions/**
**/local-*.txt,**/*.min.js,**/*.min.css,**/*.map
```

Pass as `repomix --ignore "<comma-separated>"`, or put the patterns in
`.repomixignore`.

MUST Verify a new pattern keeps real source. Excluded paths still appear in the
  DIRECTORY TREE and only their contents are dropped, which is the desired
  behavior: the agent can still see that `assets/seed/seed.json` exists and read
  it deliberately. Confirmed by checking `path="<file>"` attributes rather than
  bare name occurrences -- a name match in the tree is not a packed file.

NOT Exclude a directory because it is large. `crates/` and `apps/*/src` are large
  and are the point. Every entry above is generated output, a lockfile, fixture
  data, a duplicated tree, or an i18n bundle.

NOT Rely on `--compress` as the primary lever. It is a per-language choice: 65 to
  80% on JavaScript, TypeScript, and Python, 26% on Rust, 0% on markdown and
  JSON, and a regression on comment-dense files.

## Every other knob, measured

On the 4,107-file repository with the allowlist already applied (baseline
7,644,214 tokens). Positive means smaller:

| Knob | Effect |
| --- | --- |
| `--remove-comments` | **+13.6%** |
| `--no-directory-structure` | +0.4% |
| `--remove-empty-lines` | 0.0% |
| `--no-file-summary` | 0.0% |
| `--truncate-base64` | 0.0% |
| `--style markdown` | -0.1% |
| `--style plain` | 0.0% |
| `--style json` | **-10.9%** (worse) |

So the output FORMAT is noise: xml, markdown, and plain land within 0.1% of each
other, and json is 11% WORSE because of key repetition and escaping. Pick a style
for readability, not for size. `--remove-empty-lines` and `--truncate-base64` do
nothing measurable on a real tree.

NOT Enable `--remove-comments` by default, despite it being the only knob that
  moves. It keeps Rust doc comments (`///`) but strips every `//` and `#`, which
  is where SAFETY notes, invariants, and "why this way" live -- verified on one
  crate: 916,573 to 666,191 bytes with `SAFETY` gone. Those comments are the part
  of a file an agent cannot re-derive from the code. Reach for it only when
  packing for a mechanical task (a rename sweep, an import audit) where intent
  does not matter.

## Cost, for calibration

A pack is cheap and has no cache, so nothing is gained by deferring one:

| Operation | Time |
| --- | --- |
| pack 4,107 files | 1.65s |
| pack 1,269 files | 1.30s |
| `--no-files` map | 1.26s to 3.18s |
| second identical run | 2.49s (no caching) |

The `--no-files` map is sometimes SLOWER than the full pack it replaces. Its
saving is context (31,299 tokens against 10,365,403, a 331x reduction), never
time.
