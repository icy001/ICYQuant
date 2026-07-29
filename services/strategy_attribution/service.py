"""Strategy Performance Attribution Service - orchestrates the complete attribution pipeline.

Pipeline:
    Strategy Data → Calculator → Attribution → Analyzer → Summary → Recommendations
"""

import uuid
from typing import Any, Dict, List, Optional

from .models import (
    AttributionPeriod,
    AttributionStatus,
    AttributionSummary,
    MultiStrategyAttribution,
    PerformanceAttribution,
)
from .calculator import AttributionCalculator
from .analyzer import StrategyAnalyzer


class StrategyAttributionService:
    """Strategy Performance Attribution Service.

    Orchestrates the complete attribution pipeline:
    1. Calculate return decomposition
    2. Analyze attribution results
    3. Generate human-readable summaries
    4. Support multi-strategy portfolio analysis
    5. Period-over-period comparison

    Answers institutional-grade questions:
    - Why did the strategy make/lose money?
    - Which factors are driving returns?
    - How much alpha vs beta is the strategy generating?
    - Which trades are hurting performance?
    - Is the alpha real or spurious?
    """

    def __init__(self):
        self.calculator = AttributionCalculator()
        self.analyzer = StrategyAnalyzer()

    def attribute(
        self,
        strategy_id: str,
        period: str,
        strategy_data: Dict[str, Any],
        period_type: AttributionPeriod = AttributionPeriod.DAILY,
    ) -> Dict[str, Any]:
        """Run full attribution pipeline for a single strategy.

        Args:
            strategy_id: Strategy identifier.
            period: Time period label.
            strategy_data: Strategy performance data.
            period_type: Attribution period type.

        Returns:
            Dict with attribution, analysis, and summary.
        """
        # Step 1: Calculate attribution
        attribution = self.calculator.calculate(
            strategy_id=strategy_id,
            period=period,
            strategy_data=strategy_data,
            period_type=period_type,
        )

        # Step 2: Analyze
        analysis = self.analyzer.analyze(attribution)

        # Step 3: Summarize
        summary = self.analyzer.summarize(attribution)

        return {
            "attribution": attribution.to_dict(),
            "analysis": analysis,
            "summary": summary.to_dict(),
        }

    def attribute_multi_strategy(
        self,
        portfolio_id: str,
        period: str,
        strategies_data: List[Dict[str, Any]],
        period_type: AttributionPeriod = AttributionPeriod.DAILY,
    ) -> Dict[str, Any]:
        """Run attribution for a multi-strategy portfolio.

        Args:
            portfolio_id: Portfolio identifier.
            period: Time period label.
            strategies_data: List of dicts, each with strategy_id and strategy_data.
            period_type: Attribution period type.

        Returns:
            Dict with multi-strategy attribution and analysis.
        """
        strategy_attributions: List[PerformanceAttribution] = []

        for strat_data in strategies_data:
            strategy_id = strat_data.get("strategy_id", "unknown")
            data = strat_data.get("data", strat_data)

            attribution = self.calculator.calculate(
                strategy_id=strategy_id,
                period=period,
                strategy_data=data,
                period_type=period_type,
            )
            strategy_attributions.append(attribution)

        # Aggregate total return
        total_return = sum(a.total_return_bps for a in strategy_attributions)

        # Simple correlation calculation
        correlation_matrix: Dict[str, Dict[str, float]] = {}
        ids = [a.strategy_id for a in strategy_attributions]
        for i, id_i in enumerate(ids):
            correlation_matrix[id_i] = {}
            for j, id_j in enumerate(ids):
                if i == j:
                    correlation_matrix[id_i][id_j] = 1.0
                elif j > i:
                    corr = self._estimate_correlation(
                        strategy_attributions[i], strategy_attributions[j]
                    )
                    correlation_matrix[id_i][id_j] = corr
                    correlation_matrix.setdefault(id_j, {})[id_i] = corr

        # Diversification benefit = sum of individual - portfolio (simplified)
        individual_sum = sum(abs(a.total_return_bps) for a in strategy_attributions)
        diversification_benefit = individual_sum - abs(total_return)

        # Top and bottom contributors
        sorted_strategies = sorted(strategy_attributions, key=lambda a: a.total_return_bps, reverse=True)
        top_contributors = [
            {"strategy_id": s.strategy_id, "return_bps": s.total_return_bps,
             "alpha_bps": s.alpha_return_bps}
            for s in sorted_strategies[:3]
        ]
        bottom_contributors = [
            {"strategy_id": s.strategy_id, "return_bps": s.total_return_bps,
             "alpha_bps": s.alpha_return_bps}
            for s in sorted_strategies[-3:]
        ]

        multi_attr = MultiStrategyAttribution(
            portfolio_id=portfolio_id,
            period=period,
            total_return_bps=round(total_return, 2),
            strategy_attributions=strategy_attributions,
            correlation_matrix=correlation_matrix,
            diversification_benefit_bps=round(diversification_benefit, 2),
            top_contributors=top_contributors,
            bottom_contributors=bottom_contributors,
        )

        # Analyze
        multi_analysis = self.analyzer.analyze_multi_strategy(multi_attr)

        return {
            "attribution": multi_attr.to_dict(),
            "analysis": multi_analysis,
        }

    def get_attribution(self, attribution_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a previously calculated attribution."""
        attr = self.calculator.get_attribution(attribution_id)
        if not attr:
            return None
        return attr.to_dict()

    def get_history(
        self, strategy_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get attribution history, optionally filtered by strategy."""
        history = self.calculator.get_history(strategy_id)
        return [h.to_dict() for h in history]

    def compare_periods(
        self, strategy_id: str, period_a: str, period_b: str
    ) -> Dict[str, Any]:
        """Compare attribution across two periods."""
        return self.calculator.compare_periods(strategy_id, period_a, period_b)

    @staticmethod
    def _estimate_correlation(
        attr_a: PerformanceAttribution, attr_b: PerformanceAttribution
    ) -> float:
        """Estimate correlation between two strategies based on factor overlap."""
        factors_a = {f.category.value: f.exposure for f in attr_a.factor_exposures}
        factors_b = {f.category.value: f.exposure for f in attr_b.factor_exposures}

        common_factors = set(factors_a.keys()) & set(factors_b.keys())
        if not common_factors:
            return 0.0

        # Simple dot product of overlapping factor exposures
        dot = sum(factors_a[f] * factors_b[f] for f in common_factors)
        norm_a = sum(v ** 2 for v in factors_a.values()) ** 0.5
        norm_b = sum(v ** 2 for v in factors_b.values()) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        correlation = dot / (norm_a * norm_b)
        return round(max(min(correlation, 1.0), -1.0), 4)
