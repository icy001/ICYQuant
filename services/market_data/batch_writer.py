"""
Batch writer.
"""

from __future__ import annotations

from .quote import Quote


class BatchWriter:
    def __init__(self):
        self._buffer: list[Quote] = []

    def append(
        self,
        quote: Quote,
    ) -> None:
        self._buffer.append(quote)

    def flush(self) -> list[Quote]:
        batch = list(self._buffer)
        self._buffer.clear()
        return batch