---
name: resume
description: Create, update, or tailor ATS-compliant resumes. Use when user wants a new resume, resume update, or resume customized for a specific job posting.
allowed-tools: Agent, Read, Write, Edit, Bash, WebFetch, mcp__linkedin__get_person_profile, mcp__m365-mcp__search_emails, mcp__m365-mcp__get_calendar_events, mcp__aws-central-mcp__search_opportunities, mcp__aws-central-mcp__list_user_assigned_accounts, mcp__aws-central-mcp__search_events
---

# Resume

Create, update, or tailor ATS-compliant resumes from LinkedIn, SFDC, calendar, and email data.

## Commands

- `/resume create` — Generate a new resume from scratch
- `/resume update` — Refresh an existing resume with new data
- `/resume tailor <url>` — Customize a resume for a specific job posting

## Workflow

### 1. Gather Data (parallel agents)

| Source | What to extract |
|--------|----------------|
| LinkedIn MCP | Full profile: roles, education, certs, skills, honors, projects |
| SFDC (aws-central-mcp) | Accounts, opportunities, activities, revenue metrics |
| Calendar (M365) | Customer engagements, workshops, hackathons, events |
| Email (M365) | Recognition, achievements, project outcomes, metrics |
| Existing resume | If updating, read current file first |

### 2. If Tailoring: Analyze Job Description

1. Fetch the JD via WebFetch
2. Extract: required skills, preferred skills, responsibilities, keywords
3. Run gap analysis: match user's experience to each requirement
4. Identify keywords to embed (aim for 75%+ match rate)
5. Note gaps honestly — don't fabricate experience

### 3. Select Template

| Target | Template |
|--------|----------|
| Senior IC (Principal/Staff SA) | `references/ic-senior.md` |
| Leadership (Head of AI, VP Eng) | `references/leadership.md` |
| GCC-tailored | Add GCC section to either template |

### 4. Write Resume Content

Fill the template following ALL rules in `references/ats-rules.md`. Key constraints:

- Single column, no tables, no text boxes
- Pipe-separated skills (not bullet lists)
- Standard section names only: "Professional Summary", "Core Competencies", "Professional Experience", "Education", "Certifications", "Honors & Awards"
- Every bullet: action verb + what + measurable result
- Acronyms spelled out on first use: "Natural Language Processing (NLP)"
- Keywords from JD appear 2-3 times across different sections
- 2 pages for senior roles, 3 max for GCC leadership

### 5. Convert to DOCX

Run the converter script:
```bash
python3 ~/.config/agentic-tools/skills/resume/scripts/md2docx.py <input.md> <output.docx>
```

### 6. Verify

- Open DOCX and visually check formatting
- Copy all text, paste into plain text editor — if anything is missing, ATS will lose it too
- Check file size < 10MB (SAP SuccessFactors limit)
- Verify keyword density against target JD (if tailoring)

## Rules

- NEVER use tables, columns, text boxes, headers/footers, images, SmartArt, or icons in output
- NEVER fabricate experience or inflate metrics
- NEVER include customer names — use anonymized descriptions (verticals, size, geography)
- Always include both acronym and full form: "Amazon Web Services (AWS)"
- GCC resumes: include visa/residency status, highlight regional experience, English primary
- File naming: `FirstName_LastName_Resume.docx` or `FirstName_LastName_CompanyName_Resume.docx`
- Output markdown resume to `~/personal/resume/` alongside the DOCX

## References

Read `references/ats-rules.md` for the full ATS compliance ruleset.
Read `references/ic-senior.md` for the Senior IC resume template.
Read `references/leadership.md` for the Leadership resume template.
