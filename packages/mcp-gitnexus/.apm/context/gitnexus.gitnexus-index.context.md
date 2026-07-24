# GitNexus Code Intelligence

GitNexus builds a knowledge graph over an indexed repo (nodes/edges for
symbols, call and class-member relationships, community clusters, execution
flows). It answers *relationship* questions text search cannot.

TOOL ROUTING
DEFAULT Structural questions → GitNexus MCP tools:
  - `query` — execution flows related to a concept ("how does checkout work")
  - `context` — 360° view of one symbol: callers, callees, process membership
  - `impact` — blast radius: what breaks if a symbol changes; use before
    refactors and in PR review
  - `trace` — shortest directed call path between two symbols
  - `cypher` — raw graph query when the canned tools don't fit
DEFAULT Exact text/paths → `rg`; precise symbol *editing* and references in
  the open workspace → Serena. GitNexus complements, not replaces, both:
  it sees cross-file execution structure; Serena sees live LSP truth.
NOT Use GitNexus for unindexed repos or content newer than the index —
  check freshness first.

INDEX LIFECYCLE
MUST A repo is queryable only after `gitnexus analyze` (writes `.gitnexus/`,
  registers in `~/.gitnexus/registry.json`). Verify freshness with
  `gitnexus status` — a stale `lastCommit` vs HEAD means re-run
  `gitnexus analyze` before trusting graph answers.
DEFAULT `gitnexus detect-changes` maps a git diff onto indexed symbols and
  affected flows — cheaper than a full re-analyze for review tasks.

INSTALL / RUNTIME GOTCHAS (why the server config looks the way it does)
MUST Keep `SHARP_IGNORE_GLOBAL_LIBVIPS` — see server env — set to `1`:
  gitnexus depends on sharp (via @huggingface/transformers), and on hosts
  with a Homebrew libvips sharp abandons its prebuilt binary and attempts a
  node-gyp source build, which fails without node-gyp and kills the whole
  npx install. The env var forces the prebuilt path.
DEFAULT If `npx -y gitnexus@latest` fails with ENOTEMPTY/rename errors in
  `~/.npm/_npx/...`, an earlier interrupted install corrupted that npx cache
  entry — remove the named `~/.npm/_npx/<hash>` directory and retry.
NOT Do not run `gitnexus setup` in APM-managed environments — it writes MCP
  entries and hooks directly into editor configs, which this package owns
  declaratively instead.
