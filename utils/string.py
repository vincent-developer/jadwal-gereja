import re
from typing import Optional

# ---------- Label normalization ----------
def normalize_label(text: str) -> str:
    """Lowercase, strip, and collapse consecutive whitespace to a single space."""
    return re.sub(r"\s+", " ", text.strip().lower())


# ---------- Parentheses & delimiters ----------
def extract_parenthetical(text: str) -> Optional[str]:
    """Return the inner text of the first ``(...)`` group, or ``None`` if there is none."""
    m = re.search(r"\(([^)]+)\)", text)
    if not m:
        return None
    inner = m.group(1).strip()
    return inner or None


def split_plus_pair(text: str) -> Optional[tuple[str, str]]:
    """Split on the first ``+`` and return stripped left and right, or ``None`` if invalid."""
    if "+" not in text:
        return None
    left, right = text.split("+", 1)
    left, right = left.strip(), right.strip()
    if not left or not right:
        return None
    return left, right


def extract_plus_delimited_pair(text: str) -> Optional[tuple[str, str]]:
    """
    Parse ``left + right`` from a line, preferring the segment inside the first ``(...)``.

    Examples: ``Sabtu (A + B)`` uses ``A + B``; ``A + B`` uses the whole stripped string.
    """
    raw = text.strip()
    inner = extract_parenthetical(raw)
    segment = inner if inner is not None else raw
    return split_plus_pair(segment)


# ---------- Matching ----------
def match_canonical_choice(candidate: str, choices: list[str]) -> Optional[str]:
    """
    Return the entry from ``choices`` that best matches ``candidate`` (case- and
    spacing-insensitive): exact normalized match, else longest choice substring contained
    in the candidate, else shortest choice that contains the candidate.
    """
    n = normalize_label(candidate)
    if not n:
        return None
    for c in choices:
        if normalize_label(c) == n:
            return c
    contained = [c for c in choices if normalize_label(c) in n]
    if contained:
        return max(contained, key=lambda x: len(normalize_label(x)))
    wrapping = [c for c in choices if n in normalize_label(c)]
    if wrapping:
        return min(wrapping, key=lambda x: len(normalize_label(x)))
    return None


# ---------- Slug-style tweaks ----------
def collapse_space_before_trailing_digits(text: str) -> str:
    """Remove the space before a trailing digit run, e.g. ``misa raya 2`` -> ``misa raya2``."""
    return re.sub(r" (\d+)$", r"\1", text.strip().lower())
