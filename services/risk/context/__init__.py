"""
Risk decision context package.

Provides the decision context for a single risk evaluation
(``RiskDecisionContext``) plus a factory that builds it from an approved
signal and account/position snapshots.

Backward-compatible exports:

- ``RiskContext`` (legacy flat-module symbol, kept for compatibility)
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..account import AccountRiskInfo
from .context_factory import RiskDecisionContextFactory
from .decision_context import RiskDecisionContext


@dataclass
class RiskContext:
    account_id: str
    symbol: str
    current_position: Decimal
    account: AccountRiskInfo


__all__ = [
    "RiskContext",
    "RiskDecisionContext",
    "RiskDecisionContextFactory",
]
