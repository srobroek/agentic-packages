"""Starforge CLI assembler — prints a framed ASCII star chart.

Usage
-----
    python3 starforge.py [--width W] [--height H] [--density D] [--seed S]

Combines starfield.render_starfield and constellations.name_constellation
(both expected in the same directory) to produce a unicode-boxed star chart
with a constellation title.
"""

import argparse
import sys
import os

# Ensure the directory containing this script is on the path so that
# starfield and constellations can be imported as siblings.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from starfield import render_starfield
from constellations import name_constellation


def _build_chart(width: int, height: int, density: float, seed: int) -> str:
    """Return the full framed star chart as a string.

    Layout (inner_width = width):
        ╔═══…═══╗
        ║ <title centred> ║
        ╠═══…═══╣
        ║ <starfield row> ║
        …
        ╚═══…═══╝
    """
    title = name_constellation(seed)
    field = render_starfield(width=width, height=height, density=density, seed=seed)
    field_rows = field.split("\n")

    # Inner content width: max of starfield width and title width (with 1-space padding each side).
    inner = max(width, len(title) + 2)

    top    = "╔" + "═" * inner + "╗"
    mid    = "╠" + "═" * inner + "╣"
    bottom = "╚" + "═" * inner + "╝"

    # Title row: centred within inner, padded with spaces.
    title_padded = title.center(inner)
    title_row = "║" + title_padded + "║"

    lines = [top, title_row, mid]
    for row in field_rows:
        # Pad or truncate the starfield row to exactly inner width.
        padded = row.ljust(inner)[:inner]
        lines.append("║" + padded + "║")
    lines.append(bottom)

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print a framed ASCII star chart.",
    )
    parser.add_argument("--width",   type=int,   default=60,   help="Starfield width in columns (default: 60)")
    parser.add_argument("--height",  type=int,   default=20,   help="Starfield height in rows (default: 20)")
    parser.add_argument("--density", type=float, default=0.08, help="Star density fraction 0–1 (default: 0.08)")
    parser.add_argument("--seed",    type=int,   default=0,    help="RNG seed for deterministic output (default: 0)")
    args = parser.parse_args()

    print(_build_chart(
        width=args.width,
        height=args.height,
        density=args.density,
        seed=args.seed,
    ))


if __name__ == "__main__":
    main()
