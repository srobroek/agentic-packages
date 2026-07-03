---
description: >-
  Reference: the Codex CLI hook contract (event names, stdin payload shape,
  decision mechanism) as used by this monorepo's guard hooks. Each claim is
  labeled VERIFIED / ASSUMED / UNKNOWN with a test to confirm the open ones.
applyTo: "{**/*-codex-hooks.json,**/hooks/*.sh,**/scripts/*-guard.sh,**/scripts/*guard*.sh}"
---

# Codex CLI hook contract (reference)

Every guard hook in this repo is marketed cross-tool (Claude + Codex) but was
authored against Claude Code's documented `hookSpecificOutput` contract. This
doc records what is actually KNOWN about the Codex side, drawn from the Codex
hook configs and scripts in this repo plus the chezmoi Codex config. It exists
to be precise about the uncertainty, not to assert a clean spec.

Read this before changing any `*-codex-hooks.json` or any guard script that
parses the hook stdin payload or emits a decision.

Confidence labels:

- **[VERIFIED]** — directly observable in committed config/scripts in this repo
  or the chezmoi Codex config, OR a structural fact those files depend on to
  work at all.
- **[ASSUMED]** — the scripts behave as if this is true and it is the most
  probable reading, but it is not independently confirmed against a live Codex
  run captured here.
- **[UNKNOWN]** — not determinable from the artifacts in this repo; the scripts
  hedge against more than one possibility.

## Evidence base

All claims below are inferred from these files (no live Codex run was captured):

- Package Codex hook configs: `packages/*/.apm/hooks/*-codex-hooks.json`
  (e.g. `hooks-bash-safety`, `hooks-git-safety`, `hooks-attribution-guard`).
- Installed/canonical Codex hook wiring in chezmoi:
  `~/.local/share/chezmoi/dotfiles/dot_codex/hooks.json` and its rendered form
  `~/.codex/hooks.json`.
- Codex-native hook scripts in chezmoi:
  `dot_codex/hooks/executable_allow-chezmoi-apply.sh` (a `PermissionRequest`
  hook) and `dot_codex/hooks/executable_reindex-after-commit.sh` (a
  `PostToolUse` hook).
- Guard scripts: `packages/hooks-git-safety/scripts/git-guard.sh` and the
  canonical `~/.local/share/chezmoi/.../agentic-tools/hooks/bash-guard.sh`.
- Codex config: `~/.local/share/chezmoi/.../codex/config.toml` (the
  `[hooks.state]` table and `[features] hooks = true`).

When this doc says "the scripts," it means the files above.

## 1. Hook event names

**[VERIFIED] Codex accepts Claude-style PascalCase event names in
`hooks.json`.** `~/.codex/hooks.json` is keyed by `UserPromptSubmit`,
`SessionStart`, `PreToolUse`, `PermissionRequest`, `PostToolUse`, and `Stop`,
under a top-level `"hooks"` object. The same PascalCase keys appear in every
`packages/*/.apm/hooks/*-codex-hooks.json`. With `[features] hooks = true` set
in `config.toml`, these are the names the configs are written against.

**[VERIFIED] Codex normalizes those event names to snake_case internally.**
`config.toml` carries a `[hooks.state]` table whose keys are
`pre_tool_use`, `post_tool_use`, `permission_request`, `user_prompt_submit`,
and `stop` (e.g. `hooks.state."$HOME/.codex/hooks.json:pre_tool_use:0:0"`).
The same `hooks.json` is configured in PascalCase but tracked in snake_case, so
Codex maps `PreToolUse` -> `pre_tool_use` etc. for its trust/state bookkeeping.

**[VERIFIED] Event set used in practice:** `UserPromptSubmit`, `SessionStart`,
`PreToolUse`, `PermissionRequest`, `PostToolUse`, `Stop`. `PermissionRequest`
has no Claude Code equivalent and is Codex-specific.

**[ASSUMED] The matcher semantics mirror Claude's** — `matcher: "Bash"` selects
the Bash tool; `matcher: "Edit|Write|MultiEdit"` and `matcher: "apply_patch"`
are regex-ish alternations; an absent `matcher` (as on `UserPromptSubmit` /
`Stop`) means "always." This is how the configs are written, but Codex's exact
matcher matching rules (anchoring, case, whether `apply_patch` is the canonical
Codex edit-tool name) are not confirmed here.

**[VERIFIED] Hook `if` filters are NOT honored reliably.** The comment block at
the top of `reindex-after-commit.sh` states plainly: "Codex currently does not
honor hook-level 'if' filters reliably. Keep this hook wired broadly to
PostToolUse/Bash and make the script itself cheap, silent, and defensive." This
matches the repo-wide rule that self-gating hooks ship no `if`.

