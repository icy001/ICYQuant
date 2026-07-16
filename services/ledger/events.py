"""
Ledger domain events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID


@dataclass(frozen=True)
class LedgerPosted:
    journal_id: UUID
    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )