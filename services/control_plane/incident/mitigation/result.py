"""
MitigationResult — the outcome of one control action execution (spec section 12).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID


@dataclass
class MitigationResult:

    action_id: UUID

    success: bool

    message: str = ""

    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    completed_at: datetime | None = None

    external_reference: str | None = None
