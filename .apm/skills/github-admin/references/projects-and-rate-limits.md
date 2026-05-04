# Projects And Rate Limits

- Use the rate-limited wrapper for bulk issue creation, project item mutation, batched GraphQL operations, or any workflow that risks secondary rate limits.
- Prefer REST when it can do the job cleanly.
- Use GraphQL only for operations with no good REST equivalent.
- Keep project-field and issue-link mechanics here, not in general steering.
