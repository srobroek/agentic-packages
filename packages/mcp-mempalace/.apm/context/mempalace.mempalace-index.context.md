# MemPalace — Cross-Session Memory

LEGEND: Rules carry stable IDs (MP-n). MemPalace is a local-first cross-session
memory layer (verbatim storage, local embeddings, zero LLM calls). It remembers
decisions, debugging threads, preferences, and conversation history ACROSS
sessions. It is NOT code navigation.

MUST MP-1: use MemPalace's MCP tools for CROSS-SESSION recall — prior decisions,
"why did we choose X", past debugging outcomes, earlier discussion of a topic.
This is memory of what happened in previous sessions, not the current code.

NOT MP-2: use MemPalace to explore the CURRENT codebase's structure (symbols,
call paths, references, architecture). Use the project's semantic symbol tools
and direct file inspection for that work. Do not conflate the two: MemPalace is
what we decided or learned before; semantic code tools inspect what exists now.

MUST MP-3: prefer searching MemPalace before re-deriving a decision or
re-investigating a problem that may have been resolved in an earlier session —
recall is cheaper and preserves the exact prior reasoning (storage is verbatim,
not a lossy summary).

MUST MP-4: store durable cross-session facts through MemPalace's MCP write tools
when a decision, rationale, or hard-won debugging result emerges that a future
session would benefit from — do not rely solely on end-of-session mining.

NOT MP-5: treat MemPalace as authoritative for current code or config values —
verbatim memory can be stale. Confirm code facts against the live tree with
semantic symbol tools or Read/Grep before acting on a remembered detail.

MUST MP-6: scope recall to the project's wing when the question is
project-specific (the wing is named for the repo), so recall is not diluted by
unrelated projects' memory.

FACT MP-7: transcript mining is automatic — a SessionEnd hook files each
completed session into the repo's wing. Do NOT run the mine script mid-session:
the miner freezes a transcript at first mine (no mtime re-check), so mining a
still-growing transcript permanently loses everything appended after that
point. The manual script (`.claude/hooks/mcp-mempalace/scripts/mempalace-mine.sh`;
`.codex/` under Codex) is for one-time backfill of historical transcripts, run
when no other session is active in the repo.

MUST MP-8: when a hard-won fact emerges mid-session that must survive even a
crashed session (root cause, settled decision, environment gotcha), file it
immediately with the mempalace_add_drawer MCP tool as a short distilled note —
do not wait for SessionEnd mining, and do not re-run the mine script for this.
