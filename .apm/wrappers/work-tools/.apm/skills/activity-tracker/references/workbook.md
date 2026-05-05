# Workbook Operations

## Add Entry

Gather these fields:

- Category: `Proactive Activities`, `Initiatives`, `Think Big`, or `Outcomes`
- Name
- Description
- Activities
- Notes
- SFDC Link
- Date in `YYYY-MM-DD`

Required fields are `Name`, `Description`, and `Date`. Ask for missing required
fields before previewing a write.

Preview format:

```markdown
Adding to: <Sheet Name>
Category: <Category>
Row: <Next available row>

| Name | Description | Activities | Notes | SFDC Link | Date |
|---|---|---|---|---|---|
| ... | ... | ... | ... | ... | ... |
```

Ask: `Please confirm this entry is correct and should be added.`

## Review Entries

1. List tracker sheets first.
2. Confirm the account/sheet.
3. Read the relevant category or date range.
4. Display entries in a readable table.
5. Summarize by category only when requested.

## Edit Entry

Editing is rare. The user must explicitly request it.

1. Show the current row.
2. Show proposed changes as a before/after.
3. Suggest adding a new entry instead if the edit changes history.
4. Apply only after explicit confirmation.

## Data Integrity

- Preserve existing formatting where possible.
- Do not delete rows unless the user explicitly asks and confirms the exact row.
- Do not invent SFDC links. Leave blank or ask when no validated record exists.
- Keep tracker tab names stable; do not rename tabs as part of normal logging.
