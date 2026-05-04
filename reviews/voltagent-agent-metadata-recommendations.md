# Agent Metadata Recommendations

Review artifact for moving current Claude/Codex agents plus `VoltAgent/awesome-codex-subagents` into `srobroek/agentic-packages`.

This is a recommendation file, not final approved runtime configuration.

## Policy Baseline

- `gpt-5.5`: use for reasoning-heavy planning, orchestration, adversarial review, architecture review, security/compliance/legal analysis, data/statistical interpretation, spec verification, and other high-risk judgment work.
- `gpt-5.4`: use for capable lower-cost reasoning and frontend/design work where OpenAI guidance calls out improved UI, image, computer-use, and Playwright-style verification behavior.
- `gpt-5.4-mini`: use for cheap bounded non-code work: simple extraction, synthesis, routing, lightweight documentation, and narrow operational agents.
- `gpt-5.3-codex`: use for complex or specialized coding agents that will edit files, run tests, refactor, migrate, or implement bounded tasks.
- `gpt-5.3-codex-spark`: use for fast bounded code loops, mechanical fixes, small tests, dependency/build edits, and other simple implementation tasks where the research-preview cost/latency tradeoff is acceptable.
- Reasoning effort may be `low`, `medium`, `high`, or `xhigh`. Use `low` only for narrow extraction/status tasks; use `xhigh` only when risk, ambiguity, or orchestration complexity justifies the cost.
- Prefer `read-only` for planning, research, review, verification, legal/security/compliance, and orchestration agents. Use `workspace-write` only for agents expected to edit files or run implementation workflows.
- Main session remains responsible for orchestration, final synthesis, and verification of subagent outputs even when a subagent uses `gpt-5.5`.
- `impeccable` is only recommended for frontend, UI, UX, visual design, or product-interface agents.

## Active MCP And Tool Surface

Treat these MCP servers as available for recommendation purposes in the current Codex setup:

- `context7`
- `openaiDeveloperDocs`
- `codebase-memory-mcp`
- `github`
- `fetcher`
- `stitch`
- `playwright`
- `repomix`
- `terraform`

Treat these MCP servers as available in Claude's global configuration:

- `context7`
- `codebase-memory-mcp`
- `github`
- `fetcher`
- `stitch`
- `playwright`
- `repomix`
- `terraform`

Claude project-local `.mcp.json` currently includes: `codebase-memory-mcp`.

Session app connectors also available when explicitly relevant: `Google Drive`, `Outlook Calendar`, `Outlook Email`.

Claude-only configured agent MCPs found in existing agents: `excel-mcp`, `aws-central-mcp`, `aws-outlook-mcp`.

The retired memory MCP from the old Claude setup is intentionally omitted from recommendations.

Columns: `Current` shows the existing runtime configuration or VoltAgent upstream metadata. `Access` is recommended sandbox/workspace access. `Approval` is recommended escalation posture. `Claude perms` is the intended permissions mode to patch after APM install. `MCP/tools` lists tool surfaces to explicitly reference in the agent definition.

## Agent Name Overlap

- VoltAgent source agents: `136`.
- Live Claude Code agents: `13`.
- Live Codex agents: `1`.
- Current APM package agents: `149`.
- VoltAgent ∩ Claude Code: `0`.
- VoltAgent ∩ Codex: `0`.
- Claude Code ∩ Codex: `1`: `coder`
- APM package includes all VoltAgent agents: `yes`.
- APM package includes all live Claude Code agents: `yes`.
- APM package includes all live Codex agents: `yes`.

## Routing Notes

