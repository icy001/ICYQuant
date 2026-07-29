"""Attribution Calculator - decomposes strategy PnL into component sources.

Core calculation:
    Total PnL = Market Exposure Contribution
              + Factor Exposure Contribution
              + Signal (Alpha) Contribution
              + Execution Contribution
              - Risk Penalty
              + Residual
"""

import uuid
from typing import Any, Dict, List, Optional

from .models import (
    AttributionPeriod,
    AttributionSource,
    AttributionStatus,
    FactorCategory,
    FactorExposure,
    PerformanceAttribution,
    PositionContribution,
    ReturnComponent,
    SectorContribution,
    TradeAttribution,
    TradeQuality,
)


class AttributionCalculator:
    """Calculates performance attribution for a strategy.

    Decomposes strategy returns into:
    - Alpha (signal/skill)
    - Market Beta (systematic market exposure)
    - Style Factor returns (momentum, value, quality, etc.)
    - Sector Exposure returns
    - Position Sizing contribution
    - Execution Quality contribution
    - Risk Control adjustment
    """

    def __init__(self):
        self._attributions: Dict[str, PerformanceAttribution] = {}
        self._history: List[PerformanceAttribution] = []

    def calculate(
        self,
        strategy_id: str,
        period: str,
        strategy_data: Dict[str, Any],
        period_type: AttributionPeriod = AttributionPeriod.DAILY,
    ) -> PerformanceAttribution:
        """Calculate complete performance attribution.

        Args:
            strategy_id: Strategy identifier.
            period: Time period label (e.g., "2026-Q3").
            strategy_data: Dict with strategy performance data including:
                - total_return_bps: Total return in basis points.
                - positions: List of position dicts with symbol, weight, return.
                - trades: List of trade execution dicts.
                - factor_exposures: Dict of factor name to exposure.
                - benchmark_return: Benchmark return for beta calculation.
                - market_return: Market return for beta calculation.
                - risk_free_rate: Risk-free rate for alpha calculation.
                - sector_allocations: List of sector allocation dicts.
            period_type: Attribution analysis period.

        Returns:
            PerformanceAttribution with full decomposition.
        """
        attr_id = str(uuid.uuid4())[:8]

        total_bps = strategy_data.get("total_return_bps", 0.0)
        if total_bps == 0.0 and "total_return_pct" in strategy_data:
            total_bps = strategy_data["total_return_pct"] * 100.0

        # Calculate each component
        alpha_bps = self._calculate_alpha(strategy_data, total_bps)
        beta_bps = self._calculate_beta(strategy_data)
        factor_bps, factor_exposures = self._calculate_factor_returns(strategy_data)
        sector_bps, sector_contribs = self._calculate_sector_returns(strategy_data)
        position_bps, position_contribs = self._calculate_position_contribution(strategy_data)
        execution_bps, trade_attribs = self._calculate_execution_contribution(strategy_data)
        risk_bps = self._calculate_risk_penalty(strategy_data)

        # Residual = total - sum of all components
        sum_components = (
            alpha_bps + beta_bps + factor_bps + sector_bps
            + position_bps + execution_bps + risk_bps
        )
        residual_bps = round(total_bps - sum_components, 2)

        # Build return components list
        components = [
            ReturnComponent(
                source=AttributionSource.ALPHA,
                contribution_bps=alpha_bps,
                weight_pct=abs(alpha_bps) / max(abs(total_bps), 0.01) * 100.0,
                return_contribution_pct=(alpha_bps / max(abs(total_bps), 0.01)) * 100.0,
                explanation="Strategy-specific alpha (signal/skill)",
                confidence=0.85,
            ),
            ReturnComponent(
                source=AttributionSource.MARKET_BETA,
                contribution_bps=beta_bps,
                weight_pct=abs(beta_bps) / max(abs(total_bps), 0.01) * 100.0,
                return_contribution_pct=(beta_bps / max(abs(total_bps), 0.01)) * 100.0,
                explanation="Systematic market exposure return",
                confidence=0.90,
            ),
            ReturnComponent(
                source=AttributionSource.STYLE_FACTOR,
                contribution_bps=factor_bps,
                weight_pct=abs(factor_bps) / max(abs(total_bps), 0.01) * 100.0,
                return_contribution_pct=(factor_bps / max(abs(total_bps), 0.01)) * 100.0,
                explanation="Style factor (momentum/value/quality etc.) exposure return",
                confidence=0.80,
            ),
            ReturnComponent(
                source=AttributionSource.SECTOR_EXPOSURE,
                contribution_bps=sector_bps,
                weight_pct=abs(sector_bps) / max(abs(total_bps), 0.01) * 100.0,
                return_contribution_pct=(sector_bps / max(abs(total_bps), 0.01)) * 100.0,
                explanation="Sector/industry allocation return",
                confidence=0.75,
            ),
            ReturnComponent(
                source=AttributionSource.POSITION_SIZING,
                contribution_bps=position_bps,
                weight_pct=abs(position_bps) / max(abs(total_bps), 0.01) * 100.0,
                return_contribution_pct=(position_bps / max(abs(total_bps), 0.01)) * 100.0,
                explanation="Position sizing contribution vs equal-weight",
                confidence=0.70,
            ),
            ReturnComponent(
                source=AttributionSource.EXECUTION_QUALITY,
                contribution_bps=execution_bps,
                weight_pct=abs(execution_bps) / max(abs(total_bps), 0.01) * 100.0,
                return_contribution_pct=(execution_bps / max(abs(total_bps), 0.01)) * 100.0,
                explanation="Execution quality (slippage, impact, commission)",
                confidence=0.95,
            ),
            ReturnComponent(
                source=AttributionSource.RISK_CONTROL,
                contribution_bps=risk_bps,
                weight_pct=abs(risk_bps) / max(abs(total_bps), 0.01) * 100.0,
                return_contribution_pct=(risk_bps / max(abs(total_bps), 0.01)) * 100.0,
                explanation="Risk control adjustment (stops, hedging, constraints)",
                confidence=0.75,
            ),
        ]

        if abs(residual_bps) > 1.0:
            components.append(
                ReturnComponent(
                    source=AttributionSource.RESIDUAL,
                    contribution_bps=residual_bps,
                    weight_pct=abs(residual_bps) / max(abs(total_bps), 0.01) * 100.0,
                    return_contribution_pct=(residual_bps / max(abs(total_bps), 0.01)) * 100.0,
                    explanation="Unexplained residual return",
                    confidence=0.30,
                )
            )

        attribution = PerformanceAttribution(
            attribution_id=attr_id,
            strategy_id=strategy_id,
            period=period,
            period_type=period_type,
            total_return_bps=total_bps,
            total_return_pct=total_bps / 100.0,
            alpha_return_bps=alpha_bps,
            beta_return_bps=beta_bps,
            factor_return_bps=factor_bps,
            sector_return_bps=sector_bps,
            position_sizing_bps=position_bps,
            execution_return_bps=execution_bps,
            risk_adjustment_bps=risk_bps,
            residual_bps=residual_bps,
            components=components,
            factor_exposures=factor_exposures,
            sector_contributions=sector_contribs,
            trade_attributions=trade_attribs,
            position_contributions=position_contribs,
            status=AttributionStatus.COMPLETED,
            confidence_score=self._calculate_confidence(strategy_data),
        )

        self._attributions[attr_id] = attribution
        self._history.append(attribution)
        return attribution

    def _calculate_alpha(self, data: Dict[str, Any], total_bps: float) -> float:
        """Calculate alpha contribution (strategy-specific skill).

        Alpha = Total Return - (Beta * Market Excess Return)
        Where market excess return = market_return - risk_free_rate.
        Input market_return and risk_free_rate are in decimal form (e.g., 0.05 = 5%).
        Output is in basis points.
        """
        market_return = data.get("market_return", 0.0)
        risk_free_rate = data.get("risk_free_rate", 0.0)
        beta = data.get("beta", 1.0)

        # Convert decimal returns to bps: 0.05 = 5% = 500 bps
        market_bps = market_return * 10000.0
        rf_bps = risk_free_rate * 10000.0
        market_excess_bps = market_bps - rf_bps

        expected_from_beta = beta * market_excess_bps
        alpha_bps = total_bps - expected_from_beta

        return round(alpha_bps, 2)

    def _calculate_beta(self, data: Dict[str, Any]) -> float:
        """Calculate market beta contribution.

        Beta Contribution = Beta * Market Return.
        Input market_return is in decimal form (e.g., 0.05 = 5%).
        Output is in basis points.
        """
        market_return = data.get("market_return", 0.0)
        beta = data.get("beta", 1.0)

        # Convert decimal return to bps: 0.05 = 5% = 500 bps
        market_bps = market_return * 10000.0
        beta_contribution = beta * market_bps

        return round(beta_contribution, 2)

    def _calculate_factor_returns(
        self, data: Dict[str, Any]
    ) -> tuple:
        """Calculate style factor return contribution.

        Maps factor exposures to factor returns and calculates contributions.
        """
        factor_exposures = data.get("factor_exposures", {})
        factor_returns = data.get("factor_returns", {})
        factor_attributions: List[FactorExposure] = []

        if not factor_exposures:
            return 0.0, factor_attributions

        total_factor_bps = 0.0

        for factor_name, exposure in factor_exposures.items():
            try:
                category = FactorCategory(factor_name.upper())
            except ValueError:
                category = FactorCategory.CUSTOM

            factor_return = factor_returns.get(factor_name, 0.0)
            contribution = exposure * factor_return * 10000.0
            total_factor_bps += contribution

            t_stat = abs(contribution) / max(abs(exposure), 0.01) if exposure != 0 else 0.0
            significance = (
                "SIGNIFICANT" if abs(t_stat) > 2.0
                else "MODERATE" if abs(t_stat) > 1.0
                else "WEAK"
            )

            factor_attributions.append(
                FactorExposure(
                    category=category,
                    exposure=exposure,
                    return_contribution_bps=round(contribution, 2),
                    factor_return=factor_return,
                    t_stat=round(t_stat, 2),
                    significance=significance,
                )
            )

        return round(total_factor_bps, 2), factor_attributions

    def _calculate_sector_returns(
        self, data: Dict[str, Any]
    ) -> tuple:
        """Calculate sector/industry allocation contribution.

        Active sector contribution = sum(active_weight * sector_return)
        """
        sector_allocations = data.get("sector_allocations", [])
        sector_attributions: List[SectorContribution] = []

        if not sector_allocations:
            return 0.0, sector_attributions

        total_sector_bps = 0.0

        for alloc in sector_allocations:
            sector = alloc.get("sector", "Unknown")
            alloc_weight = alloc.get("allocation_weight", 0.0)
            bench_weight = alloc.get("benchmark_weight", 0.0)
            sector_return = alloc.get("sector_return", 0.0)
            active_weight = alloc_weight - bench_weight

            contribution = active_weight * sector_return * 10000.0
            total_sector_bps += contribution

            sector_attributions.append(
                SectorContribution(
                    sector=sector,
                    allocation_weight=alloc_weight,
                    benchmark_weight=bench_weight,
                    active_weight=round(active_weight, 4),
                    sector_return=sector_return,
                    contribution_bps=round(contribution, 2),
                )
            )

        return round(total_sector_bps, 2), sector_attributions

    def _calculate_position_contribution(
        self, data: Dict[str, Any]
    ) -> tuple:
        """Calculate position sizing contribution.

        Position contribution = weight * return - equal_weight * return
        """
        positions = data.get("positions", [])
        position_attributions: List[PositionContribution] = []

        if not positions:
            return 0.0, position_attributions

        n = len(positions)
        equal_weight = 1.0 / n if n > 0 else 0.0

        total_position_bps = 0.0

        for pos in positions:
            symbol = pos.get("symbol", "UNKNOWN")
            weight = pos.get("weight", 0.0)
            ret = pos.get("return", 0.0)
            contribution = (weight - equal_weight) * ret * 10000.0
            total_position_bps += contribution

            position_attributions.append(
                PositionContribution(
                    symbol=symbol,
                    weight=weight,
                    return_pct=ret,
                    contribution_bps=round(contribution, 2),
                    is_overweight=weight > equal_weight,
                    risk_budget_used=pos.get("risk_budget_used", weight),
                )
            )

        return round(total_position_bps, 2), position_attributions

    def _calculate_execution_contribution(
        self, data: Dict[str, Any]
    ) -> tuple:
        """Calculate execution quality contribution.

        Execution contribution = sum(slippage + market_impact + commission)
        """
        trades = data.get("trades", [])
        trade_attributions: List[TradeAttribution] = []

        if not trades:
            return 0.0, trade_attributions

        total_execution_bps = 0.0

        for i, trade in enumerate(trades):
            slippage = trade.get("slippage_bps", 0.0)
            market_impact = trade.get("market_impact_bps", 0.0)
            commission = trade.get("commission_bps", 0.0)
            total_cost = slippage + market_impact + commission

            # Execution costs are negative (drag on returns)
            total_execution_bps += total_cost

            # Determine quality
            abs_cost = abs(total_cost)
            if abs_cost < 5:
                quality = TradeQuality.EXCELLENT
            elif abs_cost < 15:
                quality = TradeQuality.GOOD
            elif abs_cost < 30:
                quality = TradeQuality.AVERAGE
            elif abs_cost < 50:
                quality = TradeQuality.POOR
            else:
                quality = TradeQuality.FAILED

            trade_attributions.append(
                TradeAttribution(
                    trade_id=trade.get("trade_id", f"trade_{i}"),
                    symbol=trade.get("symbol", "UNKNOWN"),
                    side=trade.get("side", "BUY"),
                    quantity=trade.get("quantity", 0.0),
                    arrival_price=trade.get("arrival_price", 0.0),
                    execution_price=trade.get("execution_price", 0.0),
                    slippage_bps=slippage,
                    market_impact_bps=market_impact,
                    commission_bps=commission,
                    total_cost_bps=total_cost,
                    quality=quality,
                )
            )

        return round(total_execution_bps, 2), trade_attributions

    def _calculate_risk_penalty(self, data: Dict[str, Any]) -> float:
        """Calculate risk control adjustment.

        Risk penalty from stops, hedging costs, and constraint violations.
        """
        risk_data = data.get("risk_data", {})

        stop_loss_cost = risk_data.get("stop_loss_cost_bps", 0.0)
        hedging_cost = risk_data.get("hedging_cost_bps", 0.0)
        constraint_penalty = risk_data.get("constraint_penalty_bps", 0.0)

        total_risk_bps = stop_loss_cost + hedging_cost + constraint_penalty
        return round(-abs(total_risk_bps), 2)  # Risk is always a cost

    def _calculate_confidence(self, data: Dict[str, Any]) -> float:
        """Calculate confidence score for the attribution."""
        score = 1.0

        # Deduct for missing data
        if not data.get("positions"):
            score -= 0.15
        if not data.get("trades"):
            score -= 0.10
        if not data.get("factor_exposures"):
            score -= 0.10
        if not data.get("sector_allocations"):
            score -= 0.05
        if not data.get("market_return"):
            score -= 0.10

        return max(score, 0.1)

    def get_attribution(self, attribution_id: str) -> Optional[PerformanceAttribution]:
        """Retrieve attribution by ID."""
        return self._attributions.get(attribution_id)

    def get_history(self, strategy_id: Optional[str] = None) -> List[PerformanceAttribution]:
        """Get attribution history, optionally filtered by strategy."""
        if strategy_id:
            return [a for a in self._history if a.strategy_id == strategy_id]
        return list(self._history)

    def compare_periods(
        self, strategy_id: str, period_a: str, period_b: str
    ) -> Dict[str, Any]:
        """Compare attribution across two periods."""
        attrs = [a for a in self._history if a.strategy_id == strategy_id]

        attr_a = next((a for a in attrs if a.period == period_a), None)
        attr_b = next((a for a in attrs if a.period == period_b), None)

        if not attr_a or not attr_b:
            return {"error": "One or both periods not found"}

        return {
            "strategy_id": strategy_id,
            "period_a": period_a,
            "period_b": period_b,
            "return_change_bps": attr_b.total_return_bps - attr_a.total_return_bps,
            "alpha_change_bps": attr_b.alpha_return_bps - attr_a.alpha_return_bps,
            "beta_change_bps": attr_b.beta_return_bps - attr_a.beta_return_bps,
            "factor_change_bps": attr_b.factor_return_bps - attr_a.factor_return_bps,
            "execution_change_bps": attr_b.execution_return_bps - attr_a.execution_return_bps,
            "risk_change_bps": attr_b.risk_adjustment_bps - attr_a.risk_adjustment_bps,
        }
