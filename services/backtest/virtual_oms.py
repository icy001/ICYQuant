"""
Virtual OMS.
"""

from .order_repository import VirtualOrderRepository


class VirtualOMS:
    def __init__(
        self,
        repository: VirtualOrderRepository,
    ):
        self.repository = repository

    def submit(
        self,
        order,
    ):
        self.repository.save(order)
        return order