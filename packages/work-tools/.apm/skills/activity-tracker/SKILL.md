---
name: activity-tracker
description: Manage the personal Excel activity tracker for account management, surge work, customer engagement, and SFDC-backed planning. Use when logging, reviewing, creating tracker tabs, generating account suggestions, checking stalled opportunities, or turning confirmed work context into tracker entries.
---

# Activity Tracker

Manage entries in the personal Excel tracker while preserving workbook history
and using tracker tabs as the account source of truth.

## Workflow

1. Load tracker sheets first; account tabs define the in-scope account set.
2. Reject logging, review, and suggestion requests for untracked accounts unless
   the user asks to create a new tab.
3. For meeting/email/Slack-derived entries, ask the parent to invoke
   `work-context-fetcher` and pass back its source-labeled bundle.
4. Use SFDC only for tracked accounts: account validation, opportunity links,
   open opportunity details, recent activity, and prioritization signals.
5. Preview every Excel write with target sheet, category, row, and values.
6. Write only after explicit user confirmation.

## Tracker Rules

- Workbook: `~/OneDrive - amazon.com/personal/Surge/Activity Tracking/Tracking.xlsx`.
- Template tab: `_TEMPLATE`.
- Categories: `Proactive Activities`, `Initiatives`, `Think Big`, `Outcomes`.
- Columns: `Name`, `Description`, `Activities`, `Notes`, `SFDC Link`, `Date`.
- Date format: `YYYY-MM-DD`.
- WORM default: create new entries unless the user explicitly asks to edit an
  existing row.

## New Account Tabs

Creating a new account tab is a separate setup action:

1. Search SFDC for the account.
2. Present the matched account and proposed tab name.
3. Preview that `_TEMPLATE` will be copied.
4. Ask for explicit confirmation.
5. Create the tab only after confirmation; then the account is in scope.

## Suggestions

Generate suggestions only when the user asks for recommendations, planning,
prioritization, stalled deals, account review, or "what should I do?"

Suggestions must be based on real SFDC data for tracked accounts, prioritized
by urgency and opportunity value, and linked to specific opportunities when
possible. See [suggestions.md](references/suggestions.md).

## References

- Workbook operations: [workbook.md](references/workbook.md)
- SFDC-backed suggestions: [suggestions.md](references/suggestions.md)
- Context handoff: [context.md](references/context.md)
