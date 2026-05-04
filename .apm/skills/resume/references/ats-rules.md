# ATS Compliance Rules

## DOCX Formatting

### NEVER use
| Element | Why |
|---------|-----|
| Tables | ATS reads left-to-right across rows, scrambles multi-column content |
| Multi-column layouts | Content read across instead of down |
| Text boxes | Content inside is invisible to most parsers |
| Headers/footers | Most ATS skip these — contact info placed here is LOST |
| Graphics/images/logos | Completely unreadable |
| SmartArt / Word Art | Rendered as image, not text |
| Icons (phone, email) | Render as garbage characters |
| Floating objects | Invisible to text parsers |

### Safe to use
Bold, italics, underline (sparingly), standard bullets (round or square), horizontal lines, ALL CAPS for headings, hyperlinks on non-critical text.

### Fonts
Calibri, Arial, Cambria, Garamond, Georgia, Helvetica, Times New Roman. Body: 10-12pt. Headings: 14-16pt. Name: 16-20pt.

### Layout
Single column. Left-aligned. 0.75-1" margins. 1.0-1.15 line spacing.

### File
- Format: `.docx` (96.7% parsability — best across all ATS)
- Name: `FirstName_LastName_Resume.docx`
- Size: < 10MB (SAP SuccessFactors limit)

## Section Names

Use EXACTLY these — ATS uses Named Entity Recognition to map content:

| Use | Never |
|-----|-------|
| Professional Summary | About Me, Who I Am, Executive Profile |
| Professional Experience | Career Journey, My Story |
| Core Competencies or Technical Skills | What I Know, Toolkit |
| Education | Academic Background |
| Certifications | Credentials |
| Honors & Awards | Recognition |

## Section Order (GCC-optimized)

1. Name + Contact Info (phone, email, LinkedIn, GitHub, city)
2. Professional Summary (3-5 lines)
3. Core Competencies (pipe-separated flat text)
4. Professional Experience (reverse-chronological)
5. Education
6. Certifications
7. Languages (if applicable)
8. Honors & Awards

## Keywords

- Include each critical keyword 2-3 times across different sections
- Always spell out acronyms on first use: "Natural Language Processing (NLP)"
- Target 75%+ match rate against target JD
- Placement priority: Summary > Skills > Experience bullets > Certifications
- NEVER use hidden/white text — modern ATS detect and flag this
- NEVER create standalone keyword lists without context

## Bullets

Every bullet must follow: **Action verb + What + Measurable result**

```
BAD:  Responsible for cloud migration projects
GOOD: Delivered 4 enterprise cloud migrations totaling $3M+ in new ARR
```

## Date Format

`Month YYYY – Month YYYY` or `MM/YYYY – MM/YYYY`. Be consistent. Use "Present" for current role.

## GCC/MENA Additions

- Include visa/residency status near contact info
- 2 pages standard, 3 acceptable for senior leadership
- English primary; note Arabic proficiency if applicable
- Highlight GCC/MENA regional experience explicitly
- SAP SuccessFactors: DOCX strongly preferred, 5-7 core keywords

## Vendor-Specific Notes

| ATS | Watch out for |
|-----|--------------|
| Workday | Columns, graphics, non-standard headings |
| Greenhouse | Headers, tables, large files, incomplete titles |
| SAP SuccessFactors | Scanned PDFs, tables, text boxes |
| Lever | Unexpanded acronyms, tables |
| iCIMS | Images, symbols, unusual fonts |