**Test to confirm matcher/`if` behavior:** wire a one-line hook that appends
`$(date) $CODEX_*` to a temp file under several `matcher` values and an `if`
filter, run a matching and a non-matching tool call, and diff which fired.

## 2. Trust / hashing of hook scripts

**[VERIFIED] Codex pins each hook entry by content hash before running it.**
`[hooks.state]` records a `trusted_hash = "sha256:..."` per hook slot, keyed by
`"<hooks.json path>:<event_snake_case>:<group_index>:<hook_index>"`, e.g.
`pre_tool_use:0:5`. One entry also carries `enabled = true`.

**[ASSUMED] Editing a hook script invalidates its trusted hash and forces
re-approval.** The `trusted_hash` only makes sense as an anti-tamper gate, so
changing a guard script likely requires re-trusting it in Codex before it runs
again. Not confirmed against a live edit here.

**Implication for this repo:** when a guard script is edited, a Codex user may
need to re-approve it. Document any such churn near the script, not here.

## 3. stdin payload shape

The hook receives its payload as JSON on **stdin** (every script does
`payload="$(cat)"`). **[VERIFIED]** by uniform use across all guard scripts.

### 3.1 `.tool_input` is object OR bare string — the bypass that bit us

**[VERIFIED] `.tool_input` is not reliably an object.** `git-guard.sh` carries a
comment documenting a real, fixed bug:

