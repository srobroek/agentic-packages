# Context Handoff

Use `work-context-fetcher` for calendar, email, Slack, notes, and transcript
context.

## Parent Invocation Guidance

Pass as many anchors as available:

- customer/account or opportunity name
- meeting date, date range, or title
- participants or email addresses
- Slack channel/thread link or keywords
- pasted notes or transcript snippets
- the target SFDC activity type if known

## Consuming A Bundle

1. Extract the likely activity date, people, subject, decisions, outcomes, and
   next steps.
2. Search SFDC for the relevant account, opportunity, and contacts.
3. Ask the user to choose when several SFDC records are plausible.
4. Keep source references in the payload preview, but avoid dumping long raw
   private content into Salesforce.
5. Ask for confirmation before writing.

Do not ask `work-context-fetcher` to write anywhere. It only returns facts.
