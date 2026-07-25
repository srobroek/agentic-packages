#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Generate coder effort-tier variants from the base definition.

Agent spawn calls carry `model` but NOT `effort` (effort is frontmatter-static).
So per-tier routing needs compiled variants. This stamps the base
domain-specialist.agent.md into coder-{low,medium,high,xhigh}.agent.md,
changing only the `effort:` frontmatter line and the `name:`. One source of
truth (the base file + its shared rules file); variants are generated, never
hand-edited.

Run from anywhere: `uv run gen-coder-variants.py`. Idempotent.
Orchestrator tier table maps complexity_tier -> (variant, model).
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AGENTS = os.path.abspath(os.path.join(HERE, "..", ".apm", "agents"))
BASE = os.path.join(AGENTS, "domain-specialist.agent.md")
TIERS = ["low", "medium", "high", "xhigh"]
GEN_MARK = "<!-- GENERATED variant of domain-specialist.agent.md — do not hand-edit; run gen-coder-variants.py -->"


def main():
    with open(BASE) as fh:
        base = fh.read()

    written = []
    for tier in TIERS:
        text = base
        # Rewrite name: domain-specialist -> coder-<tier>
        text = re.sub(r"^name:\s*domain-specialist\s*$",
                      f"name: domain-specialist-{tier}", text, count=1, flags=re.M)
        # Rewrite effort:
        if re.search(r"^effort:\s*\S+\s*$", text, flags=re.M):
            text = re.sub(r"^effort:\s*\S+\s*$", f"effort: {tier}", text, count=1, flags=re.M)
        else:
            text = re.sub(r"(^model:.*$)", r"\1\neffort: " + tier, text, count=1, flags=re.M)
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
    for tier in TIERS:
        p = os.path.join(AGENTS, f"domain-specialist-{tier}.agent.md")
        with open(p) as fh:
            head = fh.read(600)
        if f"name: domain-specialist-{tier}" not in head or f"effort: {tier}" not in head:
            print(f"  FAIL {tier}: frontmatter mismatch")
            ok = False
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
