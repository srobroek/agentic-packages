# SFDC-Backed Suggestions

## Account Scope

Always list workbook sheets first. Excluding `_TEMPLATE`, those tabs are the
only accounts suggestions may cover.

## Data To Gather

For each tracked account in scope:

- SFDC account match and account ID
- open opportunities
- opportunity stage, amount, close date, owner, next step, and SFDC link
- recent tasks/events or last activity when available
- relevant tracker entries already recorded

## Signals

Prioritize:

- opportunities with no recent activity, especially over two weeks
- close dates within the next 30 days
- high-value opportunities without clear next steps
- validation-stage deals needing technical deep dives
- large opportunities missing stakeholder or executive engagement
- post-launch or expansion patterns that justify initiatives

## Output

```markdown
## Suggestions for <Account Name>

### Open Opportunities
| Opportunity | Stage | Close Date | Amount | Last Activity | Risk |
|---|---|---:|---:|---:|---|

### Recommended Proactive Activities
1. **Name**
   - Why:
   - Related opportunity:
   - Timing:

### Recommended Initiatives
1. **Name**
   - Why:
   - Expected outcome:

### Think Big Ideas
1. **Name**
   - Opportunity:
   - First step:
```

For all-account planning, sort the final list by urgency first and opportunity
value second.
