"""
Shock Generator — Generate customizable market shocks for stress testing.

Creates single-factor, multi-factor, and correlated shock vectors
for application in stress testing and scenario analysis.
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ShockConfig:
    """Configuration for shock generation."""
    magnitude: float = -0.10  # base shock magnitude
    volatility_multiplier: float = 1.0
    correlation_structure: Optional[dict[str, dict[str, float]]] = None
    num_factors: int = 5
    seed: Optional[int] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ShockVector:
    """A vector of shocks to apply to multiple assets."""
    asset_shocks: dict[str, float]
    macro_shocks: dict[str, float] = field(default_factory=dict)
    description: str = ""
    total_impact_pct: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class ShockGenerator:
    """
    Generate customizable market shocks for stress testing.

    Supports:
    - Single-factor shocks (equity, rates, FX, etc.)
    - Multi-factor correlated shocks
    - Historical distribution sampling
    - Tail risk shock amplification
    - Custom shock matrices

    Usage::

        gen = ShockGenerator()
        await gen.initialize()
        shock = gen.generate_equity_shock(-0.30)
        multi_shock = gen.generate_correlated_shock(["equity", "bond", "fx"])
    """

    def __init__(self, seed: Optional[int] = None) -> None:
        self._seed = seed
        self._rng = random.Random(seed)
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the shock generator."""
        self._initialized = True

    # ---- Single-Factor Shocks ----

    def generate_equity_shock(self, magnitude: float = -0.20) -> ShockVector:
        """Generate an equity market shock."""
        return ShockVector(
            asset_shocks={"equity": magnitude},
            macro_shocks={"vix": abs(magnitude) * 2.0},
            description=f"Equity shock: {magnitude * 100:.1f}%",
            total_impact_pct=abs(magnitude) * 100,
        )

    def generate_rate_shock(self, bps_change: float = 100.0) -> ShockVector:
        """Generate an interest rate shock (in basis points)."""
        bond_shock = -bps_change / 10000 * 5  # approximate duration effect
        return ShockVector(
            asset_shocks={"bond": bond_shock, "equity": -bps_change / 10000},
            macro_shocks={"fed_rate_change": bps_change / 100},
            description=f"Rate shock: +{bps_change:.0f}bps",
            total_impact_pct=abs(bond_shock) * 100,
        )

    def generate_fx_shock(self, currency: str, magnitude: float = 0.10) -> ShockVector:
        """Generate a currency shock."""
        return ShockVector(
            asset_shocks={f"fx_{currency}": magnitude},
            macro_shocks={"fx_volatility": abs(magnitude) * 3},
            description=f"FX shock ({currency}): {magnitude * 100:.1f}%",
            total_impact_pct=abs(magnitude) * 100,
        )

    def generate_volatility_shock(self, multiplier: float = 3.0) -> ShockVector:
        """Generate a volatility spike shock."""
        equity_impact = -0.02 * multiplier
        return ShockVector(
            asset_shocks={"equity": equity_impact, "volatility_products": -0.10 * multiplier},
            macro_shocks={"vix": 30 * multiplier},
            description=f"Volatility spike: {multiplier:.1f}x",
            total_impact_pct=abs(equity_impact) * 100,
        )

    def generate_liquidity_shock(self, discount: float = 0.30) -> ShockVector:
        """Generate a liquidity crisis shock."""
        return ShockVector(
            asset_shocks={"*": -discount, "small_cap": -discount * 1.5},
            macro_shocks={"bid_ask_spread": discount * 10},
            description=f"Liquidity shock: {discount * 100:.0f}% discount",
            total_impact_pct=discount * 100,
        )

    def generate_credit_shock(self, spread_widening: float = 200.0) -> ShockVector:
        """Generate a credit spread shock (in basis points)."""
        impact = -spread_widening / 10000 * 3
        return ShockVector(
            asset_shocks={"corporate_bond": impact, "high_yield": impact * 2},
            macro_shocks={"credit_spread": spread_widening},
            description=f"Credit shock: +{spread_widening:.0f}bps",
            total_impact_pct=abs(impact) * 100,
        )

    # ---- Multi-Factor Correlated Shocks ----

    def generate_correlated_shock(
        self,
        assets: list[str],
        base_magnitude: float = -0.15,
        correlation: float = 0.7,
    ) -> ShockVector:
        """Generate correlated shocks across multiple assets."""
        shocks: dict[str, float] = {}
        common_factor = self._rng.gauss(0, 1)
        idiosyncratic_vol = math.sqrt(max(0, 1 - correlation ** 2))

        for asset in assets:
            idiosyncratic = self._rng.gauss(0, 1)
            shock = (
                base_magnitude * correlation * common_factor
                + base_magnitude * idiosyncratic_vol * idiosyncratic
            )
            shocks[asset] = shock

        avg_impact = sum(abs(s) for s in shocks.values()) / len(shocks) if shocks else 0

        return ShockVector(
            asset_shocks=shocks,
            macro_shocks={"correlation_regime": correlation},
            description=f"Correlated shock ({correlation:.1f}) across {len(assets)} assets",
            total_impact_pct=avg_impact * 100,
        )

    def generate_tail_shock(
        self,
        asset: str = "equity",
        sigma: float = 3.0,
        direction: str = "negative",
    ) -> ShockVector:
        """Generate a tail-event shock (N-sigma move)."""
        # Use inverse CDF of normal distribution
        if direction == "negative":
            z_score = -abs(sigma)
        elif direction == "positive":
            z_score = abs(sigma)
        else:
            z_score = self._rng.choice([-abs(sigma), abs(sigma)])

        magnitude = z_score * 0.02  # approximate daily vol
        magnitude = max(-1.0, min(1.0, magnitude))

        return ShockVector(
            asset_shocks={asset: magnitude},
            macro_shocks={"sigma_event": abs(sigma)},
            description=f"Tail shock ({direction} {sigma}σ): {asset} {magnitude * 100:.1f}%",
            total_impact_pct=abs(magnitude) * 100,
        )

    def generate_macro_regime_shock(
        self,
        gdp_growth: float = -2.0,
        inflation: float = 5.0,
        unemployment: float = 8.0,
    ) -> ShockVector:
        """Generate a macro-economic regime change shock."""
        equity_shock = gdp_growth * 0.05
        bond_shock = -inflation * 0.02
        commodity_shock = inflation * 0.03

        return ShockVector(
            asset_shocks={
                "equity": equity_shock,
                "bond": bond_shock,
                "commodity": commodity_shock,
            },
            macro_shocks={
                "gdp_growth": gdp_growth,
                "cpi": inflation,
                "unemployment": unemployment,
            },
            description=f"Macro regime: GDP {gdp_growth}%, CPI {inflation}%",
            total_impact_pct=abs(equity_shock) * 100,
        )

    # ---- Shock Combination ----

    def combine_shocks(self, *shocks: ShockVector) -> ShockVector:
        """Combine multiple shock vectors (additive)."""
        combined_assets: dict[str, float] = {}
        combined_macro: dict[str, float] = {}
        descriptions: list[str] = []
        total_impact = 0.0

        for s in shocks:
            for k, v in s.asset_shocks.items():
                combined_assets[k] = combined_assets.get(k, 0.0) + v
            for k, v in s.macro_shocks.items():
                combined_macro[k] = combined_macro.get(k, 0.0) + v
            descriptions.append(s.description)
            total_impact += s.total_impact_pct

        return ShockVector(
            asset_shocks=combined_assets,
            macro_shocks=combined_macro,
            description=" + ".join(descriptions),
            total_impact_pct=total_impact,
        )

    def scale_shock(self, shock: ShockVector, factor: float) -> ShockVector:
        """Scale a shock vector by a factor."""
        return ShockVector(
            asset_shocks={k: v * factor for k, v in shock.asset_shocks.items()},
            macro_shocks={k: v * factor for k, v in shock.macro_shocks.items()},
            description=f"{shock.description} (x{factor:.1f})",
            total_impact_pct=shock.total_impact_pct * factor,
        )

    # ---- Batch Generation ----

    def generate_standard_suite(self) -> list[ShockVector]:
        """Generate a standard suite of shocks for stress testing."""
        return [
            self.generate_equity_shock(-0.10),
            self.generate_equity_shock(-0.25),
            self.generate_equity_shock(-0.40),
            self.generate_rate_shock(100),
            self.generate_rate_shock(300),
            self.generate_fx_shock("USD", -0.15),
            self.generate_volatility_shock(3.0),
            self.generate_liquidity_shock(0.20),
            self.generate_credit_shock(200),
            self.generate_tail_shock("equity", 3.0),
            self.generate_tail_shock("equity", 5.0),
        ]
