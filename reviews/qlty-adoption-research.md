# qlty adoption into project-setup — research & recommendation

**Date:** 2026-06-28 · **Branch:** feat/project-setup-modular-redesign · **Status:** decision doc
**Verdict:** adopt-PARTIAL (qlty for the language linter/formatter/smell layer; keep a thin commit-msg git-hook layer)

---

## 1. Executive answer

**Can qlty be the "one and only" linter/fmt/smell layer for project-setup? No — Partial.** qlty genuinely subsumes the *language* analysis layer (ruff, biome, prettier, shellcheck, clippy, gofmt, gitleaks, trufflehog, markdownlint, yamllint, hadolint, actionlint are all first-class plugins, each pinnable to an exact version in `qlty.toml`), so it is a real consolidation of that slice. But it provably **cannot** be the single gate: qlty git hooks are **pre-commit + pre-push only — there is no commit-msg stage**, so `cocogitto-verify` and the `normalize-close-keywords` rewrite (both `stages:[commit-msg]`) have nowhere to run, and qlty has no conventional-commit plugin at any stage. A thin pre-commit (or native git-hook) layer must remain for commit-msg responsibilities, so the realistic outcome is a two-layer split, not a replacement.

---

## 2. What qlty is + its plugin model

**qlty** is a unified, multi-language code-quality CLI (lint + format + code-smell + security) with a plugin catalog, incremental/changed-files execution, and unified output. It is mature and actively maintained (the investigator verified v0.631.0 as of 2026-06-23; 362 releases; 2,555 commits). It is **Business Source License 1.1 (non-OSI)** — a single-vendor license, unlike the OSI-licensed per-tool zoo project-setup ships today.

**Plugin model** (sources below):

- Config lives in `.qlty/qlty.toml` (written by `qlty init`, which auto-detects file types and generates a baseline). Source: https://docs.qlty.sh/cli/quickstart.md
- Plugins are declared as repeated `[[plugin]]` blocks with an **exact version**:
  ```toml
  [[plugin]]
  name = "shellcheck"
  version = "0.9.0"

  [[plugin]]
  name = "stylelint"
  version = "15.10.3"
  extra_packages = ["stylelint-config-standard-scss@11.0.0"]
  ```
  Source: https://docs.qlty.sh/cli/qlty-toml.md
- Each plugin ships a `plugin.toml` carrying `known_good_version` and `latest_version`. **Critical:** for ruff today these are **equal** — `known_good_version = "0.14.6"`, `latest_version = "0.14.6"`. Source: https://raw.githubusercontent.com/qltysh/qlty/main/qlty-plugins/plugins/linters/ruff/plugin.toml
  → The "known-good" default is whatever was latest when that qlty CLI release was cut. It is a *snapshot-of-latest baked into the CLI version*, and it moves as the CLI moves. The docs do **not** state the default when a `[[plugin]]` omits `version` (treat as float-to-known-good until proven otherwise).
- Git hooks: **pre-commit and pre-push only.** No commit-msg stage exists. Source: https://docs.qlty.sh/cli/git-hooks.md
- Catalog confirmed to contain: ruff, biome, prettier, shellcheck, clippy, gofmt, gitleaks, trufflehog, markdownlint, yamllint, hadolint, actionlint. **Not found:** typos, gofumpt, taplo. Source: https://docs.qlty.sh/plugins.md

---

## 3. Coverage table — current zoo → qlty

Current tool layer is the vendored `.pre-commit-config.yaml`
(`modules/precommit-setup/templates/pre-commit-config.yaml`) plus the per-language `uv add --dev ruff …` / TS / Rust / Go tooling in the `lang-*` modules.

