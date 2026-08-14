from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .repair import (
    RepairActionType,
    RepairStatus,
)


@dataclass(frozen=True)
class RepairRecord:
    repair_id: str
    reconciliation_id: str
    action: RepairActionType
    status: RepairStatus

    reason: str

    before_quantity: Decimal | None
    before_average_price: Decimal | None
    before_realized_pnl: Decimal | None

    after_quantity: Decimal | None
    after_average_price: Decimal | None
    after_realized_pnl: Decimal | None

    attempt: int
    created_at: datetime
    completed_at: datetime | None