- `speckit-implement-task` owns SpecKit task boundaries, task interpretation, and non-code edits. For substantial coding work, the parent/main session should dispatch `coder` or a language specialist; `speckit-implement-task` returns the delegation brief when it cannot directly spawn a worker.
- `coder` is the default implementation worker for mixed-language or ordinary code changes. Language specialists replace `coder` for tasks where the requested language/framework is central to correctness; they should not normally bounce work back to `coder` unless the main session explicitly asks for a two-agent consult.
- Review agents should stay read-only and report findings. The main session decides whether to dispatch `coder`/specialists for fixes.
- Non-coding operational agents such as database administration, deployment review, analytics, data science, and incident analysis are assigned by prompt complexity and judgment risk, not by whether their name contains `engineer`.
- `challenge`/`adversarial-challenger` gets the full active tool/MCP surface for critique, but remains read-only unless a parent task explicitly turns a critique into implementation.

## Currently Configured Agents

| Agent | Current | Recommended Codex | Access | Approval | Recommended Claude | Claude perms | MCP/tools | Skills/steering | Rationale |
|---|---|---|---|---|---|---|---|---|---|
| `activity-tracker` | Claude `sonnet default`<br>Claude MCP `excel-mcp, aws-central-mcp` | `gpt-5.4-mini` `low` | `workspace-write` | `on-request` | `sonnet` `low` | `workspace-write` | filesystem, excel-mcp, aws-central-mcp, aws-outlook-mcp | - | simple, bounded, lookup, synthesis, or operational work; low effort is intentional |
| `adversarial-challenger` | Claude `opus default` | `gpt-5.5` `xhigh` | `read-only` | `none` | `opus` `xhigh` | `read-only` | filesystem, context7, openaiDeveloperDocs, codebase-memory-mcp, github, fetcher, stitch, playwright, repomix, terraform, apply_patch, shell, tool_search | - | reasoning/planning/orchestration or high-risk review; xhigh effort is intentional |
| `chezmoi-editor` | Claude `sonnet default` | `gpt-5.4-mini` `medium` | `workspace-write` | `on-request` | `sonnet` `medium` | `workspace-write` | filesystem, chezmoi | - | edits chezmoi-managed source files, not rendered live targets |
| `coder` | Codex `gpt-5.3-codex high workspace-write`<br>Claude `opus default` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, playwright, stitch | - | complex/specialized implementation |
| `dep-repo-worker` | Claude `sonnet default` | `gpt-5.4-mini` `medium` | `workspace-write` | `on-request` | `sonnet` `medium` | `workspace-write` | filesystem, github, fetcher | - | simple, bounded, lookup, synthesis, or operational work |
| `pr-reviewer` | Claude `opus default` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, github | - | reasoning/planning/orchestration or high-risk review |
| `sfdc-activity` | Claude `sonnet default`<br>Claude MCP `aws-central-mcp, aws-outlook-mcp` | `gpt-5.4-mini` `low` | `workspace-write` | `on-request` | `sonnet` `low` | `workspace-write` | filesystem, excel-mcp, aws-central-mcp, aws-outlook-mcp | - | simple, bounded, lookup, synthesis, or operational work; low effort is intentional |
| `speckit-implement-task` | Claude `opus default` | `gpt-5.5` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | speckit | SpecKit task owner for boundaries and non-code edits; route substantial coding slices to coder or language specialists |
| `speckit-research` | Claude `sonnet default` | `gpt-5.4-mini` `medium` | `read-only` | `none` | `sonnet` `medium` | `read-only` | filesystem, fetcher, github | speckit | simple, bounded, lookup, synthesis, or operational work |
| `speckit-sync` | Claude `sonnet default` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, github | speckit | reasoning/planning/orchestration or high-risk review |
| `speckit-sync-conflicts` | Claude `sonnet default` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, github | speckit | reasoning/planning/orchestration or high-risk review |
| `speckit-verify` | Claude `opus high` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, github | speckit | reasoning/planning/orchestration or high-risk review |
| `speckit-verify-tasks` | Claude `opus high` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, github | speckit | reasoning/planning/orchestration or high-risk review |

## VoltAgent Import Recommendations

### 01 Core Development

