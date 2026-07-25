# MemPalace -- Cross-Session Memory

LEGEND: Rules carry stable IDs (MP-n). MemPalace is a local-first cross-session
memory layer (verbatim storage, local embeddings, zero LLM calls). It remembers
decisions, debugging threads, preferences, and conversation history ACROSS
sessions.

MUST MP-1: use MemPalace's MCP tools for CROSS-SESSION recall -- prior decisions,
"why did we choose X", past debugging outcomes, earlier discussion of a topic.
This is memory of what happened in previous sessions, not the current code.

NOT MP-2: use MemPalace to explore the CURRENT codebase's structure (symbols,
call paths, references, architecture). Use the project's semantic symbol tools
and direct file inspection for that work.

MUST MP-3: prefer searching MemPalace before re-deriving a decision or
re-investigating a problem that may have been resolved in an earlier session --
recall is cheaper and preserves the exact prior reasoning (storage is verbatim,
not a lossy summary).

MUST MP-4: file a hard-won fact (root cause, settled decision, environment
gotcha) through MemPalace's MCP write tools as soon as it emerges mid-session, so
it survives a crashed session -- do not rely on end-of-session mining, and do not
re-run the mine script for it (see MP-7).

NOT MP-5: treat MemPalace as authoritative for current code or config values -- a
memory records what was true when it was written, not what is true now.

MUST MP-6: scope recall to the project's wing when the question is
project-specific (the wing is named for the repo), so recall is not diluted by
unrelated projects' memory.

FACT MP-7: transcript mining is automatic -- a SessionEnd hook files each
completed session into the repo's wing. Do NOT run the mine script mid-session:
the miner freezes a transcript at first mine (no mtime re-check), so mining a
still-growing transcript permanently loses everything appended after that
point. The manual script (`.claude/hooks/mcp-mempalace/scripts/mempalace-mine.sh`;
`.codex/` under Codex) is for one-time backfill of historical transcripts, run
when no other session is active in the repo.
