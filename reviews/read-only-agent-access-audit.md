# Read-Only Agent Access Audit

This audit records which agents should remain advisory/read-only and which should have write access in the APM migration.

## Runtime Constraint

- Codex supports nested subagent workflows through `agents.max_depth`, but the default depth is `1`; keep it there unless recursive delegation is explicitly needed.
- Claude Code subagents cannot spawn other subagents. Use the main conversation to chain subagents, or run an agent as the main thread when it needs controlled subagent spawning.
- Therefore, agent definitions should not depend on nested subagent delegation for correctness. A write-capable agent may ask the parent to delegate, but the parent remains the reliable orchestrator.

## Policy

- Keep agents `read-only` when the prompt is review, research, architecture, security, compliance, legal, risk, analysis, or orchestration and the expected output is findings or recommendations.
- Use `workspace-write` when the prompt's expected artifact is a repository change: implementation, docs, API docs, technical writing, config, scripts, tests, deployment files, or chezmoi source edits.
- For read-only agents that find required changes, return an implementation brief for the parent session to dispatch to `coder`, a language specialist, or another write-capable agent.

## Summary

- Total agents reviewed: `149`.
- Recommended `read-only`: `69`.
- Recommended `workspace-write`: `80`.
- Read/write corrections called out below: `15`.

## Write-Capable Corrections

| Agent | Model | Upstream access | Recommended access | Rationale |
|---|---|---|---|---|
| `api-documenter` | `gpt-5.4-mini` `medium` | `workspace-write` | `workspace-write` | simple, bounded, lookup, synthesis, or operational work |
| `azure-infra-engineer` | `gpt-5.3-codex` `high` | `read-only` | `workspace-write` | complex/specialized implementation; access differs from upstream read-only |
| `chezmoi-editor` | `gpt-5.4-mini` `medium` | `n/a` | `workspace-write` | edits chezmoi-managed source files, not rendered live targets |
| `debugger` | `gpt-5.3-codex` `high` | `read-only` | `workspace-write` | complex/specialized implementation; access differs from upstream read-only |
| `documentation-engineer` | `gpt-5.4-mini` `medium` | `workspace-write` | `workspace-write` | simple, bounded, lookup, synthesis, or operational work |
| `error-detective` | `gpt-5.3-codex-spark` `medium` | `read-only` | `workspace-write` | fast bounded code loop or mechanical implementation; access differs from upstream read-only |
| `fintech-engineer` | `gpt-5.5` `high` | `workspace-write` | `workspace-write` | reasoning/planning/orchestration or high-risk review |
| `kubernetes-specialist` | `gpt-5.3-codex` `high` | `read-only` | `workspace-write` | complex/specialized implementation; access differs from upstream read-only |
| `legacy-modernizer` | `gpt-5.3-codex` `high` | `read-only` | `workspace-write` | complex/specialized implementation; access differs from upstream read-only |
| `postgres-pro` | `gpt-5.3-codex` `high` | `read-only` | `workspace-write` | complex/specialized implementation; access differs from upstream read-only |
| `sql-pro` | `gpt-5.3-codex` `high` | `read-only` | `workspace-write` | complex/specialized implementation; access differs from upstream read-only |
| `technical-writer` | `gpt-5.4-mini` `medium` | `workspace-write` | `workspace-write` | simple, bounded, lookup, synthesis, or operational work |
| `terraform-engineer` | `gpt-5.3-codex` `high` | `read-only` | `workspace-write` | complex/specialized implementation; access differs from upstream read-only |
| `terragrunt-expert` | `gpt-5.3-codex-spark` `medium` | `read-only` | `workspace-write` | fast bounded code loop or mechanical implementation; access differs from upstream read-only |
| `windows-infra-admin` | `gpt-5.3-codex` `high` | `read-only` | `workspace-write` | complex/specialized implementation; access differs from upstream read-only |

## Read-Only Retained

