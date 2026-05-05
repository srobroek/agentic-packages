# Salesforce Activity Payload

## Activity Types

Common values:

- Discovery Call
- Call
- Email
- Demo
- Workshop
- Executive Briefing
- POC Review
- Negotiation
- Onboarding
- Follow-up

Use the user's terminology when it maps cleanly. Otherwise choose the closest
standard type and show it in the preview.

## Preview

```markdown
## Salesforce Activity Preview

- Account: <name> (<id>)
- Opportunity: <name> (<id or none>)
- Type:
- Date:
- Subject:
- Description:
- Contacts:
- Outcome:
- Next steps:
- Duration:
- Source references:
```

## Creation Result

After creation, report:

- SFDC activity ID or link when available
- related account/opportunity
- follow-up items logged
- anything not created because the MCP did not expose the needed operation

## Missing Write Capability

If the MCP only supports read/search:

```markdown
I found and confirmed the SFDC records, but the active SFDC MCP does not expose
a create/write activity operation. Here is the ready-to-create payload:

...
```
