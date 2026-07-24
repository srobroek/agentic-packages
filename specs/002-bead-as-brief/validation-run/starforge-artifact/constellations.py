"""Deterministic whimsical constellation name generator."""

import hashlib

_ARTICLES = [
    "The",
    "The Great",
    "The Lesser",
    "The Wandering",
    "The Hidden",
    "The Ancient",
    "The Forgotten",
    "The Eternal",
    "The Crimson",
    "The Silver",
]

_ADJECTIVES = [
    "",
    "Minor",
    "Major",
    "Borealis",
    "Australis",
    "Obscura",
    "Celestis",
    "Luminosa",
    "Infinita",
    "Vasta",
]

_NOUNS = [
    "Teapot",
    "Anvil",
    "Compass",
    "Kettle",
    "Lantern",
    "Sextant",
    "Hourglass",
    "Bellows",
    "Cartographer",
    "Mapmaker",
    "Wanderer",
    "Dreamer",
    "Shepherd",
    "Navigator",
    "Clockmaker",
    "Candlestick",
    "Spindle",
    "Inkwell",
    "Locket",
    "Monocle",
    "Serpens",
    "Piscis",
    "Ursae",
    "Corvus",
    "Lacerta",
]


def _pick(seed_int: int, collection: list, offset: int) -> str:
    """Pick deterministically from a list using the seed and an offset."""
    index = (seed_int + offset * 31337) % len(collection)
    return collection[index]


def _seed_to_int(seed: int | str) -> int:
    """Convert any seed to a stable integer."""
    if isinstance(seed, int):
        return seed
    digest = hashlib.sha256(str(seed).encode()).hexdigest()
    return int(digest, 16)


def name_constellation(seed: int | str) -> str:
    """Return a deterministic whimsical constellation name for the given seed.

    Args:
        seed: Integer or string used as the deterministic source.

    Returns:
        A fake constellation name such as 'The Wandering Teapot' or
        'Serpens Minor Borealis'.
    """
    s = _seed_to_int(seed)

    # Two independent styles: article-led or noun-first (Latin-style)
    style = s % 3

    if style == 0:
        # "The Wandering Teapot"
        article = _pick(s, _ARTICLES, 0)
        noun = _pick(s, _NOUNS, 1)
        return f"{article} {noun}"

    elif style == 1:
        # "Serpens Minor Borealis"
        noun = _pick(s, _NOUNS, 2)
        adj1 = _pick(s, _ADJECTIVES, 3)
        adj2 = _pick(s, _ADJECTIVES, 4)
        parts = [noun]
        if adj1:
            parts.append(adj1)
        if adj2 and adj2 != adj1:
            parts.append(adj2)
        return " ".join(parts)

    else:
        # "The Hidden Clockmaker Australis"
        article = _pick(s, _ARTICLES, 5)
        noun = _pick(s, _NOUNS, 6)
        adj = _pick(s, _ADJECTIVES, 7)
        parts = [article, noun]
        if adj:
            parts.append(adj)
        return " ".join(parts)


if __name__ == "__main__":
    print("Five whimsical constellation names:")
    for i in range(5):
        print(f"  seed={i}: {name_constellation(i)}")
