"""
Client order identifier.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClientOrderId:
    value: str

    def __post_init__(self):
        if not self.value:
            raise ValueError("client_order_id cannot be empty")

    def __str__(self):
        return self.value