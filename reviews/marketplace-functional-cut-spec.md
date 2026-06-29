# Making the APM marketplace functional for Claude & Codex

Status: proposal (2026-06-27). Diagnosis VERIFIED against `microsoft/apm` tag
`v0.21.0` (commit `975f8f0`) source + reproduced locally with the installed
`apm` 0.21.0 binary.

## TL;DR

The generated marketplace **catalog** files are correct and schema-valid. What
is broken is the **package sources they point at**: every marketplace entry has
`source: ./packages/<name>`, but those directories are in APM-native layout
(`.apm/skills/…`, `.apm/agents/…`, `.apm/hooks/*.json`) with **no native plugin
layout** (`skills/`, `agents/`, `commands/`, `hooks/hooks.json`, or
`.claude-plugin/plugin.json`) at the package root.

Consequence:

- **`apm install <pkg>@<marketplace>` works today.** APM reads `.apm/` and
  integrates into `.claude/skills`, `.claude/agents`, `.claude/settings.json`,
  `.claude/rules`, `.mcp.json`. Verified for skill/agent/hooks/steering/mcp.
- **Claude Code native `/plugin install` does NOT work.** Claude's loader (and
  APM's own `ClaudePluginDetector`) require `.claude-plugin/plugin.json` or a
  top-level `skills/`/`agents/`/`commands/` dir at the source path. Pointed at
  `./packages/<name>`, it finds an `.apm/` dir it does not understand → empty
  plugin / "Plugin directory not found".
- **Codex** has no verified native `/plugin` marketplace loader. The
  `.agents/plugins/marketplace.json` output is consumed by APM tooling (and
  Copilot CLI), not a native Codex loader. Codex consumption = `apm install`.

`apm pack` does exactly three things and **never rewrites `./packages/<name>/`**:
1. writes `.claude-plugin/marketplace.json` (Claude catalog),
2. writes `.agents/plugins/marketplace.json` (Codex catalog),
3. writes a single **repo-root** `.claude-plugin/plugin.json` (treats the whole
   monorepo as one plugin; synthesized from root `apm.yml`, with
   agents/skills/commands keys stripped).

The only marketplace transform is renaming `packages:` → `plugins:`. Local
`source:` paths are emitted **verbatim**.

## Why it looks healthy but isn't

`apm marketplace check` reports every entry OK — but it only checks **ref
resolvability** (does the path/repo resolve), not whether the target is a
loadable native plugin. So CI is green while `/plugin install` is broken.

## The `.apm/` question (resolved)

`packages/<name>/.apm/` **is tracked in git — it is authoring SOURCE, not an
install artifact.** `apm_modules/` (gitignored, empty) is the install target.
So "just point at `.apm/`" is not an option for native hosts: only `apm install`
understands `.apm/`.

## Symlink option (rejected)

A `skills -> .apm/skills` symlink does NOT cleanly serve both ecosystems:

- Claude Code **follows** symlinks that resolve inside the marketplace
  (dereferenced + copied into cache). So it would work for `/plugin`.
- `apm install` integrity verification **explicitly rejects any symlink** in a
  packed bundle. So it breaks the APM path.

Opposite policies → symlinks are out.

## Decision driver: native layout is a viable SINGLE source

VERIFIED locally: a package authored in **native plugin layout**
(`skills/<name>/SKILL.md` + `.claude-plugin/plugin.json`, no `.apm/`) installs
fine via `apm install` too — APM's `normalize_plugin_directory`
(`deps/plugin_parser.py:135`) converts native → `.apm/` at staging, then
integrates. So native layout is consumable by **both** `/plugin` AND
`apm install`. APM-native `.apm/` layout is consumable by **only** `apm install`.

This is the crux: **native plugin layout is the strict superset**. Authoring (or
generating) native layout at each package root makes the marketplace work for
Claude `/plugin` without losing the `apm install` path.

## What Claude `/plugin` can carry vs what stays APM-only

Per `microsoft/apm` `targets.py` (claude profile) and the Claude plugin spec:

| Asset (count) | Native Claude plugin component? | Notes |
|---|---|---|
| skills (36) | ✅ `skills/<name>/SKILL.md` | direct |
| agents (4) | ✅ `agents/*.md` | `.agent.md` → `.md` |
| hooks (18) | ✅ `hooks/hooks.json` | JSON already in native schema; only the **path** differs. `${PLUGIN_ROOT}/scripts/…` is the native var |
| mcp (8) | ✅ `.mcp.json` (plugin) / `mcpServers` | declared in `apm.yml mcp:` deps today; needs emitting as `.mcp.json` |
| commands | ✅ `commands/*.md` | we have none today (`.apm/prompts` → commands on install) |
| steering (16) + instructions | ❌ **APM-only** | Claude plugins have **no "rules"/instructions primitive**. `.apm/instructions → .claude/rules` is an APM-install-only mapping. Context/steering docs are not a native plugin component |
| bundles (35) | ⚠️ partial | a bundle = dependency aggregator. Native Claude marketplaces have **no transitive plugin deps**; a "bundle" can't pull member plugins via `/plugin`. Stays APM-only (or must be flattened) |

