"""Strategy Analyzer - analyzes attribution results for insights and recommendations."""

from typing import Any, Dict, List, Optional

from .models import (
    AttributionSource,
    AttributionSummary,
    PerformanceAttribution,
    MultiStrategyAttribution,
)


class StrategyAnalyzer:
    """Analyzes strategy performance attribution.

    Capabilities:
    - Return Analysis: Where did returns come from?
    - Risk Analysis: Where is risk concentrated?
    - Trade Analysis: How does execution impact returns?
    - Driver Identification: What are the key return drivers/detractors?
    - Alpha Quality Assessment: Is alpha real or spurious?
    """

    def __init__(self):
        self._analyses: Dict[str, Dict[str, Any]] = {}

    def analyze(self, attribution: PerformanceAttribution) -> Dict[str, Any]:
        """Perform comprehensive analysis of an attribution.

        Args:
            attribution: PerformanceAttribution to analyze.

        Returns:
            Dict with analysis results.
        """
        analysis_id = attribution.attribution_id

        # Return analysis
        return_analysis = self._analyze_returns(attribution)

        # Risk analysis
        risk_analysis = self._analyze_risk(attribution)

        # Trade analysis
        trade_analysis = self._analyze_trades(attribution)

        # Driver identification
        drivers, detractors = self._identify_drivers(attribution)

        # Alpha quality
        alpha_quality = self._assess_alpha_quality(attribution)

        # Efficiency
        risk_efficiency = self._assess_risk_efficiency(attribution)

        # Recommendation
        recommendation = self._generate_recommendation(attribution, drivers, detractors)

        analysis = {
            "analysis_id": analysis_id,
            "strategy_id": attribution.strategy_id,
            "period": attribution.period,
            "return_analysis": return_analysis,
            "risk_analysis": risk_analysis,
            "trade_analysis": trade_analysis,
            "key_drivers": drivers,
            "key_detractors": detractors,
            "alpha_quality": alpha_quality,
            "risk_efficiency": risk_efficiency,
            "recommendation": recommendation,
        }

        self._analyses[analysis_id] = analysis
        return analysis

    def summarize(self, attribution: PerformanceAttribution) -> AttributionSummary:
        """Generate a human-readable attribution summary.

        Args:
            attribution: PerformanceAttribution to summarize.

        Returns:
            AttributionSummary with headline, drivers, detractors, recommendations.
        """
        analysis = self.analyze(attribution)

        return AttributionSummary(
            strategy_id=attribution.strategy_id,
            period=attribution.period,
            headline=self._build_headline(attribution),
            key_drivers=analysis["key_drivers"],
            key_detractors=analysis["key_detractors"],
            recommendation=analysis["recommendation"],
            alpha_quality=analysis["alpha_quality"],
            risk_efficiency=analysis["risk_efficiency"],
        )

    def _analyze_returns(self, attr: PerformanceAttribution) -> Dict[str, Any]:
        """Analyze return decomposition."""
        total = max(abs(attr.total_return_bps), 0.01)

        return {
            "total_return_bps": attr.total_return_bps,
            "total_return_pct": attr.total_return_pct,
            "alpha_ratio": round(attr.alpha_return_bps / total, 4),
            "beta_ratio": round(attr.beta_return_bps / total, 4),
            "factor_ratio": round(attr.factor_return_bps / total, 4),
            "sector_ratio": round(attr.sector_return_bps / total, 4),
            "execution_drag_ratio": round(attr.execution_return_bps / total, 4),
            "risk_penalty_ratio": round(attr.risk_adjustment_bps / total, 4),
            "residual_ratio": round(attr.residual_bps / total, 4),
            "is_alpha_driven": attr.alpha_return_bps > 0 and
                abs(attr.alpha_return_bps) > abs(attr.beta_return_bps),
            "is_beta_driven": abs(attr.beta_return_bps) > abs(attr.alpha_return_bps),
            "return_concentration": self._calculate_concentration(attr),
        }

    def _analyze_risk(self, attr: PerformanceAttribution) -> Dict[str, Any]:
        """Analyze risk attribution."""
        # Factor concentration
        factor_concentration = 0.0
        if attr.factor_exposures:
            exposures = [abs(f.exposure) for f in attr.factor_exposures]
            factor_concentration = max(exposures) / (sum(exposures) + 0.01)

        # Sector concentration
        sector_concentration = 0.0
        if attr.sector_contributions:
            weights = [s.allocation_weight for s in attr.sector_contributions]
            sector_concentration = max(weights) / (sum(weights) + 0.01)

        # Position concentration
        position_concentration = 0.0
        if attr.position_contributions:
            weights = [p.weight for p in attr.position_contributions]
            position_concentration = max(weights) / (sum(weights) + 0.01)

        return {
            "factor_concentration": round(factor_concentration, 4),
            "sector_concentration": round(sector_concentration, 4),
            "position_concentration": round(position_concentration, 4),
            "risk_penalty_bps": attr.risk_adjustment_bps,
            "high_concentration_risk": any(
                c > 0.5 for c in [factor_concentration, sector_concentration, position_concentration]
            ),
        }

    def _analyze_trades(self, attr: PerformanceAttribution) -> Dict[str, Any]:
        """Analyze trade execution quality."""
        if not attr.trade_attributions:
            return {"total_trades": 0, "avg_cost_bps": 0.0, "quality_distribution": {}}

        costs = [t.total_cost_bps for t in attr.trade_attributions]
        avg_cost = sum(costs) / len(costs) if costs else 0.0

        # Quality distribution
        quality_dist = {}
        for trade in attr.trade_attributions:
            q = trade.quality.value
            quality_dist[q] = quality_dist.get(q, 0) + 1

        # Identify costly trades
        costly_trades = [t for t in attr.trade_attributions if abs(t.total_cost_bps) > 30]
        costly_symbols = list(set(t.symbol for t in costly_trades))

        return {
            "total_trades": len(attr.trade_attributions),
            "avg_cost_bps": round(avg_cost, 2),
            "total_execution_drag_bps": attr.execution_return_bps,
            "quality_distribution": quality_dist,
            "costly_trades_count": len(costly_trades),
            "costly_symbols": costly_symbols,
            "execution_efficiency": "EFFICIENT" if abs(avg_cost) < 10 else
                                   "ADEQUATE" if abs(avg_cost) < 25 else "INEFFICIENT",
        }

    def _identify_drivers(self, attr: PerformanceAttribution) -> tuple:
        """Identify key return drivers and detractors."""
        drivers = []
        detractors = []

        for component in attr.components:
            if component.contribution_bps > 0 and component.source != AttributionSource.RESIDUAL:
                drivers.append(
                    f"{component.source.value}: +{component.contribution_bps:.1f}bps "
                    f"({component.explanation})"
                )
            elif component.contribution_bps < 0:
                detractors.append(
                    f"{component.source.value}: {component.contribution_bps:.1f}bps "
                    f"({component.explanation})"
                )

        # Add factor-level drivers
        if attr.factor_exposures:
            for f in sorted(attr.factor_exposures,
                          key=lambda x: abs(x.return_contribution_bps), reverse=True)[:3]:
                if f.return_contribution_bps > 0:
                    drivers.append(
                        f"Factor {f.category.value}: +{f.return_contribution_bps:.1f}bps "
                        f"(exposure={f.exposure:.2f})"
                    )
                elif f.return_contribution_bps < 0:
                    detractors.append(
                        f"Factor {f.category.value}: {f.return_contribution_bps:.1f}bps "
                        f"(exposure={f.exposure:.2f})"
                    )

        return drivers[:5], detractors[:5]

    def _assess_alpha_quality(self, attr: PerformanceAttribution) -> str:
        """Assess alpha quality."""
        if attr.alpha_return_bps <= -10:
            return "NEGATIVE"
        if attr.alpha_return_bps > 0 and attr.alpha_return_bps > abs(attr.beta_return_bps) * 1.5:
            return "STRONG"
        if attr.alpha_return_bps > 0 and attr.alpha_return_bps > abs(attr.beta_return_bps) * 0.5:
            return "MODERATE"
        if attr.alpha_return_bps > 0:
            return "WEAK"
        return "NEGATIVE"

    def _assess_risk_efficiency(self, attr: PerformanceAttribution) -> str:
        """Assess risk-adjusted efficiency."""
        risk_drag_ratio = abs(attr.risk_adjustment_bps) / max(abs(attr.total_return_bps), 0.01)

        if risk_drag_ratio < 0.05:
            return "EFFICIENT"
        if risk_drag_ratio < 0.15:
            return "ADEQUATE"
        return "INEFFICIENT"

    def _generate_recommendation(
        self,
        attr: PerformanceAttribution,
        drivers: List[str],
        detractors: List[str],
    ) -> str:
        """Generate actionable recommendation."""
        parts = []

        # Alpha-driven recommendation
        alpha_ratio = attr.alpha_return_bps / max(abs(attr.total_return_bps), 0.01)
        if alpha_ratio > 0.5:
            parts.append("Strong alpha generation - consider increasing allocation")
        elif alpha_ratio < -0.3:
            parts.append("Negative alpha - review strategy logic or reduce exposure")

        # Execution recommendation
        exec_drag = abs(attr.execution_return_bps)
        if exec_drag > 20:
            parts.append(f"High execution costs ({exec_drag:.0f}bps) - review execution algo/venue")

        # Factor concentration
        if attr.factor_exposures and len(attr.factor_exposures) > 3:
            top_factor = max(attr.factor_exposures, key=lambda f: abs(f.exposure))
            if abs(top_factor.exposure) > 0.5:
                parts.append(
                    f"High concentration in {top_factor.category.value} factor - "
                    f"consider diversification"
                )

        # Risk recommendation
        if abs(attr.risk_adjustment_bps) > 30:
            parts.append("High risk penalty - tighten stop-loss or reduce leverage")

        if not parts:
            parts.append("Strategy performing within expectations - maintain current parameters")

        return " | ".join(parts)

    def _calculate_concentration(self, attr: PerformanceAttribution) -> float:
        """Calculate return source concentration (Herfindahl-like)."""
        contributions = [
            abs(attr.alpha_return_bps),
            abs(attr.beta_return_bps),
            abs(attr.factor_return_bps),
            abs(attr.sector_return_bps),
        ]
        total = sum(contributions) + 0.01
        weights = [c / total for c in contributions]
        return round(sum(w ** 2 for w in weights), 4)

    def _build_headline(self, attr: PerformanceAttribution) -> str:
        """Build headline summary."""
        direction = "up" if attr.total_return_bps > 0 else "down"
        alpha_desc = "strong alpha" if attr.alpha_return_bps > attr.beta_return_bps else "beta-driven"

        return (
            f"Strategy {attr.strategy_id} returned {direction} "
            f"{abs(attr.total_return_bps):.1f}bps in {attr.period}, "
            f"driven by {alpha_desc} ({attr.alpha_return_bps:.1f}bps alpha, "
            f"{attr.beta_return_bps:.1f}bps beta)"
        )

    def get_analysis(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve analysis by ID."""
        return self._analyses.get(analysis_id)

    def analyze_multi_strategy(
        self, multi_attr: MultiStrategyAttribution
    ) -> Dict[str, Any]:
        """Analyze a multi-strategy portfolio attribution."""
        strategy_analyses = {}
        for attr in multi_attr.strategy_attributions:
            strategy_analyses[attr.strategy_id] = self.analyze(attr)

        # Cross-strategy insights
        alpha_strategies = [
            s.strategy_id for s in multi_attr.strategy_attributions
            if s.alpha_return_bps > 0
        ]
        beta_strategies = [
            s.strategy_id for s in multi_attr.strategy_attributions
            if s.alpha_return_bps <= 0 and s.beta_return_bps > 0
        ]

        return {
            "portfolio_id": multi_attr.portfolio_id,
            "strategy_analyses": strategy_analyses,
            "alpha_generating_strategies": alpha_strategies,
            "beta_exposed_strategies": beta_strategies,
            "diversification_benefit_bps": multi_attr.diversification_benefit_bps,
            "recommendation": (
                f"Portfolio has {len(alpha_strategies)} alpha-generating and "
                f"{len(beta_strategies)} beta-exposed strategies. "
                f"Diversification benefit: {multi_attr.diversification_benefit_bps:.1f}bps"
            ),
        }
