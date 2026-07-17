"""
Strategy risk budget model.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class RiskBudget:
    account_equity: Decimal
    max_risk_percent: Decimal
    max_position_value: Decimal