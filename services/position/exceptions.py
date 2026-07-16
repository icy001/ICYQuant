"""
Position exceptions.
"""

from __future__ import annotations


class PositionNotFoundError(
    LookupError,
):
    """Position not found."""