"""Starfield generator — renders a multi-line ASCII starfield.

Public API
----------
render_starfield(width, height, density, seed) -> str
    Returns a ``height``-row by ``width``-column ASCII field of stars.
    density in [0, 1] controls star coverage fraction.
    seed makes the output deterministic.
"""

import random

# Star characters weighted toward dim glyphs.
_STARS = (
    (".", 40),
    ("·", 30),
    ("*", 15),
    ("+", 8),
    ("✧", 4),
    ("✦", 3),
)

# Build weighted population for random.choices
_POPULATION, _WEIGHTS = zip(*_STARS)


def render_starfield(width: int, height: int, density: float, seed: int) -> str:
    """Return a multi-line ASCII starfield.

    Parameters
    ----------
    width:   columns in the output grid
    height:  rows in the output grid
    density: fraction of cells that are stars, clamped to [0, 1]
    seed:    RNG seed for deterministic output
    """
    density = max(0.0, min(1.0, density))
    rng = random.Random(seed)

    total_cells = width * height
    star_count = round(total_cells * density)

    # Choose which cells are stars (sampling without replacement for even distribution)
    star_indices = set(rng.sample(range(total_cells), min(star_count, total_cells)))

    # Pick a glyph for every star cell
    star_glyphs = rng.choices(_POPULATION, weights=_WEIGHTS, k=len(star_indices))
    glyph_map = {idx: g for idx, g in zip(sorted(star_indices), star_glyphs)}

    rows: list[str] = []
    for row in range(height):
        row_chars: list[str] = []
        for col in range(width):
            cell_idx = row * width + col
            row_chars.append(glyph_map.get(cell_idx, " "))
        rows.append("".join(row_chars))

    return "\n".join(rows)


if __name__ == "__main__":
    print(render_starfield(width=80, height=20, density=0.08, seed=42))