| Agent | Current | Recommended Codex | Access | Approval | Recommended Claude | Claude perms | MCP/tools | Skills/steering | Rationale |
|---|---|---|---|---|---|---|---|---|---|
| `api-designer` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix | - | reasoning/planning/orchestration or high-risk review |
| `backend-developer` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `code-mapper` | VoltAgent `gpt-5.3-codex-spark medium read-only` | `gpt-5.3-codex-spark` `medium` | `read-only` | `none` | `sonnet` `medium` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix | - | fast bounded code loop or mechanical implementation |
| `electron-pro` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, github | - | complex/specialized implementation |
| `frontend-developer` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.4` `high` | `workspace-write` | `on-request` | `sonnet` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, playwright, stitch | interface-design, impeccable | frontend/design/product UI work with visual and browser verification |
| `fullstack-developer` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `graphql-architect` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix | - | reasoning/planning/orchestration or high-risk review |
| `microservices-architect` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix | - | reasoning/planning/orchestration or high-risk review |
| `mobile-developer` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.4` `high` | `workspace-write` | `on-request` | `sonnet` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, playwright, stitch | interface-design, impeccable | frontend/design/product UI work with visual and browser verification |
| `ui-designer` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.4` `high` | `read-only` | `none` | `sonnet` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix, playwright, stitch | interface-design, impeccable | frontend/design/product UI work with visual and browser verification |
| `ui-fixer` | VoltAgent `gpt-5.3-codex-spark medium workspace-write` | `gpt-5.4` `medium` | `workspace-write` | `on-request` | `sonnet` `medium` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, playwright, stitch | interface-design, impeccable | frontend/design/product UI work with visual and browser verification |
| `websocket-engineer` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |

### 02 Language Specialists

| Agent | Current | Recommended Codex | Access | Approval | Recommended Claude | Claude perms | MCP/tools | Skills/steering | Rationale |
|---|---|---|---|---|---|---|---|---|---|
| `angular-architect` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.4` `high` | `workspace-write` | `on-request` | `sonnet` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, playwright, stitch | interface-design, impeccable | frontend/design/product UI work with visual and browser verification |
| `cpp-pro` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, github | - | complex/specialized implementation |
| `csharp-developer` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `django-developer` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `dotnet-core-expert` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `dotnet-framework-4.8-expert` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `elixir-expert` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `erlang-expert` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `flutter-expert` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `golang-pro` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, github | - | complex/specialized implementation |
| `java-architect` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `javascript-pro` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, github | - | complex/specialized implementation |
| `kotlin-specialist` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `laravel-specialist` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `nextjs-developer` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.4` `high` | `workspace-write` | `on-request` | `sonnet` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, playwright, stitch | interface-design, impeccable | frontend/design/product UI work with visual and browser verification |
| `php-pro` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, github | - | complex/specialized implementation |
| `powershell-5.1-expert` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `powershell-7-expert` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `python-pro` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, github | - | complex/specialized implementation |
| `rails-expert` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `react-specialist` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.4` `high` | `workspace-write` | `on-request` | `sonnet` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, playwright, stitch | interface-design, impeccable | frontend/design/product UI work with visual and browser verification |
| `rust-engineer` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `spring-boot-engineer` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, github | - | complex/specialized implementation |
| `sql-pro` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, github | - | complex/specialized implementation; access differs from upstream read-only |
| `swift-expert` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `typescript-pro` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, github | - | complex/specialized implementation |
| `vue-expert` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.4` `high` | `workspace-write` | `on-request` | `sonnet` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, playwright, stitch | interface-design, impeccable | frontend/design/product UI work with visual and browser verification |

### 03 Infrastructure

| Agent | Current | Recommended Codex | Access | Approval | Recommended Claude | Claude perms | MCP/tools | Skills/steering | Rationale |
|---|---|---|---|---|---|---|---|---|---|
| `azure-infra-engineer` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, terraform | - | complex/specialized implementation; access differs from upstream read-only |
| `cloud-architect` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix, terraform | - | reasoning/planning/orchestration or high-risk review |
| `database-administrator` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix | - | reasoning/planning/orchestration or high-risk review |
| `deployment-engineer` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.5` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, terraform | - | reasoning/planning/orchestration or high-risk review |
| `devops-engineer` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, terraform | - | complex/specialized implementation |
| `devops-incident-responder` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix, terraform | - | reasoning/planning/orchestration or high-risk review |
| `docker-expert` | VoltAgent `gpt-5.3-codex-spark medium workspace-write` | `gpt-5.3-codex-spark` `medium` | `workspace-write` | `on-request` | `sonnet` `medium` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, terraform | - | fast bounded code loop or mechanical implementation |
| `incident-responder` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix | - | reasoning/planning/orchestration or high-risk review |
| `kubernetes-specialist` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, terraform | - | complex/specialized implementation; access differs from upstream read-only |
| `network-engineer` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix | - | reasoning/planning/orchestration or high-risk review |
| `platform-engineer` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix | - | reasoning/planning/orchestration or high-risk review |
| `security-engineer` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix | - | reasoning/planning/orchestration or high-risk review |
| `sre-engineer` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix | - | reasoning/planning/orchestration or high-risk review |
| `terraform-engineer` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, terraform | - | complex/specialized implementation; access differs from upstream read-only |
| `terragrunt-expert` | VoltAgent `gpt-5.3-codex-spark medium read-only` | `gpt-5.3-codex-spark` `medium` | `workspace-write` | `on-request` | `sonnet` `medium` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, terraform | - | fast bounded code loop or mechanical implementation; access differs from upstream read-only |
| `windows-infra-admin` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, terraform | - | complex/specialized implementation; access differs from upstream read-only |

