from typing import Any, Dict

from services.reconciliation.models.difference import (
    CashDifference,
    OrderDifference,
    PositionDifference,
    TradeDifference,
)


class RepairEngine:
    def __init__(self) -> None:
        self.repair_history: list[Dict[str, Any]] = []

    def repair_position(self, difference: PositionDifference) -> Dict[str, Any]:
        repair_record = {
            "type": "POSITION_REPAIR",
            "symbol": difference.symbol,
            "difference": difference.difference,
            "action": "ADJUST",
        }
        self.repair_history.append(repair_record)
        return repair_record

    def repair_cash(self, difference: CashDifference) -> Dict[str, Any]:
        repair_record = {
            "type": "CASH_REPAIR",
            "user_id": difference.user_id,
            "difference": difference.difference,
            "action": "ADJUST",
        }
        self.repair_history.append(repair_record)
        return repair_record

    def repair_trade(self, difference: TradeDifference) -> Dict[str, Any]:
        repair_record = {
            "type": "TRADE_REPAIR",
            "trade_id": difference.trade_id,
            "difference_type": difference.difference_type,
            "action": "RECREATE"
            if difference.difference_type == "MISSING_IN_ACTUAL"
            else "DELETE",
        }
        self.repair_history.append(repair_record)
        return repair_record

    def repair_order(self, difference: OrderDifference) -> Dict[str, Any]:
        repair_record = {
            "type": "ORDER_REPAIR",
            "order_id": difference.order_id,
            "difference_type": difference.difference_type,
            "action": "UPDATE_STATUS",
        }
        self.repair_history.append(repair_record)
        return repair_record
