# Surface Index

Route the detected target onto surface docs. A "surface" is a class of attack,
not a language: the same Python file belongs to `code.md` for its taint paths and
to `robustness.md` for its input handling. Load only the docs a target actually
touches, and hand each to one `gremlin`.

Each surface doc below is self-contained.

| Surface | Doc | Detect by | Owns |
|---------|-----|-----------|------|
| Code memory and logic | `code.md` | any `*.rs` `*.go` `*.py` `*.ts` `*.js` `*.c` `*.cpp` `*.java` | injection, taint to sink, unsafe blocks, integer overflow, path traversal, deserialization, TOCTOU, authz logic, ReDoS, unbounded allocation |
| Shell and hooks | `shell.md` | `*.sh` `*.bash`, shebang, `.claude/hooks/**`, `.git/hooks/**`, PreToolUse guards | command-position bypass, quoting and word splitting, `$VAR` injection, fail-open inversion, guard evasion, TOCTOU on lock files |
| Agents and prompts | `agents.md` | `SKILL.md`, `*.agent.md`, `.mcp.json`, `settings.json` with hooks or permissions | prompt injection, tool over-grant, exfil paths, instruction override, untrusted content reaching context |
| Infra, config, supply chain | `infra.md` | `*.tf` `Dockerfile` `*.yaml` with `kind:`, `.github/workflows/**`, lockfiles | IaC misconfig, container and k8s hardening, CI workflow injection, secrets, dependency CVEs, typosquats, unpinned actions |
| Robustness | `robustness.md` | every target, always | malformed input crashes, boundary values, encoding, resource limits, concurrency, state-machine edges, error-path correctness |

Each doc's attack checklist is a floor for a repo just met, and recon's trust map
and idiom census aim the pass. A checklist worked start to finish without recon
finds the generic bugs and misses this repo's own.

## Routing rules

MUST Include `robustness.md` in every run. It applies to all five target kinds and covers the stability findings the security surfaces skip.
MUST Route a hook or guard script to both `shell.md` and `robustness.md`. A guard that crashes on malformed stdin is a bypass, so the two surfaces overlap here by design.
MUST Route an agent, skill, or MCP config to `agents.md` even when it contains no code. The absence of a deterministic scanner makes reading the only detection available.
DEFAULT Split a surface across several `gremlin` agents when its file list exceeds roughly 5k LOC, dividing by subtree, crate, or package.
NOT Assigning one language to one surface is wrong: surfaces cross-cut languages, and a language may map to three of them at once.

## Overlap map

Where two surfaces could both claim a finding, the owner is:

| Finding | Owner | Why |
|---------|-------|-----|
| Unquoted `$VAR` in a shell hook | `shell.md` | command-position semantics decide exploitability |
| Unquoted variable in a Dockerfile `RUN` | `infra.md` | hadolint embeds shellcheck, so the infra scanner already covers it |
| A CLI that panics on 4 GB of stdin | `robustness.md` | no attacker path in a local dev tool, though the crash is still real |
| A server that panics on 4 GB of a request body | `code.md` | remote input reaches the allocation, making it a DoS path |
| `WebFetch` output flowing into a tool call | `agents.md` | untrusted content reaching context is the agent-surface core |
| An unpinned GitHub Action | `infra.md` | supply chain, caught by pinact and zizmor |

## Authoring

`_template.md` is the authoring template. Every doc carries the same sections:
Detect · Tools · Attack checklist · Harness patterns · Impact calibration ·
False-positive traps.
