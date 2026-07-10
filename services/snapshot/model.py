"""
Snapshot domain model.

A snapshot stores a serialized
projection state at a point in time.
"""

from __future__ import annotations


from dataclasses import (
    dataclass,
)


from datetime import datetime


from uuid import UUID


@dataclass(
    frozen=True,
)
class PortfolioSnapshot:
    """
    Portfolio state checkpoint.
    """

    snapshot_id: UUID

    event_id: UUID

    created_at: datetime | None

    state: dict