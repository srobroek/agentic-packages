#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Generate domain-specialist effort-tier variants from the base definition.

Agent spawn calls carry `model` but NOT `effort` (effort is frontmatter-static).
So per-tier routing needs compiled variants. This stamps the base
domain-specialist.agent.md into domain-specialist-<tier>.agent.md, changing
only the `effort:` frontmatter line and the `name:`. One source of truth (the
base file + its shared rules file); variants are generated, never hand-edited.

Each tier name buys the effort it names. `xhigh` means `effort: xhigh` — a tier
that silently delivered `high` made the config unreadable, because nothing at the
call site could tell a deliberate ceiling from a typo. This governs the Claude
frontmatter only. The Codex side is a separate mapping in `agent-models.yml` and
deliberately differs: there the tiers select a *model* as well as an effort
(`-medium` is Luna/high, the base is Sol/medium), because on the Codex ladder the
cheap-vs-deep step is a model step, not an effort step.

There is no `low` tier. It was deleted 2026-07-26: its Codex cell (Luna/low) is
Haiku-class — Terminal-Bench v2.1 43.4 against Haiku 4.5's 44.2, agentic 25.4 —
so the tier promised a cheap specialist and delivered one that fails silently.
See `.audit-2026-07/findings/MODEL-MATRIX.md`.

`xhigh` is an ESCALATION-ONLY tier and the orchestrator must not select it by
default. Measured effort ladders flatten at `high`: tau3 peaks there and declines
twice above it, GPQA high and xhigh are byte-identical for 42% more tokens, and
tool use regresses. Reach for it only when a node has already failed at `high`
and the failure was reasoning depth rather than context, tooling, or scope. Both
tier files say so at the top of their body.

`high` IS the base tier, so `domain-specialist-high` is a byte-for-byte duplicate
of `domain-specialist` apart from its `name:`. It is generated anyway because it
exists on `main` and another session's orchestrate rework reintroduced it after an
earlier audit PR deleted it; leaving it ungenerated would orphan a file that is
still selectable by name, which is strictly worse than a redundant one. Whether
the rework wants that variant or inherited it by accident is an open question —
ACTIONS 3.2 and 3.10.

Run from anywhere: `uv run gen-domain-specialist-variants.py`. Idempotent.
Orchestrator tier table maps complexity_tier -> (variant, model).
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AGENTS = os.path.abspath(os.path.join(HERE, "..", ".apm", "agents"))
BASE = os.path.join(AGENTS, "domain-specialist.agent.md")
# Both trees are git-tracked and both were hand-synced before this script owned
# the mirror, so regenerating only .apm/ let the mirror drift silently.
MIRROR = os.path.abspath(os.path.join(HERE, "..", "agents"))
TIER_EFFORT = {"medium": "medium", "high": "high", "xhigh": "xhigh"}
# Variants this script used to generate and no longer does. Left-over files would
# keep routing traffic to a deleted tier, so the run deletes them and says so.
RETIRED = ("low",)

# Prepended to a variant's body when the tier carries a usage restriction. The
# generator owns this text so it cannot drift from TIER_EFFORT.
TIER_NOTE = {
    "xhigh": (
        "> **Escalation-only tier.** Do not select this variant as a default. "
        "Measured effort ladders flatten at `high` — above it, benchmark scores "
        "plateau or decline, token cost rises ~42%, and tool use regresses. Use "
        "`xhigh` only after a node has failed at `high` AND the failure was "
        "reasoning depth, not missing context, a tooling block, or bad scope. "
        "If you cannot name which `high` attempt failed, the answer is "
        "`domain-specialist`, not this."
    ),
}
GEN_MARK = "<!-- GENERATED variant of domain-specialist.agent.md — do not hand-edit; run gen-domain-specialist-variants.py -->"


def main():
    with open(BASE) as fh:
        base = fh.read()

    written = []
    for tier, effort in TIER_EFFORT.items():
        text = base
        # Rewrite name: domain-specialist -> domain-specialist-<tier>
        text = re.sub(r"^name:\s*domain-specialist\s*$",
                      f"name: domain-specialist-{tier}", text, count=1, flags=re.M)
        # Rewrite effort:
        if re.search(r"^effort:\s*\S+\s*$", text, flags=re.M):
            text = re.sub(r"^effort:\s*\S+\s*$", f"effort: {effort}", text, count=1, flags=re.M)
        else:
            text = re.sub(r"(^model:.*$)", r"\1\neffort: " + effort, text, count=1, flags=re.M)
        # Insert a generated-marker just after the closing frontmatter fence,
        # followed by the tier's usage restriction if it has one.
        parts = text.split("---\n", 2)
        if len(parts) == 3:
            head = "---\n" + parts[1] + "---\n" + GEN_MARK + "\n"
            note = TIER_NOTE.get(tier)
            text = head + (f"\n{note}\n" if note else "") + parts[2]
        out = os.path.join(AGENTS, f"domain-specialist-{tier}.agent.md")
        with open(out, "w") as fh:
            fh.write(text)
        written.append(os.path.basename(out))
        # Keep the tracked mirror byte-identical. Only overwrite a file that is
        # already there: creating one would invent a package surface.
        mirror = os.path.join(MIRROR, f"domain-specialist-{tier}.md")
        if os.path.exists(mirror):
            with open(mirror, "w") as fh:
                fh.write(text)

    # Sweep retired tiers. A stale variant file is worse than a missing one: the
    # agent stays selectable by name long after the tier was removed on purpose.
    swept = []
    for tier in RETIRED:
        for p in (os.path.join(AGENTS, f"domain-specialist-{tier}.agent.md"),
                  os.path.join(MIRROR, f"domain-specialist-{tier}.md")):
            if os.path.exists(p):
                os.remove(p)
                swept.append(os.path.basename(p))

    print("generated:", ", ".join(written))
    if swept:
        print("swept retired:", ", ".join(swept))
    ok = True
    # A tier must buy the effort it is named after. Enforced here rather than
    # trusted, because the earlier xhigh->high mapping read as a typo at every
    # call site and cost an audit cycle to establish as deliberate.
    for tier, effort in TIER_EFFORT.items():
        if tier != effort:
            print(f"  FAIL {tier}: tier name must equal its effort, got {effort!r}")
            ok = False
    for tier, effort in TIER_EFFORT.items():
        p = os.path.join(AGENTS, f"domain-specialist-{tier}.agent.md")
        with open(p) as fh:
            text = fh.read()
        head = text[:600]
        if f"name: domain-specialist-{tier}" not in head or f"effort: {effort}" not in head:
            print(f"  FAIL {tier}: frontmatter mismatch")
            ok = False
        if tier in TIER_NOTE and TIER_NOTE[tier] not in text:
            print(f"  FAIL {tier}: usage restriction missing from body")
            ok = False
        mirror = os.path.join(MIRROR, f"domain-specialist-{tier}.md")
        if os.path.exists(mirror):
            with open(mirror) as fh:
                if fh.read() != text:
                    print(f"  FAIL {tier}: mirror out of sync")
                    ok = False
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
