"""
Sensitivity Analysis — Portfolio sensitivity to key risk factors.

Analyzes how portfolio value changes with respect to movements in:
price, interest rates, volatility, FX rates, and commodities.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SensitivityAnalyzer:
    """
    Portfolio sensitivity (Greeks-like) analysis engine.

    Computes first and second-order sensitivities to:
    - Price (Delta, Gamma)
    - Interest rates (Rho)
    - Volatility (Vega)
    - FX rates
    - Commodity prices

    Usage::

        analyzer = SensitivityAnalyzer()
        await analyzer.initialize()
        results = await analyzer.analyze(portfolio_data)
    """

    # Standard shock sizes
    DEFAULT_SHOCKS = {
        "price": [0.01, -0.01, 0.05, -0.05],  # ±1%, ±5%
        "interest_rate": [0.0025, -0.0025, 0.01, -0.01],  # ±25bps, ±100bps
        "volatility": [0.01, -0.01, 0.05, -0.05],
        "fx": [0.01, -0.01, 0.05, -0.05],
        "commodity": [0.02, -0.02, 0.10, -0.10],
    }

    def __init__(self) -> None:
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the sensitivity analyzer."""
        self._initialized = True

    async def analyze(self, portfolio_data: dict[str, Any]) -> dict[str, Any]:
        """
        Run full sensitivity analysis.

        Returns
        -------
        dict
            Sensitivity results per risk factor.
        """
        total_value = portfolio_data.get("total_value", 1_000_000)
        positions = portfolio_data.get("positions", [])

        results = {
            "portfolio_value": total_value,
            "sensitivities": {},
        }

        # Price sensitivity (Delta, Gamma)
        results["sensitivities"]["price"] = self._compute_price_sensitivity(
            total_value, positions
        )

        # Interest rate sensitivity
        results["sensitivities"]["interest_rate"] = self._compute_rate_sensitivity(
            total_value, positions
        )

        # Volatility sensitivity (Vega)
        results["sensitivities"]["volatility"] = self._compute_vol_sensitivity(
            total_value, positions
        )

        # FX sensitivity
        results["sensitivities"]["fx"] = self._compute_fx_sensitivity(
            total_value, positions
        )

        # Commodity sensitivity
        results["sensitivities"]["commodity"] = self._compute_commodity_sensitivity(
            total_value, positions
        )

        # Summary
        results["summary"] = self._summarize(results["sensitivities"])

        return results

    def _compute_price_sensitivity(
        self, total_value: float, positions: list[dict]
    ) -> dict[str, Any]:
        """Compute Delta and Gamma."""
        sensitivities = {}
        for shock in self.DEFAULT_SHOCKS["price"]:
            impact = total_value * shock
            sensitivities[f"shock_{shock*100:+.1f}pct"] = {
                "impact_absolute": round(impact, 2),
                "impact_percentage": round(shock * 100, 2),
            }

        # Delta ≈ impact / shock
        delta = total_value  # simplified: full notional exposure
        sensitivities["delta"] = round(delta, 2)
        sensitivities["delta_pct"] = 100.0

        # Gamma = 0 for linear instruments, non-zero for options
        options_count = sum(
            1 for p in positions
            if isinstance(p, dict) and p.get("instrument_type") in ("option", "derivative")
        )
        sensitivities["gamma"] = round(options_count * total_value * 0.001, 2)
        sensitivities["has_options"] = options_count > 0

        return sensitivities

    def _compute_rate_sensitivity(
        self, total_value: float, positions: list[dict]
    ) -> dict[str, Any]:
        """Compute interest rate sensitivity (DV01, duration)."""
        sensitivities = {}

        # Duration approximation
        bond_exposure = sum(
            p.get("market_value", 0) for p in positions
            if isinstance(p, dict) and p.get("asset_class") in ("bond", "fixed_income")
        )
        avg_duration = 5.0  # assumed average duration

        for shock in self.DEFAULT_SHOCKS["interest_rate"]:
            impact = -bond_exposure * avg_duration * shock
            sensitivities[f"shock_{shock*10000:+.0f}bps"] = {
                "impact_absolute": round(impact, 2),
                "impact_percentage": round(impact / total_value * 100, 4) if total_value > 0 else 0,
            }

        # DV01: dollar value per 1bp
        dv01 = bond_exposure * avg_duration * 0.0001
        sensitivities["dv01"] = round(dv01, 2)
        sensitivities["effective_duration"] = avg_duration
        sensitivities["bond_exposure"] = round(bond_exposure, 2)

        return sensitivities

    def _compute_vol_sensitivity(
        self, total_value: float, positions: list[dict]
    ) -> dict[str, Any]:
        """Compute volatility sensitivity (Vega)."""
        sensitivities = {}

        option_exposure = sum(
            p.get("market_value", 0) for p in positions
            if isinstance(p, dict) and p.get("instrument_type") in ("option", "derivative")
        )

        for shock in self.DEFAULT_SHOCKS["volatility"]:
            impact = option_exposure * shock * 0.4  # vega ≈ 0.4x
            sensitivities[f"shock_{shock*100:+.1f}vol_pct"] = {
                "impact_absolute": round(impact, 2),
                "impact_percentage": round(impact / total_value * 100, 4) if total_value > 0 else 0,
            }

        sensitivities["vega"] = round(option_exposure * 0.01, 2)  # per 1% vol change
        sensitivities["option_exposure"] = round(option_exposure, 2)

        return sensitivities

    def _compute_fx_sensitivity(
        self, total_value: float, positions: list[dict]
    ) -> dict[str, Any]:
        """Compute FX sensitivity."""
        sensitivities = {}

        fx_exposure = sum(
            p.get("market_value", 0) for p in positions
            if isinstance(p, dict) and p.get("asset_class") == "forex"
        )

        for shock in self.DEFAULT_SHOCKS["fx"]:
            impact = fx_exposure * shock
            sensitivities[f"shock_{shock*100:+.1f}pct"] = {
                "impact_absolute": round(impact, 2),
                "impact_percentage": round(shock * 100, 2),
            }

        sensitivities["fx_exposure"] = round(fx_exposure, 2)
        sensitivities["fx_beta"] = round(fx_exposure / total_value, 4) if total_value > 0 else 0

        return sensitivities

    def _compute_commodity_sensitivity(
        self, total_value: float, positions: list[dict]
    ) -> dict[str, Any]:
        """Compute commodity sensitivity."""
        sensitivities = {}

        commodity_exposure = sum(
            p.get("market_value", 0) for p in positions
            if isinstance(p, dict) and p.get("asset_class") == "commodity"
        )

        for shock in self.DEFAULT_SHOCKS["commodity"]:
            impact = commodity_exposure * shock
            sensitivities[f"shock_{shock*100:+.1f}pct"] = {
                "impact_absolute": round(impact, 2),
                "impact_percentage": round(shock * 100, 2),
            }

        sensitivities["commodity_exposure"] = round(commodity_exposure, 2)

        return sensitivities

    def _summarize(self, sensitivities: dict[str, Any]) -> dict[str, Any]:
        """Generate summary of sensitivities."""
        summary = {
            "largest_sensitivity": "price",
            "largest_impact_pct": 100.0,
            "warnings": [],
        }

        # Check for warnings
        delta_pct = sensitivities.get("price", {}).get("delta_pct", 0)
        if delta_pct > 200:
            summary["warnings"].append("High leverage detected (delta > 200%).")

        dv01 = sensitivities.get("interest_rate", {}).get("dv01", 0)
        if abs(dv01) > 10000:
            summary["warnings"].append(f"High rate sensitivity (DV01 = {dv01:.0f}).")

        fx_exp = sensitivities.get("fx", {}).get("fx_exposure", 0)
        if abs(fx_exp) > 500000:
            summary["warnings"].append("Significant unhedged FX exposure.")

        return summary
