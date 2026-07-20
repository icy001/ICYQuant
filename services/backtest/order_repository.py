"""
Virtual order repository.
"""


class VirtualOrderRepository:
    def __init__(self):
        self._orders = {}

    def save(
        self,
        order,
    ):
        self._orders[order.id] = order

    def get(
        self,
        order_id,
    ):
        return self._orders.get(order_id)