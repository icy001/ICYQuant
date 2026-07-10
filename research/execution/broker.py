from typing import Dict, Optional

from .order import Order, OrderStatus
from .fill import Fill
from .execution_report import ExecutionReport
from .matcher import MatchingEngine
from research.data.snapshot import MarketSnapshot


class SimulatedBroker:

    def __init__(
        self,
        commission_rate: float = 0.005,
        spread: float = 0.01,
        slippage_rate: float = 0.0005
    ):
        self.matcher = MatchingEngine(commission_rate, spread, slippage_rate)
        self._orders: Dict[str, Order] = {}
        self._fills: Dict[str, Fill] = {}

    def execute(self, order: Order, market_snapshot: MarketSnapshot) -> ExecutionReport:
        order.status = OrderStatus.ACCEPTED
        self._orders[str(order.order_id)] = order

        bar = market_snapshot.get(order.symbol)
        if bar is None:
            order.status = OrderStatus.REJECTED
            return ExecutionReport(
                order=order,
                fills=[],
                message=f"Symbol {order.symbol} not found in market data"
            )

        market_price = bar.close

        fill = self.matcher.match(order, market_price)

        if fill is None:
            order.status = OrderStatus.REJECTED
            return ExecutionReport(
                order=order,
                fills=[],
                message="Order could not be matched"
            )

        order.filled_quantity = fill.quantity
        order.status = OrderStatus.FILLED

        self._fills[str(fill.fill_id)] = fill

        return ExecutionReport(
            order=order,
            fills=[fill],
            message="Order filled successfully"
        )

    def get_order(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    def get_all_orders(self) -> Dict[str, Order]:
        return dict(self._orders)

    def get_all_fills(self) -> Dict[str, Fill]:
        return dict(self._fills)