**So: skills, agents, hooks, mcp, commands → fully native-installable. Steering /
instructions and bundles → remain APM-managed.** That's the practical answer to
"what stays with APM": the *opinionated steering layer* and the *bundle
aggregation* are APM-only; the *executable primitives* can go native.

## Options to make it functional

### Option A — Generate per-package native plugin layout into the source tree (RECOMMENDED for full native support)

For each package that ships a native-capable primitive, generate at the package
root (committed, alongside `.apm/`):
- `.claude-plugin/plugin.json` (name/version/description/author/license)
- `skills/<name>/` (copy of `.apm/skills/<name>/`)
- `agents/*.md` (from `.apm/agents/*.agent.md`)
- `hooks/hooks.json` (merge of `.apm/hooks/*-claude-hooks.json`)
- `.mcp.json` (from `apm.yml mcp:` block)

This is exactly what `apm pack --format plugin` produces — but into
`./build/<name>-<version>/`, NOT the source tree, and the marketplace doesn't
point there. So we drive it ourselves (custom generator in `.apm/scripts/`,
wired into the existing `render-docs.py all` + drift-check CI).

Pros: `/plugin install` works for ~66 primitive packages; `apm install` still
works (native layout normalizes back). Single marketplace serves both.
Cons: doubles on-disk asset copies (native + `.apm/`); generator + drift gate to
maintain; steering/bundles still can't go native (acceptable).

Trade-off knob: keep `.apm/` as the **only** hand-authored source and treat
native dirs as **generated artifacts** (like the marketplace block today) so
there's one source of truth and a CI staleness check.

### Option B — Author packages natively, drop `.apm/` for primitives

Flip the source of truth: author `skills/`, `agents/`, `hooks/hooks.json`
natively; let `apm install` normalize on the way in. Steering packages keep
`.apm/instructions` + `.apm/context` (no native equivalent).

Pros: no duplication, no generator; native-first.
Cons: large one-time migration of 66 packages; loses APM's `.apm/` authoring
conventions (prompts→commands transform, cross-target deploy_root, etc.); Codex
hook variants (`*-codex-hooks.json`) have no native plugin home.

### Option C — Keep marketplace APM-only; document `apm install` as the install path (LOWEST EFFORT)

Accept that the marketplace is an `apm install` catalog, not a `/plugin` catalog.
Fix only the **false advertising**: stop implying native `/plugin` support, make
`apm marketplace check` / a new gate assert what's actually loadable, and
document `apm marketplace add … && apm install <pkg>@…`.

Pros: zero package churn; everything already works via `apm install`.
Cons: no native Claude `/plugin` experience — which is the more practical UX the
user explicitly wants.

### Option D — Hybrid (RECOMMENDED overall)

- **Primitives (skills/agents/hooks/mcp/commands)** → Option A generated native
  layout, so `/plugin install` works.
- **Steering + bundles** → stay APM-only; mark them in the marketplace (or split
  into a second APM-only catalog) so native users aren't offered un-loadable
  entries.
- Add a real **native-loadability gate** in CI (validate each native-capable
  `source` actually has `.claude-plugin/plugin.json` or top-level
  `skills/`/`agents/`/`hooks/`), replacing the resolvability-only check.

## Proposed implementation (Option D)

1. **New generator** `.apm/scripts/build-native-plugins.py` (driven by the
   existing `build_inventory.py` walk):
   - for each package whose classification ∈ {skill, agent, hooks, mcp} (and any
     with commands), emit native layout at the package root from `.apm/` source;
   - write per-package `.claude-plugin/plugin.json`;
   - merge `*-claude-hooks.json` → `hooks/hooks.json`;
   - emit `.mcp.json` from the `apm.yml mcp:` block;
   - idempotent + `--check` for the drift gate.
2. **Wire into** `render-docs.py all` (or a sibling `build-artifacts` step) and
   the `build-artifacts.yml` staleness diff so native dirs can't drift.
3. **`.gitignore`/tracking**: decide native dirs are generated-but-committed
   (like the marketplace block) so the marketplace `source` resolves on a fresh
   clone without a build step. (Native consumers clone the repo; the dirs must be
   present.)
4. **Marketplace split or tagging**: keep steering/bundles out of the native
   catalog (they 404 under `/plugin`), or tag them clearly as `apm-only`.
5. **CI gate**: add native-loadability assertion; keep `apm marketplace check`
   for ref health.
6. **Codex**: document that `.agents/plugins/marketplace.json` is `apm install`
   (and Copilot CLI) consumed; no native Codex `/plugin` claim until verified.

## Follow-up research (VERIFIED 2026-06-27, code.claude.com docs)

### Claude DOES have native bundling — `dependencies` in plugin.json

