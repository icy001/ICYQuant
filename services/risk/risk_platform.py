"""
Enterprise Risk Platform.
"""

from dataclasses import dataclass


@dataclass
class RiskPlatform:

    pre_trade: object

    margin: object

    leverage: object

    exposure: object

    concentration: object

    liquidity: object

    volatility: object

    stress: object

    scenario: object

    aggregation: object

    monitoring: object

    reporting: object