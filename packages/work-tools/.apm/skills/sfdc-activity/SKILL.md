---
name: sfdc-activity
description: Create or prepare Salesforce activity records from meetings, calls, email, Slack, calendar events, notes, transcripts, or user input. Use when logging customer interactions to SFDC, reconstructing meeting outcomes, finding related account/opportunity/contact records, or preparing confirmed activity payloads.
---

# SFDC Activity

Create or prepare Salesforce activity records with explicit confirmation and
source-labeled context.

## Workflow

1. Gather or fetch context. For meeting/email/Slack-derived requests, ask the
   parent to invoke `work-context-fetcher` and pass back its bundle.
2. Search SFDC through `aws-central-mcp` for the account, opportunity, and
   contacts.
3. Resolve ambiguous SFDC matches with the user.
4. Build an activity payload with required fields and source-backed details.
5. Preview the exact payload.
6. Create the SFDC activity only after explicit user confirmation and only when
   the active SFDC MCP exposes a write/create operation.
7. If no write/create operation is available, return the ready-to-create payload
   and state that creation is blocked by missing write capability.

## Required Fields

- Account or opportunity
- Activity type
- Date
- Subject
- Description

Optional fields: contacts, next steps, outcome, duration, related opportunity,
source references, and follow-up tasks.

## Source Policy

- Automatically use available Outlook calendar, Outlook email, Slack, notes,
  transcripts, and user-provided snippets through `work-context-fetcher` when
  reconstructing an activity.
- Summarize findings before any write.
- Do not include unsupported claims in the Salesforce description.
- Keep descriptions professional, concise, and tied to customer outcomes.

## Confirmation

Always ask for explicit confirmation before any SFDC write:

`Please confirm this Salesforce activity payload is correct and should be created.`

## References

- Activity payloads: [payload.md](references/payload.md)
- Context handoff: [context.md](references/context.md)
