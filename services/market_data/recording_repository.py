"""
Recording repository abstraction.
"""

from __future__ import annotations

from typing import Protocol

from .quote import Quote


class RecordingRepository(Protocol):
    async def append_quote(
        self,
        quote: Quote,
    ) -> None:
        ...