### 04 Quality & Security

| Agent | Current | Recommended Codex | Access | Approval | Recommended Claude | Claude perms | MCP/tools | Skills/steering | Rationale |
|---|---|---|---|---|---|---|---|---|---|
| `accessibility-tester` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix, github | - | reasoning/planning/orchestration or high-risk review |
| `ad-security-reviewer` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix, github | - | reasoning/planning/orchestration or high-risk review |
| `architect-reviewer` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix, github | - | reasoning/planning/orchestration or high-risk review |
| `browser-debugger` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, github | - | complex/specialized implementation |
| `chaos-engineer` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix | - | reasoning/planning/orchestration or high-risk review |
| `code-reviewer` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix, github | - | reasoning/planning/orchestration or high-risk review |
| `compliance-auditor` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix, github | - | reasoning/planning/orchestration or high-risk review |
| `debugger` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, github | - | complex/specialized implementation; access differs from upstream read-only |
| `error-detective` | VoltAgent `gpt-5.3-codex-spark medium read-only` | `gpt-5.3-codex-spark` `medium` | `workspace-write` | `on-request` | `sonnet` `medium` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | fast bounded code loop or mechanical implementation; access differs from upstream read-only |
| `penetration-tester` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix, github | - | reasoning/planning/orchestration or high-risk review |
| `performance-engineer` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix | - | reasoning/planning/orchestration or high-risk review |
| `powershell-security-hardening` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix | - | reasoning/planning/orchestration or high-risk review |
| `qa-expert` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix, github | - | reasoning/planning/orchestration or high-risk review |
| `reviewer` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix, github | - | reasoning/planning/orchestration or high-risk review |
| `security-auditor` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix, github | - | reasoning/planning/orchestration or high-risk review |
| `test-automator` | VoltAgent `gpt-5.3-codex-spark medium workspace-write` | `gpt-5.3-codex-spark` `medium` | `workspace-write` | `on-request` | `sonnet` `medium` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | fast bounded code loop or mechanical implementation |

### 05 Data & AI

