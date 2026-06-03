# Fetch Tool Selection

Choose the most structured source that can answer the question.

## Routing

- Product or SaaS resource: use its CLI, API, or MCP before scraping pages.
- GitHub resource: use `gh` or GitHub MCP for issues, PRs, releases, files, and
  repository metadata.
- API or SDK behavior: use official docs first. Use Context7 for library docs
  when it is available and current enough for the task.
- Exact URL: fetch that URL first. Follow only links needed to answer the
  user's question.
- Static page or PDF: use simple fetch/open.
- JS-heavy page, interactive state, bot block, or empty HTML shell: use a
  rendered browser fetch.

## Output

- State which source answered the question.
- Include links or stable identifiers.
- Separate fetched facts from inferences.
- Note access limits, missing content, or authentication blockers.