> `tool_input` can be an object (`{command:"..."}`) OR a bare string. The naive
> `.tool_input.command // .tool_input` form THROWS on a string ("Cannot index
> string with command") and, with stderr swallowed, leaves `$command` empty —
> silently bypassing every guard.

`git-guard.sh` therefore type-checks before indexing:

```sh
command="$(printf '%s' "$payload" | jq -r '
  if (.tool_input | type) == "string" then .tool_input
  else (.tool_input.command // empty)
  end' 2>/dev/null || true)"
```

This is the load-bearing fact of the whole doc: **a Codex hook MUST handle
`.tool_input` being a string.** The older, still-shipping form in
`bash-guard.sh` and `allow-chezmoi-apply.sh` —
`jq -r '.tool_input.command // .tool_input // empty'` — does NOT type-check and
relies on `// .tool_input` to recover the string case. That recovery only works
because `jq`'s `//` catches the empty result; the throwing path in `git-guard`
was the variant that broke. Treat the type-checking form as the correct pattern.

**[UNKNOWN] WHICH tool / WHEN `.tool_input` is a string vs object.** The
artifacts prove both shapes occur but do not pin the trigger. Plausible
readings (not separated by evidence here): (a) Bash/shell tool calls deliver the
command as a bare string while structured tools deliver an object; (b) it varies
by Codex version; (c) it varies by whether the call came through the
`PreToolUse` vs `PermissionRequest` path. Do not assume; always handle both.

**Test to separate the cases:** install a `PreToolUse` hook that does
`jq -r '.tool_input | type' >> /tmp/codex-shape.log` and exercise a Bash call,
an Edit/Write call, and `apply_patch`. The logged `string`/`object` per tool
resolves [UNKNOWN] (a).

### 3.2 Other payload fields are NOT confirmed and are hedged in scripts

**[UNKNOWN] PostToolUse result field name.** `reindex-after-commit.sh` reads the
exit status defensively across four spellings:

```sh
jq -r '.tool_output.exit_code // .tool_output.exitCode //
       .tool_response.exit_code // .tool_response.exitCode // empty'
```

The author did not know whether Codex emits `tool_output` or `tool_response`,
nor snake_case vs camelCase. **This is direct evidence the PostToolUse payload
shape is unverified.**

**Test:** in a `PostToolUse:Bash` hook, `jq -c '.' >> /tmp/codex-post.log` after
a `git commit`, then inspect which of the four keys is populated.

**[ASSUMED] `matcher`-relevant tool identity lives in the payload** (some
`tool_name`-like field) so Codex can route by matcher. Field name UNKNOWN here.

**[UNKNOWN] UserPromptSubmit / SessionStart / Stop payload shapes.** No script
in this repo reads fields from those events (they only run side-effecting
commands), so their stdin shape is undocumented here.

## 4. How Codex honors a hook decision

This is where the cross-tool marketing is riskiest: the guards emit Claude
Code's `hookSpecificOutput` JSON, and it is NOT confirmed that Codex interprets
it the same way — or at all.

### 4.1 PreToolUse guards emit `permissionDecision` (Claude contract)

**[VERIFIED what is emitted]** `bash-guard.sh` and `git-guard.sh` print, on
stdout, then `exit 0`:

```json
{"hookSpecificOutput":{"hookEventName":"PreToolUse",
  "permissionDecision":"deny|ask|allow",
  "permissionDecisionReason":"..."}}
```

**[ASSUMED Codex honors it]** This is Claude Code's PreToolUse contract verbatim
(`deny` blocks, `ask` prompts the user, `allow` short-circuits approval). The
guards assume Codex reads the same fields. Whether Codex actually parses
`permissionDecision` from a `PreToolUse` hook, or ignores unknown JSON and falls
back to exit-code semantics, is **NOT confirmed by any artifact here.** Note the
guards `exit 0` even when denying, so if Codex used exit codes alone, a deny
would not block — meaning correctness depends entirely on Codex honoring the
JSON.

### 4.2 PermissionRequest uses a DIFFERENT shape: `decision.behavior`

**[VERIFIED a second, distinct shape exists for a different event.**]
`allow-chezmoi-apply.sh` (wired to `PermissionRequest`) emits:

```json
{"hookSpecificOutput":{"hookEventName":"PermissionRequest",
  "decision":{"behavior":"allow"}}}
```

This is NOT the `permissionDecision` string form; it nests
`decision.behavior`. So the decision schema is **event-dependent**:
`PreToolUse` -> `permissionDecision` (string), `PermissionRequest` ->
`decision.behavior` (object). Do not copy one event's output shape onto the
other. (The `PermissionRequest` shape here only ever emits `allow`; whether
`decision.behavior` accepts `deny`/`ask`-equivalents is UNKNOWN.)

### 4.3 Exit codes

**[ASSUMED] Exit code 0 = "no opinion, proceed."** Every script `exit 0`s on the
no-match path and even after printing a `deny`. The decision is carried by JSON,
not the exit code. Whether a nonzero exit (or exit 2, as in some hook systems)
has independent blocking meaning in Codex is **UNKNOWN** — nothing in this repo
relies on it, so it cannot be inferred.

**Test for 4.1 / 4.3 (highest-value verification):** install a `PreToolUse:Bash`
hook that emits `permissionDecision:"deny"` for a sentinel command (e.g. a
harmless `echo CODEX_DENY_PROBE`) and `exit 0`. Run that command in Codex. If it
is blocked, Codex honors `permissionDecision` over the JSON path [resolves 4.1].
Then make a second variant that emits NO JSON and `exit 1` (or `exit 2`) for the
sentinel; if THAT blocks, Codex also/instead honors exit codes [resolves 4.3].
The two probes together pin the real decision mechanism.

**Test for 4.2:** trigger a `PermissionRequest` for a `chezmoi` command with
`allow-chezmoi-apply.sh` active; if approval is auto-granted, `decision.behavior`
is honored. Then try `decision:{behavior:"deny"}` on a sentinel to see whether
the object form supports denial.

## 5. Summary table

| Claim | Status |
| --- | --- |
| `hooks.json` uses PascalCase event names | VERIFIED |
| Codex maps events to snake_case (`[hooks.state]`) | VERIFIED |
| Event set: UserPromptSubmit/SessionStart/PreToolUse/PermissionRequest/PostToolUse/Stop | VERIFIED |
| `PermissionRequest` is Codex-specific (no Claude equiv) | VERIFIED |
| Hook-level `if` filters unreliable | VERIFIED |
| Hook scripts pinned by `trusted_hash` | VERIFIED |
| Editing a script forces re-trust | ASSUMED |
| Payload arrives as JSON on stdin | VERIFIED |
| `.tool_input` may be string OR object | VERIFIED |
| Which tool/when yields string vs object | UNKNOWN |
| PostToolUse result field (`tool_output`/`tool_response`, snake/camel) | UNKNOWN |
| Tool-identity field name in payload | UNKNOWN |
| UserPromptSubmit/SessionStart/Stop payload shape | UNKNOWN |
| PreToolUse emits `hookSpecificOutput.permissionDecision` | VERIFIED (emitted) |
| Codex honors `permissionDecision` deny/ask/allow | ASSUMED |
| PermissionRequest uses `hookSpecificOutput.decision.behavior` | VERIFIED (emitted) |
| `decision.behavior` supports deny/ask | UNKNOWN |
| Exit 0 = proceed; JSON carries the decision | ASSUMED |
| Nonzero exit code has independent blocking meaning | UNKNOWN |

## 6. Rules for authoring Codex hooks in this repo

1. **Always handle `.tool_input` as string OR object** (section 3.1). Type-check
   with `jq` `if (.tool_input | type) == "string"`; do not rely on `//` recovery.
2. **Swallow `jq` errors** (`2>/dev/null || true`) but never let a swallowed
   error leave a guard variable empty in a way that silently allows the action —
   the original bypass. Fail safe, not open.
3. **Match the emitted decision shape to the event:** `permissionDecision`
   string for `PreToolUse`; `decision.behavior` object for `PermissionRequest`.
4. **Do not depend on `if` filters or exit codes for blocking.** Self-gate inside
   the script and carry the decision in the JSON.
5. **When you rely on any UNKNOWN above, run the matching test first** and update
   this doc's table with the result and the date.
