# Agentic-Packages Audit Remediation Plan

**Date:** 2026-06-25
**Source:** Comprehensive 3-workflow audit (deep-dive 28 agents, reduction 14, language-bundles replacement) + interactive grill.
**Raw findings:** 273 review + 83 reduction + 56 reproduced script bugs + 4 cross-cut syntheses.
**Status:** decisions locked via grill; **nothing implemented yet** — this doc is for approval before edits.

## Governing principles (locked)

1. **Frontier-only model assumption.** Every consumer runs a decent Opus/Sonnet/GPT-5.x model. "Model does it inline" justifies cutting *reasoning scaffolding* but NOT *facts the model can't get without the hook*.
2. **Portability floor = bash 3.2.57 + BSD sed/grep** (stock macOS). Hard rule. `#!/usr/bin/env bash` stays.
3. **`packages/` is the single source of truth.** The live chezmoi copies become installer-generated, not hand-edited. Roll global→package where the global copy is better.
4. **APM has no cross-package shared-asset primitive** (hooks resolve via `${PLUGIN_ROOT}` of their own package; installs flatten). Dedup that requires runtime sharing is rejected in favor of self-contained copies or authoring-time codegen.

---

## Phase 0 — Verify-before-act (do these checks first; they gate destructive steps)

| # | Check | Gates |
|---|---|---|
| 0.1 | Confirm `codex/config.dev-container.toml` is unreferenced by the chezmoi template selector. **Note: `mise-dev-container` config dir EXISTS** — the dev-container profile is real. | whether to DELETE vs MIGRATE the codex dev-container config |
| 0.2 | Confirm the global APM install path / how chezmoi will write installer output to the managed location | the whole SoT installer (Phase 3) |
| 0.3 | Confirm `verify` skill has no invocable command surface (already confirmed: type:skill) | already resolved — no verify-dep dedup |
| 0.4 | Confirm Codex PreToolUse stdin payload shape + whether it honors deny/ask/allow | guard fixes' cross-tool validity + codex-hook-contract doc |

---

## Phase 1 — Security & correctness bug fixes (UNCONDITIONAL; highest priority)

All fixes land in `packages/`, with a per-payload regression test, then sync to live (Phase 3).

