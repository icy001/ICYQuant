"""Sequential, date-prefixed identifier generation."""

from __future__ import annotations

from datetime import datetime, timezone


class IdGenerator:
    """Generate sequential identifiers.

    Format: ``{prefix}-{YYYYMMDD}-{sequence:06d}``

    Example: ``REC-20260814-000001`` or ``REPAIR-20260814-000001``.
    The sequence restarts for each calendar day.
    """

    def __init__(self, prefix: str) -> None:
        self._prefix = prefix
        self._sequences: dict[str, int] = {}

    def generate(self, now: datetime | None = None) -> str:
        now = now or datetime.now(timezone.utc)
        day = now.strftime("%Y%m%d")
        key = f"{self._prefix}:{day}"
        sequence = self._sequences.get(key, 0) + 1
        self._sequences[key] = sequence
        return f"{self._prefix}-{day}-{sequence:06d}"
