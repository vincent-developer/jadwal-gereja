"""
Parse schedule text lines that combine an ordinarium mass type and a Bapa Kami version,
e.g. ``Sabtu (Misa Raya 2 + PS 405)``.
"""

from __future__ import annotations

from typing import Optional

from config.constants import BAPA_KAMI_VERSIONS, ORDINARIUM_TYPES

from utils.string import extract_plus_delimited_pair, match_canonical_choice


def parse_ordinarium_type(schedule_text: str) -> Optional[str]:
    """
    Extract the ordinarium mass type from a schedule string.

    Returns the canonical label from ``ORDINARIUM_TYPES`` (same spelling and spacing,
    e.g. ``misa kita 2``, ``misa raya 2``).
    """
    pair = extract_plus_delimited_pair(schedule_text)
    if pair is None:
        return None
    left, _ = pair
    return match_canonical_choice(left, ORDINARIUM_TYPES)


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
