# Context Handoff

Use `work-context-fetcher` when the user asks to turn meetings, email, Slack,
notes, or transcripts into tracker entries.

## Parent Invocation Guidance

Ask the parent to pass:

- customer/account name if known
- date or date range
- meeting title, attendee, Slack channel/thread, or email keywords
- target tracker category if the user gave one
- any pasted notes or transcript snippets

## Consuming A Bundle

When the context bundle returns:

1. Match the account to an existing tracker tab.
2. If no tracker tab exists, stop normal logging and offer new tab setup.
3. Convert facts into tracker fields without adding unsupported claims.
4. Preserve source notes in `Notes` when they help later audit.
5. Preview the row and ask for confirmation before writing.

Do not ask `work-context-fetcher` to write anywhere. It only returns facts.
