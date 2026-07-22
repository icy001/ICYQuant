"""
Virtual order model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class VirtualOrder:

    order_id: str

    symbol: str

    side: str

    quantity: float

    price: float