| Agent | Current | Recommended Codex | Access | Approval | Recommended Claude | Claude perms | MCP/tools | Skills/steering | Rationale |
|---|---|---|---|---|---|---|---|---|---|
| `ai-engineer` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.5` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, openaiDeveloperDocs | - | reasoning/planning/orchestration or high-risk review |
| `data-analyst` | VoltAgent `gpt-5.3-codex-spark medium read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix, fetcher, github | - | reasoning/planning/orchestration or high-risk review |
| `data-engineer` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `data-scientist` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix | - | reasoning/planning/orchestration or high-risk review |
| `database-optimizer` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix | - | reasoning/planning/orchestration or high-risk review |
| `llm-architect` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix, openaiDeveloperDocs | - | reasoning/planning/orchestration or high-risk review |
| `machine-learning-engineer` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `ml-engineer` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `mlops-engineer` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `nlp-engineer` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `postgres-pro` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, github | - | complex/specialized implementation; access differs from upstream read-only |
| `prompt-engineer` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix, github, openaiDeveloperDocs | - | reasoning/planning/orchestration or high-risk review |

### 06 Developer Experience

| Agent | Current | Recommended Codex | Access | Approval | Recommended Claude | Claude perms | MCP/tools | Skills/steering | Rationale |
|---|---|---|---|---|---|---|---|---|---|
| `build-engineer` | VoltAgent `gpt-5.3-codex-spark medium workspace-write` | `gpt-5.3-codex-spark` `medium` | `workspace-write` | `on-request` | `sonnet` `medium` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | fast bounded code loop or mechanical implementation |
| `cli-developer` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `dependency-manager` | VoltAgent `gpt-5.3-codex-spark medium workspace-write` | `gpt-5.3-codex-spark` `medium` | `workspace-write` | `on-request` | `sonnet` `medium` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | fast bounded code loop or mechanical implementation |
| `documentation-engineer` | VoltAgent `gpt-5.3-codex-spark medium workspace-write` | `gpt-5.4-mini` `medium` | `workspace-write` | `on-request` | `sonnet` `medium` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | simple, bounded, lookup, synthesis, or operational work |
| `dx-optimizer` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix | - | reasoning/planning/orchestration or high-risk review |
| `git-workflow-manager` | VoltAgent `gpt-5.3-codex-spark medium read-only` | `gpt-5.4-mini` `medium` | `read-only` | `none` | `sonnet` `medium` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix | - | simple, bounded, lookup, synthesis, or operational work |
| `legacy-modernizer` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation; access differs from upstream read-only |
| `mcp-developer` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `powershell-module-architect` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `powershell-ui-architect` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.4` `high` | `workspace-write` | `on-request` | `sonnet` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, playwright, stitch | interface-design, impeccable | frontend/design/product UI work with visual and browser verification |
| `refactoring-specialist` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `slack-expert` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `tooling-engineer` | VoltAgent `gpt-5.3-codex-spark medium workspace-write` | `gpt-5.3-codex-spark` `medium` | `workspace-write` | `on-request` | `sonnet` `medium` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | fast bounded code loop or mechanical implementation |

### 07 Specialized Domains

| Agent | Current | Recommended Codex | Access | Approval | Recommended Claude | Claude perms | MCP/tools | Skills/steering | Rationale |
|---|---|---|---|---|---|---|---|---|---|
| `api-documenter` | VoltAgent `gpt-5.3-codex-spark medium workspace-write` | `gpt-5.4-mini` `medium` | `workspace-write` | `on-request` | `sonnet` `medium` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | simple, bounded, lookup, synthesis, or operational work |
| `blockchain-developer` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `embedded-systems` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `fintech-engineer` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.5` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | reasoning/planning/orchestration or high-risk review |
| `game-developer` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `iot-engineer` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `m365-admin` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix | - | reasoning/planning/orchestration or high-risk review |
| `mobile-app-developer` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.4` `high` | `workspace-write` | `on-request` | `sonnet` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix, playwright, stitch | interface-design, impeccable | frontend/design/product UI work with visual and browser verification |
| `payment-integration` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.3-codex` `high` | `workspace-write` | `on-request` | `opus` `high` | `workspace-write` | filesystem, context7, codebase-memory-mcp, repomix | - | complex/specialized implementation |
| `quant-analyst` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix, fetcher, github | - | reasoning/planning/orchestration or high-risk review |
| `risk-manager` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix | - | reasoning/planning/orchestration or high-risk review |
| `seo-specialist` | VoltAgent `gpt-5.3-codex-spark medium read-only` | `gpt-5.4-mini` `medium` | `read-only` | `none` | `sonnet` `medium` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix | - | simple, bounded, lookup, synthesis, or operational work |

