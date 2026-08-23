#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Generate architect effort-tier variants from the base definition.

Agent spawn calls carry `model` but NOT `effort` (effort is frontmatter-static).
So per-tier routing needs compiled variants. This stamps the base
architect.agent.md into architect-<tier>.agent.md, changing
only the `effort:` frontmatter line and the `name:`. One source of truth (the
base file + its shared rules file); variants are generated, never hand-edited.

Each tier name buys the effort it names. A tier that silently delivered a lower
effort made the config unreadable, because nothing at the call site could tell a
deliberate ceiling from a typo. The check at the bottom enforces name == effort.

The ladder is TWO rungs, and they differ on both axes at once:

    architect        Claude opus/medium   Codex Sol/medium   default
    architect-high   Claude opus/high     Codex Sol/high     escalation

That alignment is the point. The previous four-rung ladder crossed its own names
on the Codex side -- `-medium` sat on Luna/high while the base and `-xhigh` both
sat on Sol -- so a reader could not tell which rung a variant actually bought.
Now the rung is one step on both vendors simultaneously.

Retired tiers, all swept by RETIRED on each run:

  `low`     deleted 2026-07-26. Its Codex cell (Luna/low) is Haiku-class --
            Terminal-Bench v2.1 43.4 against Haiku 4.5's 44.2 -- so the tier
            promised a cheap specialist and delivered one that fails silently.
  `medium`  folded into the base, which now IS the medium rung. It was the only
            Luna cell in the ladder and the only variant whose Codex pin
            contradicted its name.
  `xhigh`   dropped. Measured effort ladders flatten at `high`: tau3 peaks there
            and declines twice above it, GPQA high and xhigh are byte-identical
            for 42% more tokens, and tool use regresses. There is nothing above
            `high` worth routing to, so the escalation rung IS `high`.

See `.audit-2026-07/findings/MODEL-MATRIX.md` for the per-effort numbers.

`-high` is ESCALATION-ONLY and the orchestrator must not select it by default.
Reach for it only when a node has already failed at the default rung and the
failure was reasoning depth rather than context, tooling, or scope. Its file says
so at the top of its body.

Run from anywhere: `uv run gen-architect-variants.py`. Idempotent.
Orchestrator tier table maps complexity_tier -> (variant, model).
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AGENTS = os.path.abspath(os.path.join(HERE, "..", ".apm", "agents"))
BASE = os.path.join(AGENTS, "architect.agent.md")
# Both trees are git-tracked and both were hand-synced before this script owned
# the mirror, so regenerating only .apm/ let the mirror drift silently.
MIRROR = os.path.abspath(os.path.join(HERE, "..", "agents"))
TIER_EFFORT = {"high": "high"}
# Variants this script used to generate and no longer does. Left-over files would
# keep routing traffic to a deleted tier, so the run deletes them and says so.
RETIRED = ("low", "medium", "xhigh")

# Prepended to a variant's body when the tier carries a usage restriction. The
# generator owns this text so it cannot drift from TIER_EFFORT.
TIER_NOTE = {
    "high": (
        "> **Escalation-only tier.** Do not select this variant as a default. "
        "Measured effort ladders flatten here: above it, benchmark scores "
        "plateau or decline, token cost rises ~42%, and tool use regresses. Use "
        "`-high` only after a node has failed at the default rung AND the failure was "
        "reasoning depth, not missing context, a tooling block, or bad scope. "
        "If you cannot name which default-rung attempt failed, the answer is "
        "`architect`, not this."
    ),
}
GEN_MARK = "<!-- GENERATED variant of architect.agent.md -- do not hand-edit; run gen-architect-variants.py -->"


def main():
    with open(BASE) as fh:
        base = fh.read()

    written = []
    for tier, effort in TIER_EFFORT.items():
        text = base
        # Rewrite name: architect -> architect-<tier>
        text = re.sub(r"^name:\s*architect\s*$",
                      f"name: architect-{tier}", text, count=1, flags=re.M)
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
        out = os.path.join(AGENTS, f"architect-{tier}.agent.md")
        with open(out, "w") as fh:
            fh.write(text)
        written.append(os.path.basename(out))
        # Keep the tracked mirror byte-identical. Only overwrite a file that is
        # already there: creating one would invent a package surface.
        mirror = os.path.join(MIRROR, f"architect-{tier}.md")
        if os.path.exists(mirror):
            with open(mirror, "w") as fh:
                fh.write(text)

    # Sweep retired tiers. A stale variant file is worse than a missing one: the
    # agent stays selectable by name long after the tier was removed on purpose.
    swept = []
    for tier in RETIRED:
        for p in (os.path.join(AGENTS, f"architect-{tier}.agent.md"),
                  os.path.join(MIRROR, f"architect-{tier}.md")):
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
        p = os.path.join(AGENTS, f"architect-{tier}.agent.md")
        with open(p) as fh:
            text = fh.read()
        head = text[:600]
        if f"name: architect-{tier}" not in head or f"effort: {effort}" not in head:
            print(f"  FAIL {tier}: frontmatter mismatch")
            ok = False
        if tier in TIER_NOTE and TIER_NOTE[tier] not in text:
            print(f"  FAIL {tier}: usage restriction missing from body")
            ok = False
        mirror = os.path.join(MIRROR, f"architect-{tier}.md")
        if os.path.exists(mirror):
            with open(mirror) as fh:
                if fh.read() != text:
                    print(f"  FAIL {tier}: mirror out of sync")
                    ok = False
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
