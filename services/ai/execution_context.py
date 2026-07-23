"""
Execution intelligence context.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionContext:

    order_id: str

    symbol: str

    quantity: float

    side: str

    market_snapshot: dict