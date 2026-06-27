# Discovery Sources

Use APM inventory first. For brownfield migrations, start with the primary
marketplace baseline and broaden only after gap analysis. Broaden to public
sources only when the requested capability is missing, stale, or the user asks
for external discovery.

## APM Sources

- First-party marketplace:
  `apm marketplace add srobroek/agentic-packages --name srobroek-agentic`
- Primary baseline package:
  `core@srobroek-agentic`
- Browse inventory:
  `apm marketplace browse <marketplace-name>`
- Install selected package:
  `apm install <package>@<marketplace-name>`

Registered external marketplaces may be valid project sources when explicitly
selected. Common examples:

- `wshobson-agents`: `wshobson/agents`
- `voltagent-subagents`: `VoltAgent/awesome-claude-code-subagents`

APM does not federate marketplaces through another marketplace. Register each
selected marketplace side by side and keep chosen packages explicit.

## Public Sources

Choose sources by artifact type:

- Skills: `skills.sh`, SkillsGate, MCP.Directory skills, source repos
- MCP servers: Official MCP Registry, MCP.Directory, Glama, PulseMCP
- MCP connectors/tools: Glama tools/connectors, Smithery, MCP.Directory
- Agents/subagents: registered APM marketplaces first, GitHub fallback
- Design systems and DESIGN.md: getdesign.md, Stitch/design skills, Impeccable,
  Interface Design
- Broad fallback: GitHub source search, filtered by source quality and license

Prefer registry pages for discovery and source repositories for verification.
Never treat an install snippet as sufficient review.

## Optional CLI Discovery

Use only when available and useful:

```bash
npx skills find "<query>"
smithery search "<query>" --json
smithery skills search "<query>"
smithery inspect <namespace/server>
smithery connect search "<capability>"
```

Do not let these commands write runtime installs unless the user explicitly
approves a trial.
