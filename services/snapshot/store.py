"""
Snapshot store abstraction.
"""

from __future__ import annotations


from typing import Protocol


from uuid import UUID


from .model import PortfolioSnapshot


class SnapshotStore(Protocol):
    def save(
        self,
        snapshot: PortfolioSnapshot,
    ) -> None:
        ...

    def latest(
        self,
    ) -> PortfolioSnapshot | None:
        ...

    def get(
        self,
        snapshot_id: UUID,
    ) -> PortfolioSnapshot | None:
        ...