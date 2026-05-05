---
name: prompt-lookup
description: Use when finding, comparing, or improving prompt templates and prompt-engineering patterns.
---

# Prompt Lookup

Search for and improve AI prompts: **$ARGUMENTS**

## When to Activate

- User asks for prompt templates ("Find me a code review prompt")
- User wants to search for prompts ("What prompts are available for writing?")
- User needs a specific prompt ("Get prompt XYZ")
- User wants to improve a prompt ("Make this prompt better")
- User mentions prompt libraries or prompt engineering

## Operations

### Search for prompts

Search by keyword with optional filters:
- **query**: search keywords from the user's request
- **limit**: number of results (default 10)
- **type**: TEXT, STRUCTURED, IMAGE, VIDEO, or AUDIO
- **category**: category slug (e.g., "coding", "writing")
- **tag**: tag slug

Present results showing: title, description, author, category, tags, and link.

### Get a specific prompt

Retrieve by ID. If the prompt contains variables (`${variable}` or `${variable:default}`), prompt the user to fill in values. Variables without defaults are required.

### Improve a prompt

Submit prompt text for enhancement. Specify output type (text, image, video, sound) and format (text, structured_json, structured_yaml). Return the enhanced version and explain what was improved.

## Guidelines

- Always search before suggesting the user write from scratch
- Present search results in a readable format with links
- When improving prompts, explain what was enhanced and why
- Suggest relevant categories and tags for discoverability