| Agent | Model | Category | Rationale |
|---|---|---|---|
| `api-designer` | `gpt-5.5` `high` | `01-core-development` | reasoning/planning/orchestration or high-risk review |
| `code-mapper` | `gpt-5.3-codex-spark` `medium` | `01-core-development` | fast bounded code loop or mechanical implementation |
| `graphql-architect` | `gpt-5.5` `high` | `01-core-development` | reasoning/planning/orchestration or high-risk review |
| `microservices-architect` | `gpt-5.5` `high` | `01-core-development` | reasoning/planning/orchestration or high-risk review |
| `ui-designer` | `gpt-5.4` `high` | `01-core-development` | frontend/design/product UI work with visual and browser verification |
| `cloud-architect` | `gpt-5.5` `high` | `03-infrastructure` | reasoning/planning/orchestration or high-risk review |
| `database-administrator` | `gpt-5.5` `high` | `03-infrastructure` | reasoning/planning/orchestration or high-risk review |
| `devops-incident-responder` | `gpt-5.5` `high` | `03-infrastructure` | reasoning/planning/orchestration or high-risk review |
| `incident-responder` | `gpt-5.5` `high` | `03-infrastructure` | reasoning/planning/orchestration or high-risk review |
| `network-engineer` | `gpt-5.5` `high` | `03-infrastructure` | reasoning/planning/orchestration or high-risk review |
| `platform-engineer` | `gpt-5.5` `high` | `03-infrastructure` | reasoning/planning/orchestration or high-risk review |
| `security-engineer` | `gpt-5.5` `high` | `03-infrastructure` | reasoning/planning/orchestration or high-risk review |
| `sre-engineer` | `gpt-5.5` `high` | `03-infrastructure` | reasoning/planning/orchestration or high-risk review |
| `accessibility-tester` | `gpt-5.5` `high` | `04-quality-security` | reasoning/planning/orchestration or high-risk review |
| `ad-security-reviewer` | `gpt-5.5` `high` | `04-quality-security` | reasoning/planning/orchestration or high-risk review |
| `architect-reviewer` | `gpt-5.5` `high` | `04-quality-security` | reasoning/planning/orchestration or high-risk review |
| `chaos-engineer` | `gpt-5.5` `high` | `04-quality-security` | reasoning/planning/orchestration or high-risk review |
| `code-reviewer` | `gpt-5.5` `high` | `04-quality-security` | reasoning/planning/orchestration or high-risk review |
| `compliance-auditor` | `gpt-5.5` `high` | `04-quality-security` | reasoning/planning/orchestration or high-risk review |
| `penetration-tester` | `gpt-5.5` `high` | `04-quality-security` | reasoning/planning/orchestration or high-risk review |
| `performance-engineer` | `gpt-5.5` `high` | `04-quality-security` | reasoning/planning/orchestration or high-risk review |
| `powershell-security-hardening` | `gpt-5.5` `high` | `04-quality-security` | reasoning/planning/orchestration or high-risk review |
| `qa-expert` | `gpt-5.5` `high` | `04-quality-security` | reasoning/planning/orchestration or high-risk review |
| `reviewer` | `gpt-5.5` `high` | `04-quality-security` | reasoning/planning/orchestration or high-risk review |
| `security-auditor` | `gpt-5.5` `high` | `04-quality-security` | reasoning/planning/orchestration or high-risk review |
| `data-analyst` | `gpt-5.5` `high` | `05-data-ai` | reasoning/planning/orchestration or high-risk review |
| `data-scientist` | `gpt-5.5` `high` | `05-data-ai` | reasoning/planning/orchestration or high-risk review |
| `database-optimizer` | `gpt-5.5` `high` | `05-data-ai` | reasoning/planning/orchestration or high-risk review |
| `llm-architect` | `gpt-5.5` `high` | `05-data-ai` | reasoning/planning/orchestration or high-risk review |
| `prompt-engineer` | `gpt-5.5` `high` | `05-data-ai` | reasoning/planning/orchestration or high-risk review |
| `dx-optimizer` | `gpt-5.5` `high` | `06-developer-experience` | reasoning/planning/orchestration or high-risk review |
| `git-workflow-manager` | `gpt-5.4-mini` `medium` | `06-developer-experience` | simple, bounded, lookup, synthesis, or operational work |
| `m365-admin` | `gpt-5.5` `high` | `07-specialized-domains` | reasoning/planning/orchestration or high-risk review |
| `quant-analyst` | `gpt-5.5` `high` | `07-specialized-domains` | reasoning/planning/orchestration or high-risk review |
| `risk-manager` | `gpt-5.5` `high` | `07-specialized-domains` | reasoning/planning/orchestration or high-risk review |
| `seo-specialist` | `gpt-5.4-mini` `medium` | `07-specialized-domains` | simple, bounded, lookup, synthesis, or operational work |
| `business-analyst` | `gpt-5.5` `high` | `08-business-product` | reasoning/planning/orchestration or high-risk review |
| `content-marketer` | `gpt-5.4-mini` `low` | `08-business-product` | simple, bounded, lookup, synthesis, or operational work; low effort is intentional |
| `customer-success-manager` | `gpt-5.4-mini` `low` | `08-business-product` | simple, bounded, lookup, synthesis, or operational work; low effort is intentional |
| `legal-advisor` | `gpt-5.5` `high` | `08-business-product` | reasoning/planning/orchestration or high-risk review |
| `product-manager` | `gpt-5.5` `high` | `08-business-product` | reasoning/planning/orchestration or high-risk review |
| `project-manager` | `gpt-5.5` `high` | `08-business-product` | reasoning/planning/orchestration or high-risk review |
| `sales-engineer` | `gpt-5.4-mini` `low` | `08-business-product` | simple, bounded, lookup, synthesis, or operational work; low effort is intentional |
| `scrum-master` | `gpt-5.4-mini` `low` | `08-business-product` | simple, bounded, lookup, synthesis, or operational work; low effort is intentional |
| `ux-researcher` | `gpt-5.4` `high` | `08-business-product` | frontend/design/product UI work with visual and browser verification |
| `agent-installer` | `gpt-5.4-mini` `low` | `09-meta-orchestration` | simple, bounded, lookup, synthesis, or operational work; low effort is intentional |
| `agent-organizer` | `gpt-5.5` `high` | `09-meta-orchestration` | reasoning/planning/orchestration or high-risk review |
| `context-manager` | `gpt-5.4-mini` `medium` | `09-meta-orchestration` | simple, bounded, lookup, synthesis, or operational work |
| `error-coordinator` | `gpt-5.5` `high` | `09-meta-orchestration` | reasoning/planning/orchestration or high-risk review |
| `it-ops-orchestrator` | `gpt-5.5` `high` | `09-meta-orchestration` | reasoning/planning/orchestration or high-risk review |
| `knowledge-synthesizer` | `gpt-5.4-mini` `medium` | `09-meta-orchestration` | simple, bounded, lookup, synthesis, or operational work |
| `multi-agent-coordinator` | `gpt-5.5` `xhigh` | `09-meta-orchestration` | reasoning/planning/orchestration or high-risk review; xhigh effort is intentional |
| `performance-monitor` | `gpt-5.4-mini` `low` | `09-meta-orchestration` | simple, bounded, lookup, synthesis, or operational work; low effort is intentional |
| `task-distributor` | `gpt-5.5` `high` | `09-meta-orchestration` | reasoning/planning/orchestration or high-risk review |
| `workflow-orchestrator` | `gpt-5.5` `xhigh` | `09-meta-orchestration` | reasoning/planning/orchestration or high-risk review; xhigh effort is intentional |
| `competitive-analyst` | `gpt-5.4-mini` `medium` | `10-research-analysis` | simple, bounded, lookup, synthesis, or operational work |
| `data-researcher` | `gpt-5.4-mini` `medium` | `10-research-analysis` | simple, bounded, lookup, synthesis, or operational work |
| `docs-researcher` | `gpt-5.4-mini` `medium` | `10-research-analysis` | simple, bounded, lookup, synthesis, or operational work |
| `market-researcher` | `gpt-5.4-mini` `medium` | `10-research-analysis` | simple, bounded, lookup, synthesis, or operational work |
| `research-analyst` | `gpt-5.5` `high` | `10-research-analysis` | reasoning/planning/orchestration or high-risk review |
| `search-specialist` | `gpt-5.4-mini` `low` | `10-research-analysis` | simple, bounded, lookup, synthesis, or operational work; low effort is intentional |
| `trend-analyst` | `gpt-5.4-mini` `medium` | `10-research-analysis` | simple, bounded, lookup, synthesis, or operational work |
| `adversarial-challenger` | `gpt-5.5` `xhigh` | `current-configured` | reasoning/planning/orchestration or high-risk review; xhigh effort is intentional |
| `pr-reviewer` | `gpt-5.5` `high` | `current-configured` | reasoning/planning/orchestration or high-risk review |
| `speckit-research` | `gpt-5.4-mini` `medium` | `current-configured` | simple, bounded, lookup, synthesis, or operational work |
| `speckit-sync` | `gpt-5.5` `high` | `current-configured` | reasoning/planning/orchestration or high-risk review |
| `speckit-sync-conflicts` | `gpt-5.5` `high` | `current-configured` | reasoning/planning/orchestration or high-risk review |
| `speckit-verify` | `gpt-5.5` `high` | `current-configured` | reasoning/planning/orchestration or high-risk review |
| `speckit-verify-tasks` | `gpt-5.5` `high` | `current-configured` | reasoning/planning/orchestration or high-risk review |
