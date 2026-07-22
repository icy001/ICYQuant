"""
Leverage rule model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LeverageRule:

    account_id: str

    max_leverage: float