| Current tool / hook | Stage today | qlty status | Notes |
|---|---|---|---|
| ruff (lint+format) | pre-commit + frozen `rev` (spec 003) | **Replaced** | qlty `ruff` plugin, exact-pinnable. Double-pin hazard vs frozen 003 pin (see §4). |
| biome | (TS lang module) | **Replaced** | First-class plugin. |
| prettier | (TS lang module) | **Replaced** | First-class plugin. |
| shellcheck (`shellcheck-py` v0.10.0.1) | pre-commit | **Replaced** | First-class plugin. |
| clippy | (Rust lang module) | **Replaced** | First-class plugin. |
| gofmt | (Go lang module) | **Replaced** | First-class plugin. (gofumpt NOT in catalog.) |
| gitleaks (v8.24.3) | **pre-push** | **Partial** | Plugin exists; **stage semantics under qlty UNCONFIRMED** — qlty hooks are pre-commit/pre-push, must verify gitleaks runs at pre-push not per-commit. |
| trufflehog | n/a (alt secrets) | **Replaced** (capability) | First-class plugin; same pre-push-timing caveat. |
| typos (v1.32.0) | pre-commit | **NOT covered** | No `typos` plugin in catalog. Stays in retained layer. |
| pre-commit-hooks battery: check-json/toml/yaml, check-merge-conflict, check-case-conflict, check-shebang/executable, detect-private-key, end-of-file-fixer, trailing-whitespace, check-added-large-files | pre-commit | **NOT covered / UNVERIFIED** | qlty is a *linter/formatter* orchestrator, not a file-hygiene fixer battery. No evidence it reproduces these. Assume stays in retained layer until proven. |
| cocogitto-verify (conventional commit) | **commit-msg** | **NOT covered** | No conventional-commit/commitlint/cocogitto plugin AND no commit-msg stage. Hard blocker. |
| normalize-close-keywords (local `commit-msg-rewrite.sh`) | **commit-msg** | **NOT covered** | Local commit-msg *rewrite* — a hook class qlty is architecturally not built to host. `hooks-close-keywords` package would be orphaned. |

**Summary:** qlty cleanly replaces 6 language tools (ruff, biome, prettier, shellcheck, clippy, gofmt) and the secrets-scan *capability* (gitleaks/trufflehog, pending stage check). It does **not** cover typos, the file-hygiene battery (unverified), and **cannot** cover the two commit-msg hooks.

---

## 4. Determinism verdict — does qlty fit Tier-1 byte-identical + reproduce-zero-network?

**This is the make-or-break for THIS repo, and qlty fights the contract as written.**

Spec 003 established a hard determinism contract for the Tier-1 write layer (`specs/003-stack-resolver/spec.md`):
- **FR-005 / SC-005:** every persisted pin is registry-verified (PyPI/npm) and exact — *"no ranges, no latest; resolves latest at run time"* is explicitly the anti-goal.
- **FR-014 / SC-005:** the ruff-pre-commit hook `rev` MUST be **derived from the same frozen ruff pin** so local pre-commit, CI, and the manifest agree (`modules/lang-python/module.py`: `ruff_version` flows from the frozen plan into both `pyproject.toml` and the pre-commit `rev`).
- **SC-002 / FR-009:** reproduce mode replays committed pins with **zero network calls** and writes a byte-identical manifest (network-blocking test enforces it).

How qlty collides with this:

1. **Float-to-latest reintroduction (the exact thing SC-005 killed).** qlty's `known_good_version` is the snapshot-of-latest baked into each CLI release (ruff: `known_good == latest == 0.14.6`). A version-less `[[plugin]]` (and the docs don't promise otherwise) floats; and even a pinned plugin's *default* moves when you bump the CLI. Unless **every** plugin AND the qlty CLI are explicitly pinned, you have re-created run-time version resolution.
2. **Not part of the verify+freeze contract.** qlty pins are not registry-verified by `sdk.verify_pins`, not frozen into `answers.toml`, and not replayed by reproduce. They live in a parallel channel (`qlty.toml`) that the frozen-plan reproduce path neither produces nor checks. That is a determinism-channel split against 003's single-source-of-truth invariant.
3. **Double-pin / divergence hazard on ruff.** Routing ruff through qlty while spec 003 still derives the pre-commit `rev` from the frozen ruff pin gives ruff two authorities (frozen plan `rev` vs `qlty.toml`) — exactly the local/CI divergence SC-005 was written to prevent.
4. **No documented offline/no-network/lockfile mode.** The docs index has no offline-mode or lockfile page (`docs.qlty.sh/configuration` and `/analysis-configuration.md` both 404'd; `ci.md` is silent on runtime tool fetching). qlty installs tool runtimes/binaries on demand. **There is no evidence qlty can run network-free** the way reproduce mode requires — this is thin-data and a hard adoption gate (see §6 A/B test).

**Verdict:** qlty fits the *usability* goal (one binary, incremental runs, unified output) but **fights the byte-identical + reproduce-zero-network contract** unless you (a) pin every plugin AND the CLI version, (b) decide single ownership of the ruff pin, and (c) prove a network-free run. Without those three, adopting qlty silently re-breaks what spec 003 fixed.

---

## 5. Recommendation

**Adopt-PARTIAL: qlty for the language linter/formatter/smell layer + a retained thin commit-msg git-hook layer.** Do not full-replace; do not reject.

### Option A — Full replace (REJECTED)
Fails on the commit-msg gap alone (no stage, no plugin). Orphans `hooks-close-keywords`. Also accepts BSL-1.1 lock-in as a mandatory gate. Not viable.

### Option B — qlty-for-languages + thin git-hook layer (RECOMMENDED)
qlty owns ruff/biome/prettier/shellcheck/clippy/gofmt/gitleaks/trufflehog; a slimmed retained layer owns commit-msg + file-hygiene + typos.

Concrete project-setup module changes:
- **New `qlty-setup` module** (mirrors `precommit-setup` shape): write `.qlty/qlty.toml` from a template with **exact `version=` on every `[[plugin]]`**; run `qlty install`/hooks install as a documented side-effect (not part of deterministic scaffolding, like `pre-commit install` today).
- **`lang-python` (FR-014 decision required):** pick ONE owner of the ruff pin. Either (a) keep spec-003's frozen+registry-verified ruff pin authoritative and have `qlty.toml`'s ruff `version` be **derived from / asserted against** it (single source, two emitters), or (b) move ruff entirely to qlty and **formally retire FR-014/SC-005's ruff-rev derivation**. Do not leave both channels live. Recommendation: **(a)** — preserves the verify+freeze contract.
- **`precommit-setup` (slimmed):** drop the language linters that move to qlty (shellcheck). **Keep** `cocogitto-verify` + `normalize-close-keywords` (commit-msg), the pre-commit-hooks file-hygiene battery, and `typos` until qlty parity is proven. Keep gitleaks here at pre-push unless §6 confirms qlty's pre-push secrets timing.
- **`quality-hooks`:** unaffected (it only writes `.agents/hooks/quality-languages`).
- **Determinism plumbing:** pin the qlty CLI version (mise/tool config + CI), and either extend `verify_pins`/freeze to cover `qlty.toml` pins or document that the qlty layer is explicitly **outside** the Tier-1 byte-identical guarantee.
- **License posture:** make the qlty module **OPT-IN**, not the only path, given BSL-1.1 on a bootstrapping tool. Document a migration-exit (qlty.toml pins map back to per-tool pre-commit repos).

### Option C — Don't adopt (fallback)
Defensible if the determinism A/B (§6) fails or the BSL-1.1 sign-off is refused. The current OSI zoo already meets the contract; qlty's wins are usability, not correctness.

---

## 6. To verify before building (open unknowns)

1. **[HARD GATE] Network-free reproduce.** Bootstrap a repo on two machines / two dates; run qlty + the frozen-pin path; byte-compare formatter output AND confirm a reproduce-mode run makes **zero network calls** (network-blocking sandbox). If qlty re-resolves/downloads versions at runtime, fail the adoption. *(Data thin: no offline-mode docs found.)*
2. **Version-omitted behavior.** Confirm what a `[[plugin]]` with no `version` actually resolves to (float-to-latest vs baked known_good). Docs are silent. Pin everything regardless, but confirm the failure mode.
3. **gitleaks/trufflehog stage.** Confirm qlty can run secrets at **pre-push** (not per-commit) to preserve current `stages:[pre-push]` semantics. If pre-commit-only, keep secrets in the retained layer. *(coverage-map flagged this UNCONFIRMED.)*
4. **File-hygiene parity.** Verify whether qlty reproduces check-yaml/json/toml, end-of-file-fixer, trailing-whitespace, detect-private-key, check-merge-conflict, large-file. If not, they stay in the retained layer.
5. **qlty CLI version pinning in CI.** The documented action uses `qltysh/qlty-action/fmt@main` (a float). Confirm a pinnable ref/version input exists; pin it.
6. **typos replacement.** No `typos` plugin — decide keep-in-retained-layer vs drop the check.
7. **BSL-1.1 sign-off.** Explicit owner decision: acceptable for a mandatory layer of a bootstrapping tool, or opt-in only? Document the SPOF / single-vendor risk and exit plan.

---

### Sources
- https://docs.qlty.sh/plugins.md · https://docs.qlty.sh/cli/qlty-toml.md · https://docs.qlty.sh/cli/git-hooks.md · https://docs.qlty.sh/cli/quickstart.md · https://docs.qlty.sh/cli/ci.md
- https://raw.githubusercontent.com/qltysh/qlty/main/qlty-plugins/plugins/linters/ruff/plugin.toml
- Repo: `specs/003-stack-resolver/spec.md` (FR-005/FR-009/FR-014, SC-002/SC-005); `modules/precommit-setup/templates/pre-commit-config.yaml`; `modules/lang-python/module.py`
- **Thin/unverified:** offline-mode / lockfile (no doc page found; `configuration`/`analysis-configuration.md` 404); version-omitted default; gitleaks pre-push timing; file-hygiene parity.