### 08 Business & Product

| Agent | Current | Recommended Codex | Access | Approval | Recommended Claude | Claude perms | MCP/tools | Skills/steering | Rationale |
|---|---|---|---|---|---|---|---|---|---|
| `business-analyst` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, fetcher, github | - | reasoning/planning/orchestration or high-risk review |
| `content-marketer` | VoltAgent `gpt-5.3-codex-spark medium read-only` | `gpt-5.4-mini` `low` | `read-only` | `none` | `sonnet` `low` | `read-only` | filesystem, fetcher, github | - | simple, bounded, lookup, synthesis, or operational work; low effort is intentional |
| `customer-success-manager` | VoltAgent `gpt-5.3-codex-spark medium read-only` | `gpt-5.4-mini` `low` | `read-only` | `none` | `sonnet` `low` | `read-only` | filesystem | - | simple, bounded, lookup, synthesis, or operational work; low effort is intentional |
| `legal-advisor` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem | - | reasoning/planning/orchestration or high-risk review |
| `product-manager` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, github | - | reasoning/planning/orchestration or high-risk review |
| `project-manager` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, github | - | reasoning/planning/orchestration or high-risk review |
| `sales-engineer` | VoltAgent `gpt-5.3-codex-spark medium read-only` | `gpt-5.4-mini` `low` | `read-only` | `none` | `sonnet` `low` | `read-only` | filesystem, context7, codebase-memory-mcp, repomix | - | simple, bounded, lookup, synthesis, or operational work; low effort is intentional |
| `scrum-master` | VoltAgent `gpt-5.3-codex-spark medium read-only` | `gpt-5.4-mini` `low` | `read-only` | `none` | `sonnet` `low` | `read-only` | filesystem | - | simple, bounded, lookup, synthesis, or operational work; low effort is intentional |
| `technical-writer` | VoltAgent `gpt-5.3-codex-spark medium workspace-write` | `gpt-5.4-mini` `medium` | `workspace-write` | `on-request` | `sonnet` `medium` | `workspace-write` | filesystem | - | simple, bounded, lookup, synthesis, or operational work |
| `ux-researcher` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.4` `high` | `read-only` | `none` | `sonnet` `high` | `read-only` | filesystem, fetcher, github, playwright, stitch | interface-design, impeccable | frontend/design/product UI work with visual and browser verification |
| `wordpress-master` | VoltAgent `gpt-5.4 high workspace-write` | `gpt-5.4` `medium` | `workspace-write` | `on-request` | `sonnet` `medium` | `workspace-write` | filesystem, github, playwright, stitch | interface-design, impeccable | frontend/design/product UI work with visual and browser verification |

### 09 Meta & Orchestration

| Agent | Current | Recommended Codex | Access | Approval | Recommended Claude | Claude perms | MCP/tools | Skills/steering | Rationale |
|---|---|---|---|---|---|---|---|---|---|
| `agent-installer` | VoltAgent `gpt-5.3-codex-spark medium read-only` | `gpt-5.4-mini` `low` | `read-only` | `none` | `sonnet` `low` | `read-only` | filesystem | - | simple, bounded, lookup, synthesis, or operational work; low effort is intentional |
| `agent-organizer` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem | - | reasoning/planning/orchestration or high-risk review |
| `context-manager` | VoltAgent `gpt-5.3-codex-spark medium read-only` | `gpt-5.4-mini` `medium` | `read-only` | `none` | `sonnet` `medium` | `read-only` | filesystem | - | simple, bounded, lookup, synthesis, or operational work |
| `error-coordinator` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem | - | reasoning/planning/orchestration or high-risk review |
| `it-ops-orchestrator` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem | - | reasoning/planning/orchestration or high-risk review |
| `knowledge-synthesizer` | VoltAgent `gpt-5.3-codex-spark medium read-only` | `gpt-5.4-mini` `medium` | `read-only` | `none` | `sonnet` `medium` | `read-only` | filesystem | - | simple, bounded, lookup, synthesis, or operational work |
| `multi-agent-coordinator` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `xhigh` | `read-only` | `none` | `opus` `xhigh` | `read-only` | filesystem | - | reasoning/planning/orchestration or high-risk review; xhigh effort is intentional |
| `performance-monitor` | VoltAgent `gpt-5.3-codex-spark medium read-only` | `gpt-5.4-mini` `low` | `read-only` | `none` | `sonnet` `low` | `read-only` | filesystem | - | simple, bounded, lookup, synthesis, or operational work; low effort is intentional |
| `task-distributor` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem | - | reasoning/planning/orchestration or high-risk review |
| `workflow-orchestrator` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `xhigh` | `read-only` | `none` | `opus` `xhigh` | `read-only` | filesystem | - | reasoning/planning/orchestration or high-risk review; xhigh effort is intentional |

### 10 Research & Analysis

| Agent | Current | Recommended Codex | Access | Approval | Recommended Claude | Claude perms | MCP/tools | Skills/steering | Rationale |
|---|---|---|---|---|---|---|---|---|---|
| `competitive-analyst` | VoltAgent `gpt-5.3-codex-spark medium read-only` | `gpt-5.4-mini` `medium` | `read-only` | `none` | `sonnet` `medium` | `read-only` | filesystem, fetcher, github | - | simple, bounded, lookup, synthesis, or operational work |
| `data-researcher` | VoltAgent `gpt-5.3-codex-spark medium read-only` | `gpt-5.4-mini` `medium` | `read-only` | `none` | `sonnet` `medium` | `read-only` | filesystem, fetcher, github | - | simple, bounded, lookup, synthesis, or operational work |
| `docs-researcher` | VoltAgent `gpt-5.3-codex-spark medium read-only` | `gpt-5.4-mini` `medium` | `read-only` | `none` | `sonnet` `medium` | `read-only` | filesystem, fetcher, github | - | simple, bounded, lookup, synthesis, or operational work |
| `market-researcher` | VoltAgent `gpt-5.3-codex-spark medium read-only` | `gpt-5.4-mini` `medium` | `read-only` | `none` | `sonnet` `medium` | `read-only` | filesystem, fetcher, github | - | simple, bounded, lookup, synthesis, or operational work |
| `research-analyst` | VoltAgent `gpt-5.4 high read-only` | `gpt-5.5` `high` | `read-only` | `none` | `opus` `high` | `read-only` | filesystem, fetcher, github | - | reasoning/planning/orchestration or high-risk review |
| `search-specialist` | VoltAgent `gpt-5.3-codex-spark medium read-only` | `gpt-5.4-mini` `low` | `read-only` | `none` | `sonnet` `low` | `read-only` | filesystem, fetcher, github | - | simple, bounded, lookup, synthesis, or operational work; low effort is intentional |
| `trend-analyst` | VoltAgent `gpt-5.3-codex-spark medium read-only` | `gpt-5.4-mini` `medium` | `read-only` | `none` | `sonnet` `medium` | `read-only` | filesystem, fetcher, github | - | simple, bounded, lookup, synthesis, or operational work |