A Claude plugin manifest supports a `dependencies` array (plugin-to-plugin, with
npm-style semver ranges). Installing a plugin auto-installs + transitively
enables its dependencies; disable refuses while a dependent is enabled; uninstall
`--prune` removes orphaned deps. **A components-free plugin (just
`.claude-plugin/plugin.json` with `name` + `dependencies`) is the native
equivalent of our APM dependency-aggregator bundles.** Caveats:

- Dependencies resolve **within the same marketplace** by default; cross-
  marketplace needs `allowCrossMarketplaceDependenciesOn` allowlist in the root
  marketplace.json. Our single generated marketplace.json → intra-marketplace is
  free; the external deps (`wshobson/agents/...`) in some bundles would need the
  allowlist or to be pulled into our marketplace.
- Version pinning uses git tags in `{plugin-name}--v{version}` convention. We
  already tag `{name}-v{version}` (single dash) via release-please — **note the
  Claude convention is a DOUBLE dash** (`--v`); reconcile if we want native
  version constraints, or omit `version` to track every commit.
- The "meta-plugin" symlink trick (link sibling plugins' `skills/` into your own)
  is a *separate*, build-time copy mechanism — NOT the dependency aggregator.
  Don't conflate. Bundles → use `dependencies`.

So bundles ARE expressible natively. The 32 pure-aggregator bundles become
component-free plugins with `dependencies`. (See split note below for the 3 that
also ship primitives.)

### Bundles shipping built-in primitives (must split — user decision)

Only 3 of 35 bundles ship their own primitives:

- **`speckit`** — ships skills (2) + agents (6) + hooks (2) AND aggregates a dep.
  This is a multi-primitive package, not a pure bundle. Split: agents → e.g.
  `agent-speckit-*` (or one `speckit-agents` skill-less plugin), skills →
  `speckit-bugfix` / `speckit-setup` skill packages, hooks → `hooks-speckit-*`,
  and a thin `speckit` aggregator plugin with `dependencies` on those.
- **`code-intelligence`** — pure aggregator EXCEPT it ships 2 hook files. Split
  the hooks into a `hooks-code-intelligence` package; `code-intelligence` becomes
  a pure dependency bundle.
- **`speckit-dag-hooks`** — ships 2 hook files + depends on `speckit`. Already
  essentially a hooks package mislabeled as bundle; reclassify/rename to
  `hooks-speckit-dag` (it's already `hooks-`-shaped in content).

### Steering is NOT natively installable — and cannot be cleanly refactored to be

VERIFIED: Claude plugin components are **skills, commands, agents, hooks,
MCP servers, LSP servers, monitors** — there is **no `rules`/`memory`/
`instructions`/`context` component**. Critically:

- *"A `CLAUDE.md` file at the plugin root is not loaded as project context.
  Plugins contribute context through skills, agents, and hooks rather than
  CLAUDE.md."* — a plugin cannot ship always-on guidance.
- Skills are **model-invoked / on-demand**: only the one-line description sits in
  context; the body loads only when Claude self-selects it or you invoke it. The
  docs explicitly say for *"instructions that … be in context all the time, use
  rules … skills only load when invoked or relevant."* So a skill is the WRONG
  carrier for always-on opinionated steering.
- `.claude/rules/*.md` IS the always-on mechanism — but it is written by the
  user/tooling, **never delivered by a plugin**.

**Conclusion:** our 16 steering packages + the `instructions` carried by hooks
packages **cannot become native `/plugin` installs** without losing their
always-on semantics. The only plugin-native always-on levers are
`settings.json:{agent:…}` (hijacks the whole main thread — unsuitable) or
managed-settings `claudeMd` (org policy, not distributable). **Steering stays
APM-only** (`apm install` → `.claude/rules/`), exactly as it works today. This is
not a gap to fix; it's a Claude platform limitation. Tag steering as apm-only in
the catalog.

## CRITICAL empirical finding: plugin.json can point at `.apm/` — minimal duplication

Tested with the real `claude` CLI 2.1.195 via `claude --plugin-dir <dir> plugin
details`. A per-package `.claude-plugin/plugin.json` with **component-path
overrides** can reference the EXISTING `.apm/` content for most kinds — no
content move:

| Component | Override that WORKS | Move needed? |
|---|---|---|
| **skills** | `"skills": "./.apm/skills"` (dir of `<name>/SKILL.md`) | ❌ NO — discovered in place |
| **hooks** | `"hooks": "./.apm/hooks/<pkg>-claude-hooks.json"` (file) | ❌ NO — and JSON is already native schema |
| **MCP** | root `.mcp.json` (auto-discovered) | n/a — generate from `apm.yml mcp:` block (no `.apm/` content exists to move) |
| **agents** | override into `.apm/` FAILS (dir-string breaks load; file-array finds 0) | ✅ YES — must materialize at native `agents/*.md` |

Native-root `agents/demo-agent.md` auto-discovers fine; only the `.apm/` override
is unreliable. `mcpServers` override into `.apm/` also found 0 — use root
`.mcp.json`.

**Implication for the generator:** for the 36 skill + 18 hook packages we emit
ONLY a small generated `plugin.json` (with `skills`/`hooks` overrides) — zero
content duplication. Only **agents** (4 agent packages + any agents inside
speckit) need files materialized at root `agents/*.md`, and **MCP** (8 packages)
need a generated root `.mcp.json`. Duplication is now marginal, not 66×.

### Answers to the user's two questions

- **Can APM generate the per-package `plugin.json`?** Partially. `apm pack
  --format plugin` run *per package* emits a `.claude-plugin/plugin.json` but it
  is **bare metadata only** (name/version/description/author/license) with **no
  component-path overrides**, so skills stay undiscovered (Skills (0)). `apm
  plugin init` only scaffolds. So we still need our own generator that emits
  `plugin.json` **enriched with the `skills`/`hooks` overrides** (and
  `dependencies` for bundles). Cleanest to generate the whole file ourselves from
  `build_inventory.py`, consistent with the existing `render-docs.py` approach.
- **If we ship `plugin.json`, do we still need to move content from `.apm/` to
  root?** Mostly NO. Skills + hooks stay in `.apm/` (referenced via overrides).
  Only agents must be materialized at root `agents/*.md`, and MCP needs a
  generated root `.mcp.json`.

## REVISED ARCHITECTURE: move to native-root layout (drop `.apm/` for portable primitives)

Tested with `apm` 0.21.0 + `claude` 2.1.195. A package authored in **native-root
layout WITH a `.claude-plugin/plugin.json`** is consumable by BOTH ecosystems
from a SINGLE source — no `.apm/`, no overrides, no duplication:

| Source (native root) | `apm install --target claude` | `apm install --target codex` | `/plugin install` |
|---|---|---|---|
| `skills/<n>/SKILL.md` | → `.claude/skills/<n>/` ✅ | → `.agents/skills/<n>/` ✅ | discovered ✅ |
| `agents/*.md` | → `.claude/agents/*.md` ✅ | → `.codex/agents/*.toml` ✅ (APM transforms format!) | discovered ✅ |
| `.mcp.json` (root) | configured ✅ | configured ✅ | discovered ✅ |

The load-bearing detail: **`apm install` only discovers native-root `agents/`
when `.claude-plugin/plugin.json` is present** — the manifest triggers APM's
`normalize_plugin_directory` (native→`.apm/` at staging). Without it, native-root
skills still integrate but agents are MISSED. So every native-layout package MUST
ship `.claude-plugin/plugin.json`.

**This supersedes the "keep `.apm/`, point overrides at it" approach.** Cleaner:
ONE layout (native root), authored or generated, serves Claude `/plugin`, Codex
(via apm install), and Claude (via apm install). APM round-trips it.

### HOOKS — deep dive (VERIFIED with apm 0.21.0 + claude 2.1.195)

APM routes hook files to targets **by filename-stem suffix**
(`hook_integrator.py:417-464`, `_HOOK_FILE_TARGET_SUFFIXES`):

- `*-claude-hooks.json` / `claude-hooks.json` → **claude only**
- `*-codex-hooks.json` / `codex-hooks.json` → **codex only**
- any other stem incl. **`hooks.json`** → **UNIVERSAL → deployed to every target**

Claude `/plugin` discovery is different: it auto-discovers ONLY `hooks/hooks.json`
by name; it will NOT find `hooks/claude-hooks.json`. A `plugin.json` `hooks` key
can override the path (string or array → loads that file for `/plugin`).

**The irreconcilable collision (empirically proven):**

| Approach | Claude `/plugin` | `apm install` claude | `apm install` codex |
|---|---|---|---|
| root `hooks/hooks.json` only (=claude variant) | ✅ loads it | ✅ | ❌ **LEAKS** — universal `hooks.json` deploys Claude hook to codex too |
| root `hooks/{claude,codex}-hooks.json`, no `plugin.json hooks` key | ❌ finds 0 (no `hooks.json`) | ✅ routed | ✅ routed |
| root `hooks/{claude,codex}-hooks.json` + `plugin.json hooks:"./hooks/claude-hooks.json"` | ✅ loads claude | ✅ | ❌ **LEAKS** — the `hooks` key string is treated as a synthetic universal `hooks.json` and reaches codex |
| `plugin.json hooks: ["./.apm/hooks/x-claude-hooks.json"]` (array) | ✅ loads claude | ⚠️ `apm install` crashed `Not a directory` on the array path |

Proven with a `hooks-worktree`-like case (Claude has a hook, codex is `{}`): every
approach that makes Claude `/plugin` see the hook ALSO leaks the Claude hook into
the codex `apm install`, because anything Claude can auto-discover or that the
`hooks` key names is universal-routed by APM.

**Conclusion — hooks cannot share a single file across both ecosystems.** The
only clean design:

- Keep the per-target authored files under **`.apm/hooks/<pkg>-{claude,codex}-hooks.json`**
  as the source of truth for `apm install` (suffix-routed, no leak). KEEP `.apm/`
  for hook packages.
- Generate a native **`hooks/hooks.json` (= the claude variant)** purely for
  Claude `/plugin install`, and DO NOT add a `hooks` key to `plugin.json`.
  Because `apm install` consumers use the `.apm/` files (and APM's plugin
  normalizer also reads root `hooks.json` as universal → leak), **the generated
  root `hooks/hooks.json` is ONLY safe if such a package is consumed by `/plugin`,
  not by `apm install`.**
- This means hook packages have a genuine **split-consumer** caveat: `/plugin`
  users get `hooks/hooks.json`; `apm install` users get `.apm/hooks/*` — and the
  two must not both be active. Flag this; do NOT ship a universal `hooks.json`
  that `apm install` would also pick up. (Safest: generate `hooks/hooks.json`
  AND `.gitignore`/exclude it from the apm-install content set, or document that
  hook packages are `/plugin`-only on the native side.)

(original note retained below)

### The exception: HOOKS must stay per-tool, generated in CI

VERIFIED: 10 packages have genuinely DIFFERENT claude vs codex hooks (e.g.
`agent-coder` codex matcher adds `apply_patch`; `hooks-worktree` Claude has
`WorktreeCreate`/`WorktreeRemove` events Codex lacks → codex hooks = `{}`). A
single native `hooks/hooks.json` is Claude-schema-only and cannot carry the Codex
variant. So:

- **Hooks remain authored as two files** (`<pkg>-claude-hooks.json`,
  `<pkg>-codex-hooks.json`) — keep these under `.apm/hooks/` (APM install reads
  them per-target) AND generate the native `hooks/hooks.json` (= the claude
  variant) in CI for `/plugin install`.
- So hook packages are the one kind that keeps a small `.apm/hooks/` AND gets a
  generated native `hooks/hooks.json` + `plugin.json`.

### Net layout per package kind (revised)

| Kind (count) | Authored layout | Generated in CI | `.apm/` kept? |
|---|---|---|---|
| skills (36) | native `skills/<n>/SKILL.md` | `plugin.json` | no |
| agents (4) | native `agents/*.md` | `plugin.json` | no |
| mcp (8) | `apm.yml mcp:` block | `.mcp.json` + `plugin.json` | no |
| hooks (18) | `.apm/hooks/*-{claude,codex}-hooks.json` + `scripts/` | native `hooks/hooks.json` (=claude) + `plugin.json` | YES (codex variant) |
| steering (16) | `.apm/instructions` + `.apm/context` | nothing native (apm-only) | YES |
| bundles (35) | `apm.yml dependencies:` | `plugin.json` w/ `dependencies` | no |

Migration: skills/agents move `.apm/skills`→`skills`, `.apm/agents/*.agent.md`→
`agents/*.md` (drop `.agent.md`→`.md`); generate `plugin.json` everywhere;
steering + codex-hooks stay `.apm/`.

## Version-tag decision (user): move to double-dash `{name}--v{version}`

Claude's native dependency resolution + `claude plugin tag` use
`{name}--v{version}` (double dash). Our release-please currently produces
`{name}-v{version}` (single). Decision:

- Switch the canonical tag scheme to **double-dash** so native `/plugin`
  version constraints resolve.
- **Backfill**: recreate existing single-dash tags as double-dash equivalents
  (keep both for backwards-compat; do not delete the old ones).
- Update `apm.yml marketplace.build.tagPattern` → `{name}--v{version}` and the
  release-please config (`tag-separator`/component tagging) to emit double-dash.
  Verify release-please can express a double-dash separator; if not, post-process
  tags in the release workflow.

## External-dep bundles (user): cross-marketplace allowlist

Bundles with `wshobson/*` external deps → add
`allowCrossMarketplaceDependenciesOn` to our generated marketplace.json so native
`/plugin` can pull them from their marketplace. Document that users must also add
that marketplace.

## Splitting (user): split only what isn't genuinely tied

- **speckit** — stays as ONE multi-primitive plugin (Claude allows skills +
  agents + hooks in one plugin dir; they're genuinely tied). Just fix
  classification + generate native layout (its agents materialized at root). No
  forced split.
- **code-intelligence** — its 2 hook files: keep with the bundle only if tied;
  otherwise the bundle becomes a pure `dependencies` plugin and hooks move to a
  small hooks package. (Decide during impl — the hooks look incidental.)
- **speckit-dag-hooks** — already hooks-shaped; reclassify as a hooks package.

## VALIDATION on REAL repo packages (worktree feat/native-marketplace)

### Non-hook native-root migration — ALL PASS

Prototyped 3 real packages converted to native-root layout (`.apm/skills`→
`skills`, `.apm/agents/*.agent.md`→`agents/*.md`, `apm.yml mcp:`→`.mcp.json`),
each + a generated `.claude-plugin/plugin.json`. Full matrix:

| Real package | Claude `/plugin` | `apm install` claude | `apm install` codex |
|---|---|---|---|
| code-review (skill) | ✅ Skills(1) | ✅ `.claude/skills/` | ✅ `.agents/skills/` |
| agent-coder (agent) | ✅ Agents(1) | ✅ `.claude/agents/coder.md` | ✅ `.codex/agents/coder.toml` (APM converts md→toml) |
| mcp-context7 (mcp) | ✅ MCP(1) | ✅ configured | ✅ `.codex/config.toml` |

Native-root is CONFIRMED viable for skills/agents/mcp on real packages, all
three consumption paths. Proceed with the migration for these kinds.

### Hook leak — CONFIRMED real end-to-end (not synthetic)

Real `hooks-worktree` (claude has `WorktreeCreate`/`WorktreeRemove`; codex
hooks = `{}`):

- Current `.apm/`-only state: ✅ correct — codex install = empty hooks, claude =
  both events. No leak today.
- After adding a generated root `hooks/hooks.json` (= claude variant) for
  `/plugin`: `claude --plugin-dir` correctly shows Hooks(2); BUT
  `apm install --target codex` then deployed `WorktreeCreate`/`WorktreeRemove`
  into `.codex/hooks.json` — a LEAK of Claude-only events into Codex.

Root cause in APM source: `hook_integrator.py:582-618` `find_hook_files` scans
BOTH `.apm/hooks/*.json` AND root `hooks/*.json`; a stem of `hooks` has no target
suffix → universal → every target. There is NO `.apmignore` to exclude it.

**Therefore for hook packages the native `hooks/hooks.json` and the `apm install`
path are mutually exclusive on one committed tree.** Resolution options:
1. Hook packages stay `.apm/`-only for `apm install`; the native `hooks/hooks.json`
   is generated ONLY into the marketplace-consumed artifact, NOT committed to the
   package source that `apm install` reads (e.g. generated into a build/ plugin
   dir the marketplace points at — but the marketplace points at the source dir,
   so this needs the source to NOT contain a bare `hooks.json`).
2. Accept hook packages are `/plugin`-install-native only via a SEPARATE
   generated plugin dir, while `apm install` users keep `.apm/hooks`.
3. Simplest interim: hook packages remain `apm install`-only (as today); do NOT
   advertise them for native `/plugin` until a non-leaking layout is designed.

This is the one unresolved design point; everything else is settled.

## MIXED packages (hooks alongside another primitive) — the real hook nuance

7 packages ship `.apm/hooks` but are NOT classified `hooks-*` — they carry hooks
beside a native primitive, so "keep hooks apm-only" can't apply to the whole
package, only its hook component:

| Package | class | claude vs codex hooks |
|---|---|---|
| agent-coder | agent | **DIFFER** (codex adds `apply_patch` matcher) |
| code-intelligence | bundle | **DIFFER** |
| mcp-repomix | mcp | **DIFFER** |
| speckit | bundle | **DIFFER** |
| speckit-dag-hooks | bundle | **DIFFER** |
| unstuck | skill | **DIFFER** |
| secrets-scan | skill | identical |

**Refined rule (verified on real agent-coder + secrets-scan):** the leak ONLY
bites when claude ≠ codex hooks.

- **Identical hooks** (secrets-scan): generated root `hooks/hooks.json` is correct
  for BOTH targets; APM dedups against the suffix files ("2 adopted"); codex got
  the single correct `Bash` matcher. `/plugin` loads skill + hook. ✅ SAFE — the 8
  identical-hook packages (incl. secrets-scan + most hooks-* pkgs) can ship a
  native `hooks/hooks.json` with no leak.
- **Differing hooks** (agent-coder): codex install got BOTH the correct
  `apply_patch|Edit|Write|MultiEdit` (from codex-hooks.json) AND the leaked
  `Edit|Write|MultiEdit` (from universal hooks.json) → duplicate/wrong. ✗ LEAK.
  The ~10 differing-hook packages cannot ship a committed native `hooks/hooks.json`
  without corrupting the codex apm-install.

So the split is by **hook-variant-equality**, not by package classification:

- **Native primitive (skill/agent/mcp/bundle) is ALWAYS safe to take native-root**
  for the skill/agent/mcp/dependencies part — that's unaffected by the hook issue.
- **Hook component**: ship native `hooks/hooks.json` ONLY when claude == codex.
  When they differ, do NOT commit a native `hooks/hooks.json`; that package's hook
  is `/plugin`-unavailable (but its skill/agent/mcp still works natively, and
  `apm install` still gets the correct per-target hook).

Net: a differing-hook mixed package (e.g. agent-coder) ships native-root agent +
plugin.json (so `/plugin` gets the agent), keeps `.apm/hooks/{claude,codex}` for
apm install, and simply omits a native `hooks/hooks.json` (so `/plugin` users get
the agent but not the hook). Identical-hook packages get the hook natively too.

## Steering NOT installable as a plugin — EMPIRICALLY CONFIRMED (not just docs)

Tested against real `claude` CLI 2.1.195 (earlier this was docs-only; the docs
were wrong about Codex, so verified directly):

1. `plugin.json` with `rules`/`instructions`/`memory` keys + matching dirs →
   `claude plugin details` shows 0 components, ~0 always-on tokens. Keys
   unrecognized.
2. `claude plugin init --with` lists the COMPLETE supported component set:
   **skills, agents, hooks, mcp, lsp, output-style, channel**. No
   rules/instructions/memory/context.
3. Runtime A/B with a secret-word marker via `claude -p`:
   - Plugin root `CLAUDE.md` (`--plugin-dir`) → model answered **NONE** (not
     injected).
   - Plugin-shipped `rules/00-marker.md` dir → **NONE** (not loaded).
   - Project `.claude/rules/00-marker.md` (the apm-install path) → model answered
     **BANANA-7842** (loaded, always-on). ✅

CONCLUSION: a Claude plugin genuinely cannot deliver always-on steering. The
`.claude/rules/` mechanism works perfectly but is only reachable via `apm
install` (or hand-placement), NOT via `/plugin install`. Steering's 16 packages
stay apm-only — confirmed, not assumed. (Codex equivalent: steering→`.codex/`
rules via apm install; Codex native `plugin add` likewise has no rules component.)

## "apm-only" tagging — what's actually possible (verified)

There is NO native "block this from /plugin" flag in APM 0.21.0:
- Codex `policy.installation` is **hardcoded `AVAILABLE`** (output_mappers.py:253)
  — not per-package configurable.
- No per-output package exclusion / `claude_only` / `codex_only` in the
  marketplace schema. Every package appears in BOTH catalogs.
- Fields that DO pass through to the Claude catalog per plugin: `name`,
  `description`, `version`, `author`, `license`, `repository`, `tags`,
  `homepage`. (Codex catalog: `name`, `source`, `policy`, `category`.)

Behavior when a component-less steering package IS installed natively (tested):
- Claude `/plugin` + Codex `plugin add` → **silent no-op success**: installs,
  reports 0 components, contributes nothing. Not an error, but a TRAP — user
  believes steering installed; got nothing.

So "tag as apm-only" can only mean one of these CONCRETE mechanisms:

1. **`tags` + `description` marker** (soft, Claude catalog only): add a tag like
   `apm-install-only` and prefix the description (e.g. "[apm install only] …").
   Passes through to `.claude-plugin/marketplace.json`. Discoverable by a human
   browsing, but does NOT prevent `/plugin install`; codex catalog has no tags
   field so this is Claude-only and unenforced.

2. **EXCLUDE steering from the marketplace entirely** (hard, recommended for the
   native side): don't list the 16 steering packages (and any apm-only ones) in
   the `marketplace:` block at all. They remain installable via
   `apm install srobroek/agentic-packages/packages/<name>` by path. Native
   `/plugin`/`codex plugin` users never see a plugin that would no-op. This is the
   only mechanism that actually PREVENTS the trap. Cost: steering isn't
   discoverable via marketplace browse — document the `apm install` path in README.

3. **Second, APM-only marketplace** (structured): keep the native marketplace
   (primitives + bundles) and ALSO emit a separate catalog/list for steering
   consumed only via `apm install`/`apm marketplace`. APM `marketplace:` supports
   one block per repo, so this means a second doc the README links, not a second
   `outputs:` — more machinery for marginal benefit.

4. **Upstream feature request**: ask APM to expose `policy.installation:
   UNAVAILABLE` (Codex has the field; Claude marketplace spec may have an
   equivalent) and/or per-output package filtering. Cleanest long-term.

RECOMMENDATION: **Option 2** (exclude steering from the generated marketplace; it
stays `apm install <path>`-only) + a README section listing steering packages and
their install command. It's the only choice that prevents the silent-no-op trap,
and it's a trivial filter in the generator (skip classification==steering, and
the instructions-only hooks content, when emitting marketplace entries). Pair
with Option 1's description marker IF we still want them listed for discovery.

## Rejected idea: split differing-hook packages into `-claude` / `-codex` packages

Does APM support per-package target restriction so a `pkg-claude` package only
ever installs to claude (avoiding the universal-hooks.json leak)? **NO — verified
in source + empirically (apm 0.21.0):**

- **Install does not gate by package target.** A package declaring `target:
  claude` STILL installs to codex when you run `apm install <pkg> --target codex`
  (tested: the skill deployed to `.agents/skills/` regardless). The `--target`
  flag / consumer `targets:` decides deployment; the package's own `target:` is
  used for MCP config plumbing, not as an install gate. So nothing stops a codex
  user from installing the `-claude` variant and getting the wrong hook.
- **Marketplace cannot exclude a package from one catalog.** `PackageEntry`
  (`yml_schema.py:320-360`) has NO `target`/`targets` field, and both
  `ClaudeMarketplaceMapper` and `CodexMarketplaceMapper` iterate the same
  `config.packages`. Every entry appears in BOTH `.claude-plugin/marketplace.json`
  AND `.agents/plugins/marketplace.json`. A `-claude` package would still be
  listed in the codex catalog and be codex-installable.

So the split doesn't isolate targets — APM has no mechanism to bind a package to
one harness at either the marketplace or install layer. The
hook-variant-equality rule (generate native `hooks/hooks.json` only when
claude==codex; otherwise hook is `/plugin`-unavailable) remains the correct
approach. (A `-claude`/`-codex` split would only duplicate packages without
fixing the leak.)

## MAJOR REFRAMING: Codex 0.137.0 has a NATIVE plugin marketplace

Earlier research (from docs) concluded Codex had no native plugin loader. That is
**OUTDATED**. Verified with `codex` CLI 0.137.0:

- `codex plugin marketplace add <path|owner/repo|git-url>`, `codex plugin
  list/add/remove` exist.
- Pointed at our repo, `codex plugin marketplace list` + `codex plugin list` READ
  the APM-generated `.agents/plugins/marketplace.json` and list all 117 plugins.
- `codex plugin add code-review@srobroek-agentic` (current `.apm/` layout) FAILS
  with **`Error: missing plugin.json`** — the SAME root cause as Claude. The
  native-root migration fixes BOTH ecosystems identically.
- Native-root packages (skills/agents) install cleanly via `codex plugin add`
  into `$CODEX_HOME/plugins/cache/<mkt>/<name>/<version>/`, preserving the native
  layout (`.claude-plugin/plugin.json`, `skills/`, `agents/`, `hooks/hooks.json`).
- A plugin's native `hooks/hooks.json` is consumed by Codex's native plugin
  loader and registered under `[plugins."<name>@<mkt>"]` in `config.toml`. Codex
  WANTS the `apply_patch` matcher — i.e. the codex-relevant matcher belongs in the
  one native `hooks/hooks.json`.

### This dissolves most of the hook problem

The hook leak was a problem of the **`apm install`** integration path (universal
`hooks.json` routed to every target). But the NATIVE plugin path (`/plugin
install` for Claude, `codex plugin add` for Codex) consumes the SAME native
`hooks/hooks.json` and each harness fires only the matchers it understands
(Claude ignores `apply_patch`; Codex ignores `Edit|Write|MultiEdit`-only Claude
tools / Claude-only events). So a SINGLE superset `hooks/hooks.json` serves both
NATIVE loaders.

The leak ONLY matters for the legacy `apm install <pkg> --target codex` path. If
native plugin install (Claude `/plugin` + `codex plugin`) becomes the primary
distribution, hooks unify and the whole differing-variant problem largely
evaporates for native consumers.

## Hook UNIFICATION analysis (user ask: can minor refactor make hooks universal?)

Claude TOLERATES `apply_patch` in a matcher (loads fine, never fires — verified).
Categorizing the 10 differing packages by WHY they differ:

| Cat | Packages | Cause | Unifiable to one superset file? |
|---|---|---|---|
| A | agent-coder, hooks-git-workflow, hooks-quality | codex adds `apply_patch` to Edit\|Write matcher | YES — use `apply_patch\|Edit\|Write\|MultiEdit` everywhere; Claude ignores apply_patch |
| B | mcp-repomix, agent-coder | codex drops `async`/`timeout` fields | YES — keep the fields; verify Codex ignores unknown keys (likely) |
| C | hooks-worktree, hooks-subagent-worktree, code-intelligence | Claude-only EVENTS (WorktreeCreate, PreToolUse:Agent, SessionStart) that codex variant omits | YES for the FILE (superset keeps the events; Codex ignores events it lacks) — needs verifying Codex tolerates unknown event keys |
| D | speckit, speckit-dag-hooks, unstuck | deeper divergence: Claude `Skill`/`UserPromptExpansion` vs codex `Bash`/`UserPromptSubmit`; `${CLAUDE_PROJECT_DIR}` vs `$(git rev-parse)` | PARTIAL — needs real refactor; some matchers/commands are genuinely harness-specific |

Cats A+B+C (7 packages) look unifiable into ONE superset `hooks.json` that both
harnesses load and each filters. Cat D (3 packages) needs genuine per-harness
logic and may stay split. NEXT STEP: empirically verify Codex tolerates (a)
unknown event keys, (b) unknown fields, (c) Claude-only matchers — then collapse
A/B/C variants to single files (which ALSO makes them leak-free on apm install,
since identical variants dedup).

## Revised plan deltas (after follow-up research)

- Bundles → emit a component-free native plugin with `dependencies` (intra-
  marketplace). Decide tag convention (`--v` vs our `-v`) or drop `version`.
- Split the 3 primitive-shipping bundles into primitive packages + thin
  aggregators BEFORE generating native layout.
- Steering + the `instructions`-only hooks content → remain apm-only; tag in
  catalog; do not attempt native conversion.
- External deps (`wshobson/*`) inside bundles: either vendor into our marketplace
  or add cross-marketplace allowlist; otherwise native bundle install will not
  pull them.

## Open decisions for the user

- **Scope**: full native support for primitives (Option D), or just fix the
  framing and lean on `apm install` (Option C)?
- **Source of truth**: keep `.apm/` authoritative and generate native dirs
  (less churn, some duplication), or flip to native-authored (Option B)?
- **Generated-but-committed vs build-on-clone** for the native dirs.
- **Steering/bundle handling** in the catalog: drop, tag, or second catalog.
