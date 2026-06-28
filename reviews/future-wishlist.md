# Future wishlist (out-of-roadmap ideas)

Ideas considered but NOT on the active spec roadmap (specs 006–016 +
`reviews/tier2-agentic-features-roadmap.md` ranks #1–#12). Each entry is a parked
candidate with enough context to pick it up later; none is committed work.

---

## W1 — Adopt `qlty` (qltysh/qlty) for the language linter/formatter/smell layer

**Status:** researched 2026-06-28 → **adopt-PARTIAL, opt-in**; parked pending owner
decision. Full decision doc: [`reviews/qlty-adoption-research.md`](./qlty-adoption-research.md).

**Idea (as proposed):** replace the per-tool lint/fmt zoo project-setup scaffolds
(ruff, biome, prettier, shellcheck, clippy, gofmt, gitleaks, typos, cocogitto, the
pre-commit-hooks battery) with `qlty` as the single linter/formatter/smell detector —
install qlty + plugins instead of N separate tools.

**Verdict — cannot be "one and only"; partial adoption only (3 verified blockers):**
1. **No commit-msg stage.** qlty git hooks are pre-commit + pre-push only (verified
   firsthand via docs.qlty.sh/cli/git-hooks). `cocogitto-verify` + the
   `normalize-close-keywords` rewrite both run at `commit-msg` → a thin git-hook layer
   MUST remain.
2. **Determinism collision.** qlty's `known_good_version` == `latest_version`
   (ruff 0.14.6, verified) and floats with the CLI release; no documented offline mode;
   pins live outside spec 003's verify→freeze→reproduce contract → naive adoption
   re-breaks SC-005 and double-pins ruff.
3. **License.** BSL 1.1 (verified — converts to GPLv3 on 2028-12-10), not OSI;
   single-vendor lock-in for a mandatory bootstrap gate.

**What it genuinely buys:** clean consolidation of the *language* layer (ruff, biome,
prettier, shellcheck, clippy, gofmt, gitleaks/trufflehog are first-class, exact-pinnable
plugins in one `.qlty/qlty.toml` + one binary). Does NOT cover typos, the file-hygiene
battery, or commit-msg.

**If picked up:** a new OPT-IN `qlty-setup` module (language linters only) + a slimmed
retained commit-msg/file-hygiene layer; every plugin + the qlty CLI version pinned;
single owner for the ruff pin (keep 003's frozen pin authoritative). **Hard gate before
building:** a network-free reproduce A/B test (qlty offline-mode is the key unverified
unknown) + a BSL-1.1 sign-off. See the research doc §5–§6 for the concrete module changes
and the to-verify checklist.

**Process note:** the research workflow's investigate layer failed (2 agents returned
schema-stub placeholders, 1 hard-errored); the verdict was reconstructed by the
challenge/synthesis agents and the 3 load-bearing facts were re-verified by hand. The
conclusion is sound; if revisited, re-run a clean investigate pass.
