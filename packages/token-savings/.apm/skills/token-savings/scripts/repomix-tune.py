#!/usr/bin/env python3
"""Measure repomix tuning options against a real repository, and print the winner.

Every claim in this package about repomix came from running this sweep. It exists
so the next person does not have to trust the numbers: point it at a repository
and it re-derives them, on whatever repomix version is installed.

The finding it was built to establish, and which it will re-check: PATH FILTERING
is the only real lever. Every content-transformation knob is negligible, lossy in
a way that matters, or actively counterproductive. `--style json` and
`--parsable-style` both make the pack ~10% BIGGER.

Usage:
  repomix-tune.py --repo <path>              # full sweep, markdown table
  repomix-tune.py --repo <path> --json       # machine-readable
  repomix-tune.py --repo <path> --top 15     # what is eating the pack
  repomix-tune.py --repo <path> --quick      # skip the slow full-pack variants
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TIMEOUT = 900

# Shipped defaults, kept here as the single source of truth so the sweep measures
# what the hook actually runs. `repomix-map.py` holds the same lists; a drift
# between them shows up as the "shipped" row not matching the best result.
INCLUDES = ",".join(
    (
        "**/*.rs", "**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx", "**/*.py",
        "**/*.go", "**/*.sh", "**/*.toml", "**/*.sql", "**/*.md",
        "**/*.yaml", "**/*.yml",
    )
)

IGNORES = ",".join(
    (
        "**/CHANGELOG.md",
        "**/*.lock", "**/*.lock.yaml", "**/*.lock.json",
        "**/pnpm-lock.yaml", "**/Cargo.lock", "**/uv.lock",
        "**/package-lock.json", "**/poetry.lock",
        "**/.claude-plugin/marketplace.json", "**/.agents/plugins/marketplace.json",
        "**/assets/seed/**", "**/fixtures/**", "**/testdata/**", "**/*.snap",
        "**/messages/*.json", "**/locales/**", "**/i18n/**",
        "**/bindings/index.ts", "**/*.generated.*", "**/generated/**",
        "**/.agents/skills/**", "**/.specify/extensions/**",
        "**/graphify-out/**", "**/.serena/**", "**/repomix.xml",
        "**/local-*.txt", "**/*.min.js", "**/*.min.css", "**/*.map",
    )
)

CODE_ONLY = ",".join(
    ("**/*.rs", "**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx", "**/*.py", "**/*.go", "**/*.sh")
)

# (label, extra args, note). Ordered so the path-filtering rows come first.
VARIANTS: tuple[tuple[str, list[str], str], ...] = (
    ("default", [], "no tuning"),
    ("--ignore only", ["--ignore", IGNORES], "blocklist alone"),
    ("--include code+prose", ["--include", INCLUDES], "allowlist alone"),
    ("--include CODE only", ["--include", CODE_ONLY], "discards every README and ADR"),
    ("--include + --ignore", ["--include", INCLUDES, "--ignore", IGNORES], "SHIPPED"),
    ("--compress", ["--compress"], "regresses on comment-dense files"),
    ("--remove-comments", ["--remove-comments"], "strips // and #, keeps Rust ///"),
    ("--remove-empty-lines", ["--remove-empty-lines"], ""),
    ("--no-file-summary", ["--no-file-summary"], ""),
    ("--no-directory-structure", ["--no-directory-structure"], ""),
    ("--truncate-base64", ["--truncate-base64"], ""),
    ("--parsable-style", ["--parsable-style"], "default xml is NOT valid XML"),
    ("--style markdown", ["--style", "markdown"], ""),
    ("--style plain", ["--style", "plain"], ""),
    ("--style json", ["--style", "json"], ""),
    ("--no-files (the map)", ["--no-files", "--no-file-summary"], "tree only, no contents"),
)

QUICK_LABELS = frozenset(
    {"default", "--ignore only", "--include + --ignore", "--no-files (the map)"}
)


def pack(repo: Path, extra: list[str], out: Path) -> dict:
    """Run one repomix variant, returning its reported totals and wall time."""
    import time

    command = ["repomix", "--output", str(out)]
    # `--style` may be supplied by the variant; default to xml when it is not.
    if "--style" not in extra:
        command += ["--style", "xml"]
    command += extra + [str(repo)]

    started = time.monotonic()
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.SubprocessError as exc:
        return {"error": type(exc).__name__}
    elapsed = time.monotonic() - started

    tokens = re.search(r"Total Tokens:\s*([\d,]+)", result.stdout)
    files = re.search(r"Total Files:\s*([\d,]+)", result.stdout)
    if not tokens:
        return {"error": (result.stderr or result.stdout or "no total reported")[:200]}
    return {
        "tokens": int(tokens.group(1).replace(",", "")),
        "files": int(files.group(1).replace(",", "")) if files else None,
        "bytes": out.stat().st_size if out.exists() else None,
        "seconds": round(elapsed, 2),
    }


def top_files(repo: Path, count: int) -> list[str]:
    """What is actually eating the pack. Usually not code."""
    result = subprocess.run(
        ["repomix", "--style", "xml", "--top-files-len", str(count), "--output", "/dev/null", str(repo)],
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
    )
    rows = []
    for line in result.stdout.splitlines():
        match = re.match(r"\s*\d+\.\s+(\S+)\s+\(([\d,]+) tokens.*?([\d.]+)%\)", line)
        if match:
            rows.append(f"{match.group(2):>12} tokens  {match.group(3):>5}%  {match.group(1)}")
    return rows


def valid_xml(path: Path) -> bool | None:
    """Does the pack actually parse as XML? The default style does not."""
    import xml.etree.ElementTree as ET

    if not path.exists():
        return None
    try:
        ET.parse(path)
        return True
    except Exception:  # noqa: BLE001 - any parse failure is the answer
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--top", type=int, default=0, help="also list the N biggest files")
    parser.add_argument("--quick", action="store_true", help="only the path-filtering variants")
    args = parser.parse_args(argv)

    if shutil.which("repomix") is None:
        print("repomix is not installed", file=sys.stderr)
        return 1
    repo = Path(args.repo).expanduser().resolve()
    if not (repo / ".git").exists():
        print(f"not a git repository: {repo}", file=sys.stderr)
        return 1

    version = subprocess.run(["repomix", "--version"], capture_output=True, text=True).stdout.strip()

    results = {}
    xml_validity = {}
    with tempfile.TemporaryDirectory(prefix="repomix-tune-") as scratch:
        for label, extra, note in VARIANTS:
            if args.quick and label not in QUICK_LABELS:
                continue
            out = Path(scratch) / f"{abs(hash(label))}.out"
            results[label] = {**pack(repo, extra, out), "note": note}
            if label in ("default", "--parsable-style"):
                xml_validity[label] = valid_xml(out)

    baseline = results.get("default", {}).get("tokens")

    if args.as_json:
        print(json.dumps({
            "repo": str(repo), "repomix": version,
            "results": results, "xml_valid": xml_validity,
            "top_files": top_files(repo, args.top) if args.top else [],
        }, indent=2))
        return 0

    print(f"# repomix tuning: {repo.name} (repomix {version})\n")
    print("| Variant | Tokens | Files | Time | vs default | Note |")
    print("| --- | --- | --- | --- | --- | --- |")
    for label, data in results.items():
        if "error" in data:
            print(f"| `{label}` | ERROR | | | | {data['error'][:40]} |")
            continue
        delta = ""
        if baseline and label != "default":
            change = (1 - data["tokens"] / baseline) * 100
            delta = f"**{change:+.1f}%**" if abs(change) >= 5 else f"{change:+.1f}%"
        print(
            f"| `{label}` | {data['tokens']:,} | {data.get('files') or ''} "
            f"| {data['seconds']}s | {delta} | {data['note']} |"
        )

    if xml_validity:
        print("\n## XML validity\n")
        for label, ok in xml_validity.items():
            print(f"- `{label}`: {'parses as XML' if ok else 'does NOT parse as XML'}")
        if xml_validity.get("default") is False:
            print(
                "\n  The default `--style xml` is a text format with XML-shaped delimiters,\n"
                "  not XML. Use `--parsable-style` only when a real parser reads the output;\n"
                "  it costs ~10% and renders every quote and generic as an entity."
            )

    positive = [
        (label, (1 - d["tokens"] / baseline) * 100)
        for label, d in results.items()
        if baseline and "error" not in d and label != "default"
    ]
    winners = sorted((p for p in positive if p[1] > 0), key=lambda p: -p[1])[:3]
    losers = [p for p in positive if p[1] < -1]
    if winners:
        print("\n## Biggest reductions\n")
        for label, change in winners:
            print(f"- `{label}`: {change:.1f}%")
    if losers:
        print("\n## Made it BIGGER\n")
        for label, change in losers:
            print(f"- `{label}`: {change:.1f}%")

    if args.top:
        print(f"\n## Top {args.top} files by token count\n")
        print("Usually not code. A single seed fixture was 14.4% of one pack.\n")
        for row in top_files(repo, args.top):
            print(f"    {row}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
