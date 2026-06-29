# 017 Brownfield Probe — memory

## Provenance

Carved out of spec 008 on 2026-06-28 at the user's direction (two decisions): drop the
`brownfield_skip` per-module input (redundant — `idempotent_write` already gives
no-clobber), and standardize the "does my artifact exist?" check across ALL modules
into one SDK primitive. See `[[project-setup-008-brownfield-redesign]]` for the full
decision record and `[[project-setup-tier2-resolver]]` for runner-core facts.

## Key facts (so future work doesn't re-derive)

- The no-clobber guarantee already exists deterministically via `sdk.idempotent_write`
  (`sdk.py:241-252`): `reconcile=False` ⇒ write-if-absent (preserve existing).
  `git-init` (`module.py:135`) and `license-write` (`module.py:207`) already comply;
  `gitignore-generate` is the ONLY clobberer (`reconcile=True`, `module.py:217`).
- `looks_like_secret` (`sdk.py:558`) = 6 curated ANCHORED regexes (`_SECRET_PATTERNS`
  at `sdk.py:548`), deliberately NOT entropy-based. Scanner research (adversarially
  verified 2026-06-28): gitleaks ruleset is MIT, ~179 rules, RE2-pure (Python-`re`
  safe) and VENDORABLE — but its generic/high-entropy rules depend on keyword+entropy+
  allowlist prefilters that are NOT plain regex, so vendor ONLY anchored provider rules.
  detect-secrets is importable inline (`scan_line`) but pulls mandatory requests+pyyaml
  (breaks hermetic). trufflehog = Go binary, AGPL, not in-process. ⇒ keep curated +
  cherry-pick anchored gitleaks shapes; no dep.
- Every module hand-rolls existence checks today (survey 2026-06-28): lang-python
  `pyproject.exists()` ×4; lang-ts `package.json` ×3 + nuxt/vite; lang-go/rust
  go_mod/cargo_toml; package-add `target.exists()`; precommit-setup `abs_dest.exists()`.
  The `sdk_path.is_file()` hits are the SDK-bootstrap shim — NOT artifact checks, leave them.

## AS-BUILT

(to be filled at implementation — record the probe API actually shipped, the merge
helper location, the final widened `_SECRET_PATTERNS` set + MIT attribution, the
greenfield byte-identity proof, and any deferred migration.)