### 1A. Guard bypasses (security false-negatives)
- **String-form `tool_input` bypass** (bash-guard, git-guard, chezmoi-guard): `.tool_input.command // .tool_input` *throws* on a string. Replace with chezmoi-sync's idiom: `jq -r 'if (.tool_input|type)=="string" then .tool_input else (.tool_input.command // empty) end'`.
- **git-guard misses** `git reset HEAD --hard` and `git clean -df`/`-xdf`: widen regexes to match `--hard` anywhere in a reset invocation and any force-flag cluster (`-df`/`-xdf`/`-fd`/`--force`).
- **git-guard `git -C '/path with space'` bypass**: strip global options first, re-match subcommand (don't model spaced quoted args in one ERE).
- **bash-guard misses** `mkfs.ext4`, `rm -rf /*`, `rm -rf //`, `rm -rf $HOME`, `;sudo`/`&&sudo`: extend the deny regexes.
- **chezmoi-guard `..` traversal bypass**: `realpath -m` / Python `Path.resolve(strict=False)` canonicalization in `normalize_path` before membership test (chezmoi-sync already has the helper).

### 1B. Portability class (bash 3.2 + BSD) — ~20 bugs
- `rm-rf-guard.sh:24` `;;&` → explicit independent flag tests (bash-3.2 parse error today; script is DEAD on macOS).
- `quality-before-commit.sh` (61/70/91) + `quality-edit-advisory.sh:73` `mapfile` → `while IFS= read -r` loop (commit quality gate currently fails-OPEN on go/py/ts).
- `apm-discover.sh:211` + `project-setup.sh:309` empty-array `set -u` → `"${arr[@]+"${arr[@]}"}"` guard (default `project-setup` aborts before writing files).
- `speckit-pr-issue-refs.sh` `+?` (BSD sed reject) → portable greedy regex; also fixes ssh-URL slug.
- `speckit/task-issue-sync.sh` `\b` (BSD sed) → drop `\b`.
- `go-quality/check.sh:4` `gofmt -l . | (! grep .)` → capture+test (exits 1 on clean repo under 3.2).
- `typescript-quality/check.sh` `biome && tsc; exit 0` → run each on own line, let `set -e` propagate (currently FALSE-PASSES on biome failures).

### 1C. Other reproduced crashes
- `resume-session` list+read: guard `iter_json_lines` to yield only dicts (one non-dict JSONL line crashes the whole listing).
- `dispatcher.py`: type-guard command/feature_directory (non-string → AttributeError); `node.get('title', node_id)` fallback.
- `_test_dispatcher.py`: replace hardcoded `phases == 174` with data-derived assertion (currently 178 → CI broken).
- `validate-dag.py`: line-tolerant `blocked_by` capture (`[^\]]*`) — currently MISSES multi-line cycles.
- `new-handover.py`: YAML-safe value quoting + OSError guard on out-dir-is-file.
- `setup-{go,python,rust,ts}.sh`: gitnr-present-but-fails fallback (mirror project-setup.sh's working pattern).
- `package-add.sh`: reject `..`/`/`/absolute `--name` (path traversal); validate `--lang` before mkdir.
- `setup-speckit.sh`: `grep -qw` → exact name match (`security-review` falsely matches `review`).
- `speckit-task-commit-check.sh` / `speckit-stop-gate.sh`: `|| true` on git calls; fix grep-c double-zero.
- `speckit-issue-label-guard.sh`: anchor `deferred` detection to a label, not substring `defer`.
- `worktree-create.sh`/`cleanup.sh`: sanitize name, guard against main-repo, `--force` only in managed tree, `stash -u`.

### 1D. Guard false-positives (read-only — fix NOW)
- **no-ff-guard**: anchor to a real `merge` subcommand; exclude `merge-base`, `mergetool`, `--abort/--continue/--quit`, `--ff-only`; require `--no-ff` as a token. (Currently blocks read-only `git merge-base`.) Identical in live + package.
- **squash-merge-guard**: anchor strategy alternation `([[:space:]=]|$)`; accept `-s/-m/-r`; allow `--help`. (Live copy is behind the package fix.)
- _Deny-vs-ask SEVERITY policy (branch -d, stash drop, lint gate) = deferred to a per-guard pass (Phase 6)._

### 1E. Broken bundle pins (silently break installs today)
- `core/apm.yml`: `project-lifecycle#^0.1.2`, `code-intelligence#^0.1.3`, `agentic-maintenance#^0.1.3` → all deps are at **0.2.0** (excluded by caret). Bump to `^0.2.0`.
- `speckit-dag-hooks/apm.yml`: `speckit#^0.1.1` → speckit is **0.4.0**. Bump to `^0.4.0`.
- `planning-product/apm.yml:20-22`: YAML folded scalar merges two deps into one malformed locator. Split into two `-` items.
- `language-rust → language-steering-rust#main`, `language-typescript → language-steering-typescript#main`: pin to `^0.5.0`/`^0.2.0` (or adopt a uniform sibling-pin policy — see open item).

---

## Phase 2 — Speckit DAG refactor

- **Prune node families:** CUT onboarding (7), brownfield (4), diagram (3), optimize (3). KEEP spine, memory-md, review-run, github-issues, tinyspec, agent-assign, bugfix, retro/qa/critique/conduct/security-review/code-review/cleanup, worktree nodes.
- **`$ref` for ALL shared prose:** add a top-level `_fragments` dict + a ~10-line render-time `$ref` expander in `render_body`. Convert the orchestrator/stay-alive prose (and review-variant shared context) to refs. (Not the strip-suffix fallback — keep explicit.)
- **Fix 5× malformed `going_to: "review.run - fix-findings"`** strings (folded-scalar bug class) while touching those nodes.
- **Authoring builder (replaces hand-written JSON):** add `build_nodes.py` — a **stdlib `@dataclass` Graph/Node/Edge builder** (zero deps). Edges are a single canonical store; `came_from`/`goes_to` are **projections derived at emit time**, so `g.edge(a, b, when=…)` auto-populates BOTH sides — structurally eliminating the came_from/goes_to disagreement (the malformed `"review.run - fix-findings"` becomes impossible to author). Two methods: `g.edge(src, dst, when=…)` for real node→node links (auto-bidirectional, validated to exist) vs `node.hint("…")` for free-text navigation prose NOT validated as an edge (covers "(direct invocation…)" strings). `$ref` fragments first-class via `g.fragment(name, text)`.
- **emit() → compiled artifact:** the builder validates via stdlib `graphlib` (cycle) + BFS (orphan/reachability) + well-formedness, then writes flat **`nodes.json`**. **No networkx** (new dep; binary-wheel cost for rustworkx/igraph; diagram justification gone since diagram-* cut).
- **Runtime firewall (why JSON stays, per grill):** dispatcher reads `nodes.json` with stdlib `json`, UNCHANGED and dependency-pure. The JSON boundary enforces "authoring code may use anything; runtime stays stdlib" — graph errors fail CI not the user's tool call; runtime does a point lookup (no graph materialized on the hot path); the DAG stays greppable/diffable.
- **CI staleness gate:** `build_nodes.py --check` regenerates and diffs against committed `nodes.json`; fail on mismatch (same drift-prevention pattern as the chezmoi installer).

---

## Phase 3 — Source-of-truth installer (the #1 systemic fix)

Model on `chezmoi .chezmoiscripts/run_onchange_before_45-uv-tools.sh.tmpl` / `30-mise-tools`:
- New `run_onchange_*` chezmoi script, sha256-data-hash trigger, feature-gated, idempotent install loop, **auto-latest `upgrade --all`** (matching uv/mise; user accepts non-reproducibility for currency).
- **Scope:** APM marketplace (your packages incl. hooks/skills/steering) + Claude plugin marketplaces + Codex marketplaces/configs + `npx skills` (the `npx skills` command).
- **Roll-up (one-by-one review):** where the live chezmoi copy is BETTER than the package, back-port into the package FIRST, then let the installer drive live:
  - `pre-commit-test-gate.sh` (live stateless rewrite is the intended design) → replace package version.
  - `codebase-index.sh` (live async/XDG/MCP-guarded) → fold into code-intelligence package.
- **Orphans:** `stuck-reset.sh` DELETE (dead v1 of unstuck_monitor.py).
- **CI drift-check** (= `hooks-portability-ci` pkg, see Phase 5): hard-fail when live copies diverge from package output, plus `bash-3.2 -n` + BSD-sed passes + string-form payload pass.

**Stays chezmoi-only (documented exceptions in steering index.md):**
- `sandbox-push-reminder.sh` — Amazon Code-Defender/sandbox fact + Claude-only field.
- `chezmoi-sync.sh` — bootstraps chezmoi itself; already uses the correct realpath pattern.

**Gets a new public package:**
- `hooks-chezmoi-guard` — extract `chezmoi-guard.sh`, fix the `..` + string-form bypasses there, sync to live.

---

## Phase 4 — Retirements & relocations

- **Rename `resume` → `resume-cv`** (namespace collision with resume-session); pin its `#master`/`#main` third-party deps.
- **Retire `prompt-lookup`** (no backend exists; ships broken): delete + remove its dep lines in `agentic-maintenance` + `code-intelligence`.
- **Delete `steering-pragmatic`** (verbatim copy of global personality.md, always-on).
- **Move `hyperresearch` OUT of APM** into the chezmoi uv-tools install path (pinned uv tool — resolves provenance concern).
- **KEEP** diagrams + presentation (reviewed, not retired).
- **Split Tauri:** new `language-rust-tauri` package gets the Tauri context/playbook; the Tauri MCP server gets its own package (split from today's `mcp-tauri`, which already holds server + context); `language-rust-tauri` depends on the server package; `language-rust` → pure bundle.

---

## Phase 5 — Net-new packages

- **secrets-scan** — gitleaks/trufflehog PreToolUse pre-commit hook + skill (closes the "check for secrets" prose-only gap).
- **dep-audit** — npm/cargo/pip-audit/osv-scanner skill (closes the supply-chain gap).
- **codex-hook-contract** — reference doc: verified Codex hook event names, stdin payload shape, deny/ask/allow semantics (de-risks every "cross-tool" guard). Depends on Phase 0.4.
- **hooks-portability-ci** — release gate: `bash-3.2 -n` lint, BSD-sed/grep pass, string-form payload pass, + the Phase-3 drift-check.

---

## Phase 6 — Structure, dedup, steering, metadata

- **MCP wiring:** add `mcp-codebase-memory` as a real dep of `code-intelligence` (+ install path/prereq for the bare binary); add `playwright → mcp-playwright` edge. **`core` depends on individual MCP servers directly (NO mcp-core bundle).**
- **type:hybrid → type:bundle** for the payload-less language-* (go/python/terraform + arm-cortex/dotnet/functional/julia/jvm/shell/web-scripting).
- **Normalize `includes: auto`:** strip from deps-only bundles, keep only where a package has own payload.
- **Add `terraform-quality`** (fmt/validate/tflint) mirroring go-quality; `language-terraform` depends on it.
- **Merge the 3 commit skills → 1 multi-mode skill** with a shared `references/commit-discipline.md`. ⚠️ Migration risk: changes invocation surface (3 named skills → 1 + mode arg); update bundle/trigger refs; document old→new mapping.
- **Quality-skill bug fixes in place, keep 3 copies** (no shared-lib infra; verify-dep rejected as fragile).
- **branch-check.sh:** replace ~256 lines → ~30: keep git-fact injection (branch, protected status, feature branches/worktrees), cut keyword/is_complex engine + /tmp cooldown. (Both copies; also fixes detached-HEAD + BSD-grep bugs.)
- **Strip optimize-steering fabricated stats** (keep actionable rules).
- **Rename `trace_call_path` → `trace_path`** (3 refs: codebase-memory trace.md + reference.md + pr-reviewer agent).
- **Collapse "prefer graph/grep" restatement** (8+ → 1 canonical); soften global "ALWAYS prefer MCP" to non-absolute.
- **README/plugin.json generator:** sync plugin.json version (0.2.0 → match apm.yml) + generate counts from marketplace.json + CI `--check` gate.

### Codex config
- **Delete dead variants** `config.toml` (plain, Linux paths) + `config.dev-container.toml` — **PENDING 0.1** (migrate dev-container to `:workspace_roots`/drop `codex_hooks` if live).
- **Prune `default.rules`** session accretions (AWS account IDs, OU ids, worktree blobs) + policy: session approvals must not auto-persist.
- **Tighten over-broad allows** (unqualified git commit / push origin main / rebase / curl / docker run) so Codex rules stop re-permitting what git-safety hooks gate.

---

## Open items (need a decision, not yet grilled)
- Uniform sibling-pin policy across the 5 rich language bundles (caret + dep-bump automation, OR `#main` for co-released siblings + update docs/bundles.md:64). Currently inconsistent (rust/ts on `#main`, go/python/terraform on `^0.1.1`).
- Deny-vs-ask severity policy per guard (Phase 6 follow-on).

## Suggested execution order
1. Phase 0 checks → 2. Phase 1 (bugs + pins, security first) → 3. Phase 2 (speckit) + Phase 5 hooks-portability-ci → 4. Phase 3 (installer + roll-up) → 5. Phase 4 (retirements) → 6. Phase 6 (structure/steering/codex) → 7. remaining Phase 5 net-new.
