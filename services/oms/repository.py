from typing import Dict, List, Optional

from .models import Order


class OrderRepository:
    def __init__(self) -> None:
        self._orders: Dict[str, Order] = {}

    def save(self, order: Order) -> None:
        self._orders[order.order_id] = order

    def get(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    def get_by_symbol(self, symbol: str) -> List[Order]:
        return [order for order in self._orders.values() if order.symbol == symbol]

    def get_all(self) -> List[Order]:
        return list(self._orders.values())

    def delete(self, order_id: str) -> None:
        if order_id in self._orders:
            del self._orders[order_id]