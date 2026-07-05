# Ledger and DAG: stores, schemas, scripts, git anchors

Two shared stores live at one **absolute path outside every worktree** so agents
in isolated worktrees still get live reads/writes. Broadcast the path to every
agent (like you broadcast worktree paths):

```
<primary>/.orchestration/run-<id>/      # gitignore this dir
  graph.json            # mutable task DAG + current state
  ledger.jsonl          # append-only forensic history
  artifacts/<seq>-input.md, <seq>-output.md   # full briefs / reports
```

Only `graph.py` writes `graph.json`; only `ledger.py` writes `ledger.jsonl` (and
`artifacts/`). Both use `flock` so concurrent agents never corrupt a file.
Every script requires an **absolute** `--store` path — a relative path resolves
against the agent's own worktree, not the shared store, and silently diverges.

## DAG — `graph.py --store <store> …`

Built on stdlib `graphlib` (no external dependency, no agent). Nodes hold
`{id, desc, scope[], deps[], state, assignee, branch, commits[], meta{}}`.

| Command | Purpose |
|---|---|
| `init [--run-id]` | create empty graph |
| `add-node <id> --scope 'a/**,b/**' [--desc] [--dep x …]` | add a task; scope = owned globs |
| `add-edge <from> <to>` | `<from>` must finish before `<to>` |
| `set-state <id> <state>` | advance state (validated enum) |
| `set-meta <id> --assignee <agentId> [--branch <b> --commit <sha>]` | record the live agent handle at spawn, and the branch/commit once `REPORTED` — this is what makes a run resumable after compaction/crash |
| `ready [--json]` | nodes whose deps are cleared **and** scope is disjoint from every in-flight node |
| `impact <id>` | every downstream node stranded if `<id>` is/becomes `failed` |
| `show <id>` · `list [--state]` · `validate` · `dot` | inspect / check (acyclic + disjoint concurrent scopes) / Graphviz |

`ready`'s scope check is what prevents two parallel worktree coders from editing
the same files. **Merge order is not encoded** — the gatekeeper decides it at
runtime, FCFS + conflict probe.

## Ledger — `ledger.py --store <store> …`

`add` stamps `ts` (UTC), `run_id`, `seq`; validates the `event` enum; writes
`--input/--output` (or `--input-file/--output-file`) into `artifacts/` and
records `*_ref`; then flock-appends one JSON line.

- **Canonical event set:** the lowercase message verbs (`assign`, `blocked`,
  `advice`, `reported`, `review`, `fix`, `conflict`, `approve`, `merged`,
  `dismiss`, `ask`) plus `failed` and `note`.
- **`--worktree <path>`** records the agent's live worktree at the time of the
  event (ephemeral pointer — see Git anchoring below).
- Prefer **`--input-file`/`--output-file`** over inline `--input`/`--output`:
  inline text over ~200 chars is truncated in-row once an artifact file exists
  for that record, so long briefs/reports must go through the file form to stay
  whole.
- A corrupted trailing line (partial write from a crash) is tolerated: skipped
  with a stderr warning, never a hard failure — readers keep working on the
  well-formed lines before it.

Record shape:

```json
{"ts":"2026-07-05T14:02:11Z","run_id":"run-7f3a","seq":42,"event":"reported",
 "actor":"coder-t3","role":"coder","model":"sonnet","effort":"medium","parent":"main",
 "node":"t3","state":"in_review","base":"main@3f9a1c2",
 "branch":"coder/t3-auth-middleware","commits":["a1b2c3d"],"pushed":"origin/coder/t3-…",
 "pr":null,"merge_sha":null,"worktree":"/…/worktrees/t3 (ephemeral)",
 "input":"…summary…","input_ref":"artifacts/0042-input.md",
 "output":"…summary…","output_ref":"artifacts/0042-output.md",
 "result":"green: 41 passed; clippy/fmt clean",
 "issues":["validate_token sig change rippled to src/api/**"],
 "unexpected":["found /auth/legacy not in brief → raised ASK"],
 "refs":["reviewer-t3"],"artifacts":["commit:a1b2c3d"]}
```

**Read (deterministic, not grep):** `query [--node --actor --event --state --since
--fields] [--json]`, `timeline --node`, `replay --node` (brief→output→result chain
with artifact paths), `summary`, `issues`, `agents`. The `ledger-scribe` agent runs
these on demand.

## Conflict probe — `conflict-probe.sh <subcommand> …`

Deterministic, non-mutating merge-safety checks for the gatekeeper.

| Subcommand | Purpose | Exit / output |
|---|---|---|
| `conflicts <base> <branch>` | predict a merge conflict via `git merge-tree`, no tree mutated | exit 1 + conflicting paths on conflict; exit 0 clean |
| `pairwise <base> <a> <b>` | do two approved branches touch overlapping files? | same convention: exit 1 + paths, else 0 |
| `ci <pr\|branch>` | `gh pr checks` status | reflects CI pass/fail for that ref |

## Hygiene and validation scripts

| Script | Purpose |
|---|---|
| `msg-lint.py` | validates a SendMessage body: known VERB, a node id, and the required fields for that verb present |
| `worktree-sweep.sh <wt>` | refuses to touch a dirty tree; otherwise removes build dirs and runs `git worktree remove` + `git worktree prune` |
| `consistency-check.py --store <store>` | cross-checks graph state against ledger events; the close-out go/no-go gate; exit 1 on any mismatch |

## Git anchoring (survives worktree teardown)

A worktree path goes stale once the worktree is removed after merge, so **code is
anchored to durable git objects, not the worktree**:

- `base` (ref@sha branched from), `branch`, `commits[]` (SHAs — `git show <sha>`
  reproduces the change), `pushed` (remote ref once the coder pushes), `pr`
  (number/URL when opened), `merge_sha` (SHA on the target after merge).
- `worktree` is recorded only as a **live, ephemeral** pointer, valid while the
  node is in flight.
- Full brief/report **text** lives in the shared `artifacts/` dir (never inside a
  worktree), so it survives teardown.

Reproduction after the run: read the brief/report from `artifacts/`, and the diff
from the commit SHA / PR / merge commit — no dependency on any worktree still
existing.
