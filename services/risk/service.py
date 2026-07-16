"""
Pre-trade risk service.
"""

from __future__ import annotations

from typing import Optional

from .engine import RiskEngine
from .mapper import RiskRequestMapper
from .registry import default_rules
from .validators import ensure_approved


class PreTradeRiskService:
    def __init__(
        self,
        engine: Optional[RiskEngine] = None,
    ):
        self.engine = engine or RiskEngine(
            default_rules()
        )

    def evaluate(
        self,
        order,
    ):
        request = RiskRequestMapper.from_order(
            order
        )

        result = self.engine.evaluate(
            request
        )

        ensure_approved(result)

        return result