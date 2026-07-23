# Fixture Case Schema — `fixtures/<agent>/case-<slug>.yaml`

Authoritative field reference in [data-model.md](../data-model.md)
(ConformanceCase). This contract adds the worked example and authoring rules.

## Example — clean regime, reviewer-low

```yaml
agent: reviewer-low
regime: clean
prompt: |
  Review this diff against the acceptance criteria.

  Acceptance criteria:
  - rename `get_user` to `fetch_user` everywhere; no behavior change.

  Diff:
  --- a/svc/users.py
  +++ b/svc/users.py
  @@ -10,7 +10,7 @@
  -def get_user(uid):
  +def fetch_user(uid):
       return _db.lookup(uid)
sandbox:
  files:
    svc/users.py: |
      def fetch_user(uid):
          return _db.lookup(uid)
assert:
  first_line: '^VERDICT: (APPROVE|CHANGES|ESCALATE)\b'
  max_words: 100          # reviewer-low CAP 100w clean
  no_reprint: true
  forbidden_patterns:
    - '^Findings'          # clean regime: findings section must be absent
timeout_s: 120
budget_usd: 0.50
```

## Example — findings regime with artifact assertion, lint-guard

```yaml
agent: lint-guard
regime: findings
prompt: |
  LINT-GUARD node=n42 scope=svc/
  lint_report:
    svc/app.py:12:F401:warning:'os' imported but unused
    svc/app.py:99:E501:warning:line too long
sandbox:
  files:
    svc/app.py: |
      import os
      # ... 12-line file; line 99 does not exist -> stale finding
assert:
  first_line: '^LINT-GUARD \S+ verdict=(PASS|WARN|BLOCK) items=\d+'
  max_words: 180          # lint-guard: 180 with findings
  no_reprint: true
  required_patterns:
    - 'svc/app\.py:12'
timeout_s: 120
```

## Authoring rules

- One case file per regime you exercise; name `case-clean.yaml`,
  `case-findings.yaml`, or `case-<scenario>.yaml`.
- `assert.first_line` and `assert.max_words` MUST match the agent's declared
  contract — `check` cross-validates against the derived contract and fails
  on drift (FR-011). When the contract is underivable (prose caps), the case
  is the encoding of record; keep it faithful.
- Fixture content must be self-contained and small: a fixture is a *probe*,
  not a realistic workload. Smallest input that forces the regime.
- Never stage real credentials, real user data, or network-dependent content
  (FR-013).
- `sandbox.git: true` only when the agent's task semantics require a repo
  (e.g. workers that inspect `git status`); it costs run time.

## skips.yaml

```yaml
skips:
  - agent: workflow-coder
    reason: >-
      Requires live orchestrate run state (claimed bead, assigned node,
      pushable remote); faithful stub deferred — tracked for v2.
```

Rules: reason ≥ 10 words, must say *what* environment is infeasible and the
follow-up intent. An agent may not appear in both `skips.yaml` and a case dir.
