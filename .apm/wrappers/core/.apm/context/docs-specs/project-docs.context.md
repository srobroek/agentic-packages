# Project Docs

Split docs by purpose. Prefer these files when the project needs durable shared
knowledge:

- `docs/architecture.md` for architecture, runtime shape, boundaries, diagrams,
  and important flows.
- `docs/stack.md` for languages, package managers, frameworks, infrastructure,
  storage, deployment, and quality tooling.
- `docs/decisions.md` or `docs/decisions/*.md` for durable decisions.
- `docs/research.md` or `docs/research/*.md` for source-backed research.
- `docs/runbooks.md` or `docs/runbooks/*.md` for operational procedures.
- `docs/product.md` for product and domain context.
- `docs/engineering.md` for development workflows and repo conventions.
- `docs/operations.md` for deploy, hosting, secrets, monitoring, and incident
  handling.
- `docs/api.md` or `docs/api/*` for API documentation that is not generated
  from contract sources.

Read the relevant doc before making architecture or stack assumptions. If a
needed doc is missing during setup or brownfield ingestion, create a concise
initial version instead of bloating runtime instruction files.

Use Astro for marketing or content docs, VitePress for technical docs, and
Storybook for shared UI or design systems.
