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

`xhigh` maps to `effort: high`: above `high`, measured effort ladders show no
capability gain and a tool-use regression, so the tier name is a routing label
the orchestrator selects, not the effort it buys. There is no `high` variant —
it would be a byte-for-byte duplicate of the base definition.

Run from anywhere: `uv run gen-domain-specialist-variants.py`. Idempotent.
Orchestrator tier table maps complexity_tier -> (variant, model).
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AGENTS = os.path.abspath(os.path.join(HERE, "..", ".apm", "agents"))
BASE = os.path.join(AGENTS, "domain-specialist.agent.md")
TIER_EFFORT = {"low": "low", "medium": "medium", "xhigh": "high"}
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
        # Insert a generated-marker just after the closing frontmatter fence.
        parts = text.split("---\n", 2)
        if len(parts) == 3:
            text = "---\n" + parts[1] + "---\n" + GEN_MARK + "\n" + parts[2]
        out = os.path.join(AGENTS, f"domain-specialist-{tier}.agent.md")
        with open(out, "w") as fh:
            fh.write(text)
        written.append(os.path.basename(out))

    print("generated:", ", ".join(written))
    # Verify each parses a frontmatter block with the right name+effort.
    ok = True
    for tier, effort in TIER_EFFORT.items():
        p = os.path.join(AGENTS, f"domain-specialist-{tier}.agent.md")
        with open(p) as fh:
            head = fh.read(600)
        if f"name: domain-specialist-{tier}" not in head or f"effort: {effort}" not in head:
            print(f"  FAIL {tier}: frontmatter mismatch")
            ok = False
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
