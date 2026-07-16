"""
Risk rule registry.
"""

from __future__ import annotations

from decimal import Decimal

from .rules.exposure_limit import ExposureLimitRule
from .rules.margin_rule import MarginRule
from .rules.max_order_size import MaxOrderSizeRule
from .rules.position_limit import PositionLimitRule


def default_rules():
    return [
        MaxOrderSizeRule(
            limit=Decimal("100000"),
        ),
        PositionLimitRule(
            limit=Decimal("10000"),
        ),
        ExposureLimitRule(
            limit=Decimal("1000000"),
        ),
        MarginRule(
            margin_rate=Decimal("0.1"),
        ),
    ]