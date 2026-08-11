"""
Capital Adequacy Engine — Institutional capital assessment and regulatory compliance.

Evaluates capital requirements, ratios, and buffers against regulatory
frameworks and internal risk limits.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class CapitalAssessment:
    """Result of capital adequacy assessment."""
    available_capital: float
    required_capital: float
    capital_ratio: float
    capital_surplus: float
    tier1_capital: float = 0.0
    tier2_capital: float = 0.0
    risk_weighted_assets: float = 0.0
    leverage_ratio: float = 0.0
    regulatory_status: str = "compliant"
    buffer_level: str = "adequate"
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class CapitalAdequacyEngine:
    """
    Capital adequacy assessment engine.

    Evaluates:
    - Capital requirements based on portfolio risk
    - Regulatory ratios (CAR, Tier 1, Leverage)
    - Capital buffers and stress testing
    - Surplus/deficit analysis
    - Compliance status

    Usage::

        engine = CapitalAdequacyEngine()
        await engine.initialize()
        result = await engine.assess(portfolio_data)
    """

    # Regulatory minimums
    MIN_CAR_RATIO = 0.08  # 8%
    MIN_TIER1_RATIO = 0.06  # 6%
    MIN_LEVERAGE_RATIO = 0.03  # 3%
    CONSERVATION_BUFFER = 0.025  # 2.5%

    def __init__(self) -> None:
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the capital adequacy engine."""
        self._initialized = True

    async def assess(self, portfolio_data: dict[str, Any]) -> dict[str, Any]:
        """
        Assess capital adequacy.

        Parameters
        ----------
        portfolio_data : dict
            Portfolio with total_value, positions, VaR, stress results.

        Returns
        -------
        dict
            Capital adequacy assessment.
        """
        total_value = portfolio_data.get("total_value", 1_000_000)
        positions = portfolio_data.get("positions", [])
        var_data = portfolio_data.get("var_results", {})
        stress_data = portfolio_data.get("stress_testing", {})

        # Available capital (assumed from portfolio equity)
        available_capital = total_value * 0.15  # Assume 15% capital base

        # Risk-weighted assets (RWA) calculation
        rwa = self._compute_rwa(positions, total_value, var_data)

        # Required capital
        required_capital = rwa * self.MIN_CAR_RATIO

        # Tier 1 and Tier 2
        tier1 = available_capital * 0.70
        tier2 = available_capital * 0.30

        # Ratios
        car_ratio = available_capital / rwa if rwa > 0 else 1.0
        tier1_ratio = tier1 / rwa if rwa > 0 else 1.0
        leverage_ratio = tier1 / total_value if total_value > 0 else 0

        # Capital surplus
        surplus = available_capital - required_capital
        surplus_pct = (surplus / required_capital * 100) if required_capital > 0 else 0

        # Regulatory status
        warnings: list[str] = []
        compliant = True

        if car_ratio < self.MIN_CAR_RATIO + self.CONSERVATION_BUFFER:
            warnings.append(f"CAR ({car_ratio:.2%}) below minimum + buffer ({self.MIN_CAR_RATIO + self.CONSERVATION_BUFFER:.2%})")
            compliant = False
        if tier1_ratio < self.MIN_TIER1_RATIO:
            warnings.append(f"Tier 1 ratio ({tier1_ratio:.2%}) below minimum ({self.MIN_TIER1_RATIO:.2%})")
            compliant = False
        if leverage_ratio < self.MIN_LEVERAGE_RATIO:
            warnings.append(f"Leverage ratio ({leverage_ratio:.2%}) below minimum ({self.MIN_LEVERAGE_RATIO:.2%})")
            compliant = False

        # Buffer level
        buffer = car_ratio - self.MIN_CAR_RATIO
        if buffer > 0.05:
            buffer_level = "strong"
        elif buffer > 0.025:
            buffer_level = "adequate"
        elif buffer > 0:
            buffer_level = "thin"
        else:
            buffer_level = "deficient"

        # Stress-adjusted capital
        worst_loss = stress_data.get("worst_case_loss_pct", 0) / 100
        stressed_capital = available_capital * (1 - abs(worst_loss))
        stressed_ratio = stressed_capital / rwa if rwa > 0 else 0

        return {
            "available_capital": round(available_capital, 2),
            "required_capital": round(required_capital, 2),
            "capital_surplus": round(surplus, 2),
            "capital_surplus_pct": round(surplus_pct, 1),
            "risk_weighted_assets": round(rwa, 2),
            "tier1_capital": round(tier1, 2),
            "tier2_capital": round(tier2, 2),
            "ratios": {
                "car": round(car_ratio, 4),
                "car_pct": round(car_ratio * 100, 1),
                "tier1_ratio": round(tier1_ratio, 4),
                "tier1_ratio_pct": round(tier1_ratio * 100, 1),
                "leverage_ratio": round(leverage_ratio, 4),
                "leverage_ratio_pct": round(leverage_ratio * 100, 1),
                "stressed_car": round(stressed_ratio, 4),
                "stressed_car_pct": round(stressed_ratio * 100, 1),
            },
            "regulatory_status": "compliant" if compliant else "breach",
            "buffer_level": buffer_level,
            "warnings": warnings,
            "minimums": {
                "car_min_pct": self.MIN_CAR_RATIO * 100,
                "tier1_min_pct": self.MIN_TIER1_RATIO * 100,
                "leverage_min_pct": self.MIN_LEVERAGE_RATIO * 100,
                "conservation_buffer_pct": self.CONSERVATION_BUFFER * 100,
            },
        }

    def _compute_rwa(
        self,
        positions: list[dict],
        total_value: float,
        var_data: dict[str, Any],
    ) -> float:
        """Compute Risk-Weighted Assets."""
        # Risk weights by asset class
        risk_weights = {
            "equity": 1.0,
            "bond": 0.2,
            "government_bond": 0.0,
            "corporate_bond": 0.5,
            "high_yield": 1.5,
            "commodity": 1.0,
            "forex": 0.5,
            "real_estate": 1.0,
            "derivative": 1.5,
            "crypto": 4.0,
            "cash": 0.0,
        }

        rwa = 0.0
        for pos in positions:
            if not isinstance(pos, dict):
                continue
            market_value = abs(pos.get("market_value", 0))
            asset_class = pos.get("asset_class", "equity").lower()
            weight = risk_weights.get(asset_class, 1.0)
            rwa += market_value * weight

        # Add VaR-based add-on
        var_entries = var_data.get("var_entries", [])
        if var_entries:
            max_var = max(
                abs(e.get("var_value", 0)) for e in var_entries
            )
            rwa += max_var * 12.5  # VaR × multiplier

        return rwa
