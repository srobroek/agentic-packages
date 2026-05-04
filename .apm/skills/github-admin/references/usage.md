# GitHub Admin Usage

- Use plain `gh` for interactive one-off operations such as repo inspection, repo creation, branch protection, environment setup, PR updates, and single issue operations.
- Use `scripts/gh-api.py` only when repeated operations, retries, rate limits, project automation, or batch execution matter.
- Plain `gh api` is acceptable for one-off REST or GraphQL calls; use the wrapper for a sequence of mutative API calls.
- Prefer `--body-file` over long inline bodies for issues and PRs.
- Keep GitHub-hosted workflow mechanics here instead of burying them inside unrelated skills.
