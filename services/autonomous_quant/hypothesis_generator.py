"""Hypothesis Generator — Generates testable research hypotheses from opportunities.

Spins structured hypotheses from market opportunities. Each hypothesis
includes a clear statement, expected mechanism, falsification criteria,
and required resources for testing.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HypothesisGenerator:
    """Hypothesis Generator — creates testable quant research hypotheses.

    Hypothesis structure:
        ├── Statement: What is being tested
        ├── Universe: Scope of the hypothesis
        ├── Time Horizon: Expected holding period
        ├── Expected Direction: Predicted effect direction
        ├── Expected Mechanism: Why it should work
        ├── Required Features: What data is needed
        ├── Required Data: Data requirements
        └── Falsification Criteria: What would disprove it

    Each hypothesis is a first-class research object with its own lifecycle:
        DRAFT → VALIDATING → VALID → PLANNING → EXPERIMENTING → COMPLETED/REJECTED
    """

    def __init__(self) -> None:
        self._hypotheses_generated: int = 0

    async def generate(
        self,
        opportunities: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate hypotheses from research opportunities.

        Args:
            opportunities: Ranked research opportunities.

        Returns:
            Dict with hypotheses list and metadata.
        """
        hypotheses: List[Dict[str, Any]] = []

        for opp in opportunities:
            hyp = self._generate_for_opportunity(opp)
            if hyp:
                hypotheses.append(hyp)

        self._hypotheses_generated += len(hypotheses)

        logger.info("Hypotheses generated: %d", len(hypotheses))

        return {
            "hypotheses": hypotheses,
            "total_generated": self._hypotheses_generated,
            "by_type": self._group_by_type(hypotheses),
        }

    def _generate_for_opportunity(
        self,
        opp: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Generate a hypothesis for a specific opportunity."""
        opp_type = opp.get("type", "")
        symbols = opp.get("symbols", [])

        if not symbols:
            return None

        generators = {
            "momentum": self._momentum_hypothesis,
            "mean_reversion": self._mean_reversion_hypothesis,
            "volatility": self._volatility_hypothesis,
            "cross_asset": self._cross_asset_hypothesis,
            "correlation_breakdown": self._correlation_breakdown_hypothesis,
            "anomaly": self._anomaly_hypothesis,
            "regime": self._regime_hypothesis,
            "sector": self._sector_hypothesis,
            "liquidity": self._liquidity_hypothesis,
        }

        generator = generators.get(opp_type, self._generic_hypothesis)
        return generator(opp, symbols)

    # ------------------------------------------------------------------
    # Hypothesis Templates
    # ------------------------------------------------------------------

    def _momentum_hypothesis(
        self, opp: Dict[str, Any], symbols: List[str]
    ) -> Dict[str, Any]:
        """Momentum-based hypothesis."""
        symbol_str = symbols[0] if symbols else "the asset"
        return self._build_hypothesis(
            opportunity=opp,
            statement=(
                f"Past price momentum in {symbol_str} predicts future "
                f"relative returns in {opp.get('title', 'the universe')}"
            ),
            expected_direction="positive",
            expected_mechanism="Trend continuation due to investor underreaction",
            features_needed=["momentum_1m", "momentum_3m", "momentum_6m", "volatility"],
            falsification="No significant predictive power (IC < 0.02) in out-of-sample test",
        )

    def _mean_reversion_hypothesis(
        self, opp: Dict[str, Any], symbols: List[str]
    ) -> Dict[str, Any]:
        """Mean reversion hypothesis."""
        return self._build_hypothesis(
            opportunity=opp,
            statement=f"Extreme short-term returns in {', '.join(symbols[:3])} revert within 5-20 days",
            expected_direction="negative",
            expected_mechanism="Overreaction correction and liquidity provision",
            features_needed=["returns_1d", "returns_5d", "volume", "volatility"],
            falsification="No significant mean reversion effect (t-stat < 2.0)",
        )

    def _volatility_hypothesis(
        self, opp: Dict[str, Any], symbols: List[str]
    ) -> Dict[str, Any]:
        """Volatility-based hypothesis."""
        return self._build_hypothesis(
            opportunity=opp,
            statement=f"Volatility regime shifts predict future return dispersion in {', '.join(symbols[:3])}",
            expected_direction="both",
            expected_mechanism="VIX/volatility term structure inform cross-sectional dispersion",
            features_needed=["realized_vol", "implied_vol", "vol_spread", "term_structure"],
            falsification="Volatility metrics do not explain return dispersion (R² < 0.05)",
        )

    def _cross_asset_hypothesis(
        self, opp: Dict[str, Any], symbols: List[str]
    ) -> Dict[str, Any]:
        """Cross-asset relationship hypothesis."""
        return self._build_hypothesis(
            opportunity=opp,
            statement="Cross-asset price relationships contain predictive information for equity returns",
            expected_direction="directional",
            expected_mechanism="Lead-lag relationships across asset classes",
            features_needed=["equity_returns", "bond_yields", "fx_rates", "commodity_prices"],
            falsification="Cross-asset signals add no marginal predictive power",
        )

    def _correlation_breakdown_hypothesis(
        self, opp: Dict[str, Any], symbols: List[str]
    ) -> Dict[str, Any]:
        """Correlation breakdown hypothesis."""
        return self._build_hypothesis(
            opportunity=opp,
            statement=f"Correlation breakdown events precede directional moves in {', '.join(symbols[:3])}",
            expected_direction="directional",
            expected_mechanism="De-correlation signals regime change and alpha opportunities",
            features_needed=["pairwise_corr", "sector_corr", "corr_rolling", "corr_breakdown_flag"],
            falsification="Correlation breakdown does not predict future returns",
        )

    def _anomaly_hypothesis(
        self, opp: Dict[str, Any], symbols: List[str]
    ) -> Dict[str, Any]:
        """Anomaly investigation hypothesis."""
        return self._build_hypothesis(
            opportunity=opp,
            statement=f"The detected {opp.get('details', {}).get('type', 'unknown')} anomaly contains predictive alpha",
            expected_direction="directional",
            expected_mechanism="Statistical anomalies reflect information asymmetry or regime change",
            features_needed=["anomaly_score", "context_features", "market_features"],
            falsification="Anomaly signal decays within 1 day or has negative IC",
        )

    def _regime_hypothesis(
        self, opp: Dict[str, Any], symbols: List[str]
    ) -> Dict[str, Any]:
        """Regime-based hypothesis."""
        regime = opp.get("details", {}).get("current_regime", "unknown")
        return self._build_hypothesis(
            opportunity=opp,
            statement=f"The {regime} market regime creates distinct factor return patterns",
            expected_direction="conditional",
            expected_mechanism="Different factors perform differently across regimes",
            features_needed=["regime_classification", "factor_returns", "macro_indicators"],
            falsification="Factor returns are not regime-conditional",
        )

    def _sector_hypothesis(
        self, opp: Dict[str, Any], symbols: List[str]
    ) -> Dict[str, Any]:
        """Sector-based hypothesis."""
        return self._build_hypothesis(
            opportunity=opp,
            statement=f"Sector rotation signals predict {opp.get('title', 'relative performance')}",
            expected_direction="directional",
            expected_mechanism="Sector flows anticipate relative performance shifts",
            features_needed=["sector_returns", "sector_flows", "relative_strength"],
            falsification="Sector signals have no predictive power",
        )

    def _liquidity_hypothesis(
        self, opp: Dict[str, Any], symbols: List[str]
    ) -> Dict[str, Any]:
        """Liquidity-based hypothesis."""
        return self._build_hypothesis(
            opportunity=opp,
            statement=f"Order flow imbalance in {', '.join(symbols[:3])} predicts short-term returns",
            expected_direction="positive",
            expected_mechanism="Order flow contains informed trading information",
            features_needed=["order_imbalance", "trade_size", "bid_ask_spread", "depth"],
            falsification="Flow signal IC < 0.01 or decays within minutes",
        )

    def _generic_hypothesis(
        self, opp: Dict[str, Any], symbols: List[str]
    ) -> Dict[str, Any]:
        """Generic hypothesis for unknown opportunity types."""
        return self._build_hypothesis(
            opportunity=opp,
            statement=f"The {opp.get('type', 'observed')} pattern in {', '.join(symbols[:3])} is predictive",
            expected_direction="unknown",
            expected_mechanism="Pattern reflects underlying market inefficiency",
            features_needed=["price", "volume", "volatility"],
            falsification="No significant predictive signal (IC ≈ 0)",
        )

    # ------------------------------------------------------------------
    # Builder
    # ------------------------------------------------------------------

    def _build_hypothesis(
        self,
        opportunity: Dict[str, Any],
        statement: str,
        expected_direction: str,
        expected_mechanism: str,
        features_needed: List[str],
        falsification: str,
        time_horizon: str = "short_term",
    ) -> Dict[str, Any]:
        """Build a structured hypothesis."""
        return {
            "hypothesis_id": f"hyp_{random.randint(10000, 99999)}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
            "source_opportunity": opportunity.get("opportunity_id", ""),
            "opportunity_type": opportunity.get("type", ""),
            "statement": statement,
            "universe": opportunity.get("symbols", []),
            "time_horizon": time_horizon,
            "expected_direction": expected_direction,
            "expected_mechanism": expected_mechanism,
            "required_features": features_needed,
            "required_data": ["price", "volume", "fundamentals"],
            "falsification_criteria": falsification,
            "confidence": opportunity.get("confidence", 0.6),
            "status": "draft",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _group_by_type(
        hypotheses: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        groups: Dict[str, int] = {}
        for h in hypotheses:
            t = h.get("opportunity_type", "unknown")
            groups[t] = groups.get(t, 0) + 1
        return groups
