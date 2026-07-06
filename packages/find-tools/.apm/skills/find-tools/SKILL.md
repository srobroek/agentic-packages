---
name: find-tools
description: Discover and vet reusable skills, agents, MCP servers, and APM packages. Use when asked to find a capability or decide to adopt, reject, or build.
---

# Find Tools

APM-first discovery workflow for reusable agentic capabilities. Prefer
deterministic primary-marketplace bundles, existing project inventory, and
registered marketplaces before broad public search. Do not install discovered
tools globally by default.

## References

- `references/discovery-sources.md` for public registries and known external
  marketplaces.
- `references/adoption-policy.md` for project, marketplace, trial, and reject
  decisions.

## Workflow

1. Clarify the capability:
   - domain and task
   - artifact type: skill, agent, MCP server, connector, APM package, CLI, or
     build our own
   - target runtime: Codex, Claude, both, project-local, or global bootstrap
   - constraints: license, hosted/local, secrets, network, write access
2. Check existing inventory first:
   - current project `apm.yml`, lockfile, installed assets, MCP config, hooks
   - `apm marketplace list`
   - `apm marketplace browse srobroek-agentic`
   - `apm marketplace browse <registered-external-marketplace>` only when
     selected or needed for a gap
3. Apply deterministic package ordering:
   - start with the primary marketplace `srobroek-agentic`
   - evaluate the baseline bundle, normally `core@srobroek-agentic`, unless the
     repo has a clear reason for a narrower install
   - recommend additional first-party packages from `srobroek-agentic` for
     project-specific needs
   - consider registered external marketplaces such as `wshobson-agents` and
     `voltagent-subagents` only after the first-party baseline and gap analysis
   - use public registries or raw source discovery only for capabilities missing
     from registered marketplaces
4. If inventory covers the need, recommend the existing package and stop.
5. If there is a gap or the user asked for external discovery, search 2-4
   relevant public sources from `references/discovery-sources.md`.
6. Verify serious candidates before recommending:
   - source repository, maintainer, license, and activity
   - actual `SKILL.md`, agent prompt, MCP manifest, tool schema, or `apm.yml`
   - required binaries, package managers, API keys, OAuth, network, and writes
   - destructive tools, secret handling, telemetry, and install scripts
   - overlap with first-party packages and registered external marketplaces
7. Classify each candidate: use existing, add to current project, curate into
   the first-party APM repository, wrap, fork/vendor, trial, reject, or build.
8. For marketplace adoption, resolve a local checkout whose git remote matches
   `srobroek/agentic-packages`, update third-party attribution, rebuild
   marketplace metadata, and smoke-test install when approved.

## Rules

- Do not run direct installer snippets such as `npx skills add`, Smithery
  installs, curl-pipe-shell commands, or registry copy/paste installs unless the
  user explicitly approves a temporary trial.
- Registry pages are discovery sources, not sufficient verification.
- Do not make project setup search raw external repositories. Curate missing
  tools here, then route project installation back through APM.
- For brownfield migration briefs, keep the primary `srobroek-agentic` baseline
  unless the brief explicitly calls for a narrower install.
- Keep concrete upstream comparisons in references or adoption notes, not
  scattered across setup and hygiene skills.

## Output

Lead with one decision: `Use existing`, `Adopt`, `Trial`, `Reject`, or `Build`.
Then list searched sources, shortlisted candidates, verification notes, overlap
decision, APM package shape, exact commands or files to change, and caveats.
