from datetime import datetime
from typing import List, Optional

from services.reconciliation.models.difference import (
    CashDifference,
    OrderDifference,
    PositionDifference,
    TradeDifference,
)
from services.reconciliation.repair.repair_engine import RepairEngine


class RepairTask:
    def __init__(self, repair_engine: RepairEngine) -> None:
        self.repair_engine = repair_engine
        self.task_id: str = ""
        self.status: str = "PENDING"
        self.created_at: datetime = datetime.utcnow()
        self.completed_at: Optional[datetime] = None

    def execute(
        self,
        position_diffs: List[PositionDifference],
        cash_diffs: List[CashDifference],
        trade_diffs: List[TradeDifference],
        order_diffs: List[OrderDifference],
    ) -> None:
        self.status = "IN_PROGRESS"

        for diff in position_diffs:
            self.repair_engine.repair_position(diff)

        for diff in cash_diffs:
            self.repair_engine.repair_cash(diff)

        for diff in trade_diffs:
            self.repair_engine.repair_trade(diff)

        for diff in order_diffs:
            self.repair_engine.repair_order(diff)

        self.status = "COMPLETED"
        self.completed_at = datetime.utcnow()
