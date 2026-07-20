"""
Transaction cost model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TransactionCost:
    commission: float
    exchange_fee: float
    slippage: float
    spread: float