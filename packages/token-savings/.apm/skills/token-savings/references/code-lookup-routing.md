# Code lookup: which tool answers which question

Reaching for the wrong code-navigation tool costs tokens twice: once for the
answer, and again for the follow-up when the answer is incomplete. Measured on a
741-file Rust repository, the same four questions cost:

| Arm | Tool calls | Output bytes | Answered |
| --- | --- | --- | --- |
| grep and read | 14 | ~59,000 | 4/4 |
| graphify | 10 | 22,018 | 3/4 |

The graphify figure includes **12,464 bytes of `graphify --help`**, 57% of its
total, spent only because nothing had told the agent the command surface. This
file is that steering. With it, the same queries cost 71 to 2,840 bytes each.

## Route by question shape

MUST Use Serena for anything that depends on VISIBILITY or types. It is
  LSP-backed and live, so it knows `pub` from private, resolves generics, and is
  correct on a buffer that has not been saved. graphify does not model visibility
  at all -- asked for a file's public API it inferred "public" from `lib.rs`
  import edges, which is a guess.

MUST Use graphify for "what calls this" and "how are these two things related"
  when a graph exists. `affected` does a real reverse traversal and returns
  function names with file:line, where `rg` returns textual matches it cannot
  separate from doc-comment mentions. On one symbol `rg` found 27 matches;
  graphify returned 18 actual callers, each named.

MUST Fall back to `rg` when neither has an answer, and when the question is
  textual rather than structural (a string literal, a config key, a comment).

NOT Ask graphify to enumerate a file's members. `explain` hard-truncates at 20
  connections and prints "... and N more" with no flag to lift the cap; a file
  node with 55 connections loses 35 of them silently. `query --context contains`
  does not expand file-to-symbol edges, and free-text `query` returns document
  nodes rather than source nodes.

## graphify command surface

```bash
graphify explain "<symbol>"            # node plus its neighbours, typed edges
graphify affected "<symbol>"           # REVERSE traversal: what breaks if this changes
graphify path "<A>" "<B>"              # shortest path between two nodes
graphify query "<question>"            # BFS traversal; weak on source nodes
graphify update <path>                 # incremental rebuild, no LLM
```

All query verbs take `--graph <path>/graphify-out/graph.json`.

DEFAULT `explain` costs a few hundred bytes, `affected` a few thousand, `path`
  under a hundred. Prefer `path` when the question is "are these connected".

## Building and refreshing the graph

MUST Build with `graphify update <path>`, NOT bare `graphify <path>`. The plain
  form runs a semantic-extraction pass that ships file contents to an LLM
  backend -- observed attempting 468 files to AWS Bedrock on a 741-file
  repository. `update` is local and deterministic ("no LLM needed" per its own
  help), and is the incremental path: 7.4s on 741 files, 55s on 4,107.

MUST Gitignore `graphify-out/` before building. It is 9.9 MB on a small
  repository and 60 MB on a large one, and graphify writes it into the working
  tree without ignoring it.

## Serena

Serena's index is per-project and small (960 KB on a 741-file repository), but it
keeps language servers resident: 4 processes at 95 MB RSS, over a 522 MB
machine-wide install of bundled servers. graphify has zero resident processes and
no daemon, at the cost of a snapshot that is stale until rebuilt.

MUST Check `.serena/project.yml` names the repository's real languages. Serena's
  auto-detection chose Python only on a repository whose source is Rust, and a
  wrong language means every answer comes from a partial index.
