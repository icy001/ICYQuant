"""Liquidity Intelligence Engine.

Monitors global liquidity conditions across multiple dimensions:
central bank balance sheets, money supply, credit markets,
currency conditions, and cross-border capital flows.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from .data import MacroDataSnapshot, MacroIndicator


class LiquidityCondition(str, Enum):
    """Overall liquidity condition."""
    EXTREMELY_TIGHT = "extremely_tight"
    TIGHT = "tight"
    SLIGHTLY_TIGHT = "slightly_tight"
    NEUTRAL = "neutral"
    SLIGHTLY_LOOSE = "slightly_loose"
    LOOSE = "loose"
    EXTREMELY_LOOSE = "extremely_loose"


class LiquidityTrend(str, Enum):
    """Direction of liquidity change."""
    RAPIDLY_TIGHTENING = "rapidly_tightening"
    TIGHTENING = "tightening"
    SLIGHTLY_TIGHTENING = "slightly_tightening"
    STABLE = "stable"
    SLIGHTLY_EASING = "slightly_easing"
    EASING = "easing"
    RAPIDLY_EASING = "rapidly_easing"


@dataclass
class LiquidityAnalysis:
    """Result of liquidity analysis.

    Attributes:
        condition: Overall liquidity condition.
        trend: Liquidity trend direction.
        composite_score: Composite liquidity score (-1 to 1, positive = loose).
        monetary_base_score: Central bank balance sheet score.
        credit_market_score: Credit conditions score.
        currency_score: Dollar/currency liquidity score.
        cross_border_score: Capital flow score.
        confidence: Analysis confidence (0-1).
        risk_asset_impact: Expected impact on risk assets (-1 to 1).
        details: Additional analysis details.
        timestamp: Analysis timestamp.
    """
    condition: LiquidityCondition
    trend: LiquidityTrend
    composite_score: float = 0.0
    monetary_base_score: float = 0.0
    credit_market_score: float = 0.0
    currency_score: float = 0.0
    cross_border_score: float = 0.0
    confidence: float = 0.5
    risk_asset_impact: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_accommodative(self) -> bool:
        return self.condition in (
            LiquidityCondition.LOOSE,
            LiquidityCondition.EXTREMELY_LOOSE,
            LiquidityCondition.SLIGHTLY_LOOSE,
        )

    @property
    def is_restrictive(self) -> bool:
        return self.condition in (
            LiquidityCondition.TIGHT,
            LiquidityCondition.EXTREMELY_TIGHT,
            LiquidityCondition.SLIGHTLY_TIGHT,
        )

    @property
    def is_favorable_for_risk(self) -> bool:
        return self.risk_asset_impact > 0.2

    @property
    def summary(self) -> str:
        return f"{self.condition.value} ({self.trend.value}, score: {self.composite_score:+.2f})"


class LiquidityEngine:
    """Analyzes global liquidity conditions.

    Evaluates liquidity across four dimensions:
    1. Monetary base: central bank balance sheets, reserve levels
    2. Credit markets: spreads, lending conditions, bond market depth
    3. Currency: USD strength, FX reserves, EM currency stress
    4. Cross-border: capital flows, carry trade activity, global M2
    """

    # Dimension weights for composite score
    _DIMENSION_WEIGHTS: dict[str, float] = {
        "monetary_base": 0.35,
        "credit_market": 0.30,
        "currency": 0.20,
        "cross_border": 0.15,
    }

    # Indicator mapping for each dimension
    _MONETARY_BASE_INDICATORS = {
        "Fed_Balance_Sheet": 0.25,
        "ECB_Balance_Sheet": 0.20,
        "BOJ_Balance_Sheet": 0.15,
        "M2_Growth": 0.25,
        "Reserve_Balances": 0.15,
    }

    _CREDIT_MARKET_INDICATORS = {
        "HY_Spread": 0.25,           # High-yield spread (inverse)
        "IG_Spread": 0.20,           # Investment-grade spread (inverse)
        "TED_Spread": 0.15,          # Interbank stress
        "Commercial_Paper_Spread": 0.10,
        "Bank_Lending_Survey": 0.15,
        "Bond_Market_Depth": 0.15,
    }

    _CURRENCY_INDICATORS = {
        "DXY": 0.30,                 # Dollar index (inverse for global liquidity)
        "EM_FX_Index": 0.25,
        "FX_Volatility": 0.20,
        "Carry_Trade_Index": 0.15,
        "Central_Bank_Swap_Lines": 0.10,
    }

    _CROSS_BORDER_INDICATORS = {
        "Global_M2": 0.30,
        "Capital_Flows_EM": 0.25,
        "Cross_Border_Lending": 0.20,
        "FDI_Flows": 0.15,
        "Portfolio_Flows": 0.10,
    }

    # Credit spread thresholds (bps)
    _HY_SPREAD_TIGHT = 300
    _HY_SPREAD_WIDE = 600
    _IG_SPREAD_TIGHT = 80
    _IG_SPREAD_WIDE = 200
    _TED_SPREAD_NORMAL = 30
    _TED_SPREAD_STRESSED = 60

    def __init__(self):
        self._history: list[LiquidityAnalysis] = []

    def analyze(self, snapshot: MacroDataSnapshot) -> LiquidityAnalysis:
        """Analyze liquidity from a macro data snapshot.

        Args:
            snapshot: Current macro data snapshot.

        Returns:
            LiquidityAnalysis with condition, trend, and component scores.
        """
        # 1. Compute dimension scores
        monetary = self._compute_monetary_base_score(snapshot)
        credit = self._compute_credit_market_score(snapshot)
        currency = self._compute_currency_score(snapshot)
        cross_border = self._compute_cross_border_score(snapshot)

        # 2. Composite score
        composite = (
            monetary * self._DIMENSION_WEIGHTS["monetary_base"] +
            credit * self._DIMENSION_WEIGHTS["credit_market"] +
            currency * self._DIMENSION_WEIGHTS["currency"] +
            cross_border * self._DIMENSION_WEIGHTS["cross_border"]
        )

        # 3. Classify condition
        condition = self._classify_condition(composite)

        # 4. Determine trend from historical comparison
        trend = self._determine_trend(composite)

        # 5. Risk asset impact
        impact = self._compute_risk_impact(composite, credit, monetary)

        analysis = LiquidityAnalysis(
            condition=condition,
            trend=trend,
            composite_score=composite,
            monetary_base_score=monetary,
            credit_market_score=credit,
            currency_score=currency,
            cross_border_score=cross_border,
            confidence=self._compute_confidence(snapshot),
            risk_asset_impact=impact,
            details={
                "dimensions": {
                    "monetary_base": monetary,
                    "credit_market": credit,
                    "currency": currency,
                    "cross_border": cross_border,
                },
            },
        )

        self._history.append(analysis)
        return analysis

    def analyze_from_dict(self, data: dict[str, float]) -> LiquidityAnalysis:
        """Analyze from a simple data dict.

        Convenience method for testing.

        Args:
            data: Dict mapping indicator names to values.

        Returns:
            LiquidityAnalysis result.
        """
        from .data import IndicatorCategory

        snapshot = MacroDataSnapshot()
        for name, value in data.items():
            indicator = MacroIndicator(
                name=name,
                value=value,
                category=IndicatorCategory.MONETARY,
            )
            snapshot.add(indicator)
        return self.analyze(snapshot)

    def get_history(self) -> list[LiquidityAnalysis]:
        """Get historical liquidity analyses."""
        return list(self._history)

    # ── Private helpers ─────────────────────────────────────────────

    def _compute_monetary_base_score(self, snapshot: MacroDataSnapshot) -> float:
        """Compute central bank balance sheet / money supply score."""
        return self._weighted_normalized_score(
            snapshot, self._MONETARY_BASE_INDICATORS, invert=False,
        )

    def _compute_credit_market_score(self, snapshot: MacroDataSnapshot) -> float:
        """Compute credit market conditions score.

        Credit spreads are inverted: wider spreads = tighter liquidity.
        """
        total_weight = 0.0
        weighted_sum = 0.0

        # HY spread — normalize: 300-600 bps range
        hy = snapshot.get("HY_Spread")
        if hy is not None:
            w = self._CREDIT_MARKET_INDICATORS["HY_Spread"]
            signal = self._normalize_in_range(
                hy.value, self._HY_SPREAD_TIGHT, self._HY_SPREAD_WIDE, invert=True,
            )
            weighted_sum += signal * w
            total_weight += w

        # IG spread
        ig = snapshot.get("IG_Spread")
        if ig is not None:
            w = self._CREDIT_MARKET_INDICATORS["IG_Spread"]
            signal = self._normalize_in_range(
                ig.value, self._IG_SPREAD_TIGHT, self._IG_SPREAD_WIDE, invert=True,
            )
            weighted_sum += signal * w
            total_weight += w

        # TED spread
        ted = snapshot.get("TED_Spread")
        if ted is not None:
            w = self._CREDIT_MARKET_INDICATORS["TED_Spread"]
            signal = self._normalize_in_range(
                ted.value, self._TED_SPREAD_NORMAL, self._TED_SPREAD_STRESSED, invert=True,
            )
            weighted_sum += signal * w
            total_weight += w

        # Other indicators
        for name in ("Commercial_Paper_Spread", "Bank_Lending_Survey", "Bond_Market_Depth"):
            ind = snapshot.get(name)
            if ind is not None:
                w = self._CREDIT_MARKET_INDICATORS[name]
                weighted_sum += self._simple_signal(ind) * w
                total_weight += w

        if total_weight == 0:
            return 0.0
        return max(-1.0, min(1.0, weighted_sum / total_weight))

    def _compute_currency_score(self, snapshot: MacroDataSnapshot) -> float:
        """Compute currency liquidity score.

        Strong dollar = tighter global liquidity (inverted).
        """
        total_weight = 0.0
        weighted_sum = 0.0

        # DXY — invert: strong USD = tighter global liquidity
        dxy = snapshot.get("DXY")
        if dxy is not None:
            w = self._CURRENCY_INDICATORS["DXY"]
            # DXY 90-110 range typical
            signal = self._normalize_in_range(dxy.value, 90, 110, invert=True)
            weighted_sum += signal * w
            total_weight += w

        # EM FX Index
        em_fx = snapshot.get("EM_FX_Index")
        if em_fx is not None:
            w = self._CURRENCY_INDICATORS["EM_FX_Index"]
            weighted_sum += self._simple_signal(em_fx) * w
            total_weight += w

        # Other indicators
        for name in ("FX_Volatility", "Carry_Trade_Index", "Central_Bank_Swap_Lines"):
            ind = snapshot.get(name)
            if ind is not None:
                w = self._CURRENCY_INDICATORS[name]
                # FX Volatility is inverted
                invert = name == "FX_Volatility"
                signal = self._simple_signal(ind, invert=invert)
                weighted_sum += signal * w
                total_weight += w

        if total_weight == 0:
            return 0.0
        return max(-1.0, min(1.0, weighted_sum / total_weight))

    def _compute_cross_border_score(self, snapshot: MacroDataSnapshot) -> float:
        """Compute cross-border capital flow score."""
        return self._weighted_normalized_score(
            snapshot, self._CROSS_BORDER_INDICATORS, invert=False,
        )

    def _weighted_normalized_score(self, snapshot: MacroDataSnapshot,
                                   weights: dict[str, float],
                                   invert: bool = False) -> float:
        """Generic weighted score from indicator weights."""
        total_weight = 0.0
        weighted_sum = 0.0

        for name, weight in weights.items():
            ind = snapshot.get(name)
            if ind is not None:
                weighted_sum += self._simple_signal(ind, invert) * weight
                total_weight += weight

        if total_weight == 0:
            return 0.0
        return max(-1.0, min(1.0, weighted_sum / total_weight))

    @staticmethod
    def _simple_signal(indicator: MacroIndicator,
                       invert: bool = False) -> float:
        """Convert indicator to simple signal using change if available."""
        if indicator.change is not None and indicator.change_pct is not None:
            signal = min(1.0, max(-1.0, indicator.change_pct / 3.0))
        else:
            # Use absolute value normalized to -1..1
            signal = min(1.0, max(-1.0, indicator.value / 10.0))
        return -signal if invert else signal

    @staticmethod
    def _normalize_in_range(value: float, low: float, high: float,
                            invert: bool = False) -> float:
        """Normalize a value in [low, high] to [-1, 1].

        low  → +1 (best case, e.g. tight spread)
        high → -1 (worst case, e.g. wide spread)
        If invert=False, low→-1, high→+1.
        """
        if high == low:
            return 0.0
        normalized = 2.0 * (value - low) / (high - low) - 1.0
        normalized = max(-1.0, min(1.0, normalized))
        return -normalized if invert else normalized

    @staticmethod
    def _classify_condition(score: float) -> LiquidityCondition:
        """Classify liquidity condition from composite score."""
        if score > 0.8:
            return LiquidityCondition.EXTREMELY_LOOSE
        elif score > 0.4:
            return LiquidityCondition.LOOSE
        elif score > 0.15:
            return LiquidityCondition.SLIGHTLY_LOOSE
        elif score > -0.15:
            return LiquidityCondition.NEUTRAL
        elif score > -0.4:
            return LiquidityCondition.SLIGHTLY_TIGHT
        elif score > -0.8:
            return LiquidityCondition.TIGHT
        else:
            return LiquidityCondition.EXTREMELY_TIGHT

    def _determine_trend(self, current_score: float) -> LiquidityTrend:
        """Determine liquidity trend from historical comparison."""
        if len(self._history) < 2:
            return LiquidityTrend.STABLE

        prev = self._history[-1].composite_score
        diff = current_score - prev

        if diff > 0.2:
            return LiquidityTrend.RAPIDLY_EASING
        elif diff > 0.08:
            return LiquidityTrend.EASING
        elif diff > 0.02:
            return LiquidityTrend.SLIGHTLY_EASING
        elif diff > -0.02:
            return LiquidityTrend.STABLE
        elif diff > -0.08:
            return LiquidityTrend.SLIGHTLY_TIGHTENING
        elif diff > -0.2:
            return LiquidityTrend.TIGHTENING
        else:
            return LiquidityTrend.RAPIDLY_TIGHTENING

    @staticmethod
    def _compute_risk_impact(composite: float, credit: float,
                             monetary: float) -> float:
        """Compute expected impact on risk assets."""
        # Risk assets most sensitive to credit conditions and monetary base
        return (composite * 0.5 + credit * 0.30 + monetary * 0.20)

    def _compute_confidence(self, snapshot: MacroDataSnapshot) -> float:
        """Compute analysis confidence based on data completeness."""
        all_indicators = set()
        for mapping in (self._MONETARY_BASE_INDICATORS, self._CREDIT_MARKET_INDICATORS,
                         self._CURRENCY_INDICATORS, self._CROSS_BORDER_INDICATORS):
            all_indicators.update(mapping.keys())

        available = sum(1 for name in all_indicators if snapshot.get(name))
        return min(0.95, max(0.3, available / len(all_indicators)))


__all__ = [
    "LiquidityCondition",
    "LiquidityTrend",
    "LiquidityAnalysis",
    "LiquidityEngine",
]
