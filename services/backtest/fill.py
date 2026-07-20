"""
Fill model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Fill:
    order_id: str
    quantity: float
    price: float