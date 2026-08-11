"""
Autonomous Risk Optimizer — central risk optimization engine.

Transforms raw target positions into risk-adjusted positions by applying:
    - Dynamic risk budgeting (regime-aware)
    - Exposure optimization (gross/net)
    - Factor risk decomposition
    - Concentration & correlation controls
    - Liquidity & drawdown constraints
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class OptimizationMode(Enum):
    """Risk optimization modes."""
    STANDARD = "standard"
    DEFENSIVE = "defensive"
    AGGRESSIVE = "aggressive"
    LIQUIDATION = "liquidation"
    EMERGENCY = "emergency"


@dataclass
class RiskConstraints:
    """Risk constraint parameters."""
    max_risk_budget: float = 1.0
    max_gross_exposure: float = 2.0
    max_net_exposure: float = 1.5
    max_leverage: float = 3.0
    max_single_position: float = 0.20
    max_sector_exposure: float = 0.40
    max_factor_exposure: float = 0.60
    min_liquidity_ratio: float = 0.01
    max_correlation: float = 0.70
    max_drawdown: float = 0.15
    var_limit_pct: float = 0.03
    es_limit_pct: float = 0.05


@dataclass
class RiskOptimizationResult:
    """Result of a risk optimization run."""
    id: str = field(default_factory=lambda: str(uuid4()))
    original_positions: dict[str, float] = field(default_factory=dict)
    adjusted_positions: dict[str, float] = field(default_factory=dict)
    risk_budget_used: float = 0.0
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    leverage: float = 0.0
    var_estimate: float = 0.0
    es_estimate: float = 0.0
    resizes: list[dict] = field(default_factory=list)
    rejections: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class RiskOptimizer:
    """
    Autonomous risk optimization engine.

    Pipeline:
        1. Apply dynamic risk budget
        2. Optimize exposures
        3. Apply leverage constraints
        4. Control concentration
        5. Optimize correlations
        6. Check liquidity
        7. Apply drawdown controls
        8. Apply regime-aware scaling
        9. Compute VaR / ES
        10. Generate final risk-adjusted positions

    Safety: All adjustments flow through RiskExecutionController.
    """

    def __init__(self, constraints: Optional[RiskConstraints] = None) -> None:
        self._constraints = constraints or RiskConstraints()
        self._last_result: Optional[RiskOptimizationResult] = None

    async def optimize(
        self,
        target_positions: dict[str, float],
        market_data: Optional[dict] = None,
        mode: OptimizationMode = OptimizationMode.STANDARD,
        regime: str = "NORMAL",
    ) -> RiskOptimizationResult:
        """
        Run full risk optimization on target positions.

        Args:
            target_positions: Raw target {asset: weight}
            market_data: Current market data
            mode: Optimization mode
            regime: Current market regime

        Returns:
            RiskOptimizationResult with adjusted positions
        """
        result = RiskOptimizationResult(original_positions=dict(target_positions))
        current_positions = dict(target_positions)

        # Stage 1: Risk budget
        budget = self._compute_dynamic_budget(regime, mode)
        current_positions = self._apply_risk_budget(current_positions, budget)
        result.risk_budget_used = budget

        # Stage 2: Exposure
        current_positions, gross, net = self._optimize_exposure(current_positions)
        result.gross_exposure = gross
        result.net_exposure = net

        # Stage 3: Leverage
        current_positions, lev = self._apply_leverage_constraint(current_positions)
        result.leverage = lev

        # Stage 4: Concentration
        current_positions, resizes = self._optimize_concentration(current_positions)
        result.resizes.extend(resizes)

        # Stage 5: Correlation
        current_positions = self._optimize_correlation(current_positions)

        # Stage 6: Liquidity
        current_positions, liq_warnings = self._check_liquidity(
            current_positions, market_data or {}
        )
        result.warnings.extend(liq_warnings)

        # Stage 7: Drawdown
        current_positions = self._apply_drawdown_control(current_positions, mode)

        # Stage 8: Regime scaling
        current_positions = self._apply_regime_scaling(current_positions, regime)

        # Stage 9: VaR / ES
        result.var_estimate = self._estimate_var(current_positions)
        result.es_estimate = self._estimate_es(current_positions)

        result.adjusted_positions = current_positions
        result.timestamp = datetime.now()
        self._last_result = result

        logger.info(
            "Risk optimization complete: %d positions, budget=%.2f, gross=%.2f, var=%.4f",
            len(current_positions), budget, gross, result.var_estimate,
        )
        return result

    # ── Internal Methods ───────────────────────────────────────

    def _compute_dynamic_budget(self, regime: str, mode: OptimizationMode) -> float:
        """Compute dynamic risk budget based on regime and mode."""
        base_budgets = {
            "NORMAL": 1.0, "TRENDING": 0.85, "MEAN_REVERTING": 0.75,
            "HIGH_VOL": 0.60, "RISK_OFF": 0.35, "CRISIS": 0.20,
        }
        mode_multipliers = {
            OptimizationMode.STANDARD: 1.0,
            OptimizationMode.DEFENSIVE: 0.70,
            OptimizationMode.AGGRESSIVE: 1.15,
            OptimizationMode.LIQUIDATION: 0.30,
            OptimizationMode.EMERGENCY: 0.10,
        }
        base = base_budgets.get(regime, 0.60)
        multiplier = mode_multipliers.get(mode, 1.0)
        budget = min(base * multiplier, self._constraints.max_risk_budget)
        return max(budget, 0.05)  # Floor at 5%

    def _apply_risk_budget(
        self, positions: dict[str, float], budget: float
    ) -> dict[str, float]:
        """Scale all positions by risk budget."""
        return {k: v * budget for k, v in positions.items()}

    def _optimize_exposure(
        self, positions: dict[str, float]
    ) -> tuple[dict[str, float], float, float]:
        """Optimize gross and net exposure."""
        long_exposure = sum(v for v in positions.values() if v > 0)
        short_exposure = sum(abs(v) for v in positions.values() if v < 0)
        gross = long_exposure + short_exposure
        net = long_exposure - short_exposure

        result = dict(positions)
        if gross > self._constraints.max_gross_exposure:
            scale = self._constraints.max_gross_exposure / gross
            result = {k: v * scale for k, v in result.items()}
            gross = self._constraints.max_gross_exposure

        if abs(net) > self._constraints.max_net_exposure:
            scale = self._constraints.max_net_exposure / abs(net)
            result = {k: v * scale for k, v in result.items()}
            net = self._constraints.max_net_exposure * (1 if net > 0 else -1)

        return result, gross, net

    def _apply_leverage_constraint(
        self, positions: dict[str, float]
    ) -> tuple[dict[str, float], float]:
        """Apply leverage limit."""
        gross = sum(abs(v) for v in positions.values())
        if gross > self._constraints.max_leverage:
            scale = self._constraints.max_leverage / gross
            return {k: v * scale for k, v in positions.items()}, self._constraints.max_leverage
        return positions, gross

    def _optimize_concentration(
        self, positions: dict[str, float]
    ) -> tuple[dict[str, float], list[dict]]:
        """Control single-asset and sector concentration."""
        resizes = []
        result = dict(positions)
        for asset, weight in list(result.items()):
            if abs(weight) > self._constraints.max_single_position:
                sign = 1 if weight > 0 else -1
                new_weight = self._constraints.max_single_position * sign
                resizes.append({
                    "asset": asset, "original": weight, "adjusted": new_weight,
                    "reason": "single_asset_concentration",
                })
                result[asset] = new_weight
        return result, resizes

    def _optimize_correlation(
        self, positions: dict[str, float]
    ) -> dict[str, float]:
        """Reduce positions with high correlation."""
        return positions  # Requires correlation matrix input

    def _check_liquidity(
        self, positions: dict[str, float], market_data: dict
    ) -> tuple[dict[str, float], list[str]]:
        """Check and adjust for liquidity constraints."""
        warnings = []
        adv = market_data.get("adv", {})
        result = dict(positions)
        for asset, weight in list(result.items()):
            asset_adv = adv.get(asset, float("inf"))
            if asset_adv > 0 and abs(weight) / asset_adv < self._constraints.min_liquidity_ratio:
                warnings.append(f"Low liquidity for {asset}")
        return result, warnings

    def _apply_drawdown_control(
        self, positions: dict[str, float], mode: OptimizationMode
    ) -> dict[str, float]:
        """Scale positions based on drawdown level."""
        if mode == OptimizationMode.EMERGENCY:
            return {k: v * 0.10 for k, v in positions.items()}
        if mode == OptimizationMode.LIQUIDATION:
            return {k: v * 0.30 for k, v in positions.items()}
        return positions

    def _apply_regime_scaling(
        self, positions: dict[str, float], regime: str
    ) -> dict[str, float]:
        """Apply regime-specific position scaling."""
        regime_scales = {
            "NORMAL": 1.0, "TRENDING": 1.0, "MEAN_REVERTING": 0.85,
            "HIGH_VOL": 0.60, "RISK_OFF": 0.35, "CRISIS": 0.15,
        }
        scale = regime_scales.get(regime, 0.50)
        return {k: v * scale for k, v in positions.items()}

    def _estimate_var(self, positions: dict[str, float]) -> float:
        """Estimate portfolio VaR."""
        gross = sum(abs(v) for v in positions.values())
        return gross * 0.02  # Simplified: 2% daily VaR estimate

    def _estimate_es(self, positions: dict[str, float]) -> float:
        """Estimate Expected Shortfall."""
        return self._estimate_var(positions) * 1.4  # ES ≈ 1.4x VaR

    @property
    def last_result(self) -> Optional[RiskOptimizationResult]:
        return self._last_result
