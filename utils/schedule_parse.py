"""
Parse schedule text lines that combine an ordinarium mass type and a Bapa Kami version,
e.g. ``Sabtu (Misa Raya 2 + PS 405)``.
"""

from __future__ import annotations

from typing import Optional

from config.constants import BAPA_KAMI_VERSIONS, ORDINARIUM_TYPES

from utils.string import (
    collapse_space_before_trailing_digits,
    extract_plus_delimited_pair,
    match_canonical_choice,
)


def parse_ordinarium_type(schedule_text: str) -> Optional[str]:
    """
    Extract the ordinarium mass type from a schedule string and return it in slug form.

    Example: ``Sabtu (Misa Raya 2 + PS 405)`` -> ``misa raya2`` (space before the trailing
    number is removed; spelling follows ``ORDINARIUM_TYPES``).
    """
    pair = extract_plus_delimited_pair(schedule_text)
    if pair is None:
        return None
    left, _ = pair
    canonical = match_canonical_choice(left, ORDINARIUM_TYPES)
    if canonical is None:
        return None
    return collapse_space_before_trailing_digits(canonical)


def parse_bapa_kami_version(schedule_text: str) -> Optional[str]:
    """
    Extract the Bapa Kami version from a schedule string.

    Example: ``Sabtu (Misa Raya 2 + PS 405)`` -> ``ps 405`` (matches ``BAPA_KAMI_VERSIONS``).
    """
    pair = extract_plus_delimited_pair(schedule_text)
    if pair is None:
        return None
    _, right = pair
    return match_canonical_choice(right, BAPA_KAMI_VERSIONS)
