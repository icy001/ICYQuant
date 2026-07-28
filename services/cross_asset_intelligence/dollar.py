"""Dollar Intelligence Engine.

Analyzes USD cycles and their cross-asset impacts including effects on
gold, commodities, emerging markets, and risk assets. The dollar is
the central hub of the global financial system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .relationship import DollarTrend


@dataclass
class DollarResult:
    """Result of dollar intelligence analysis.

    Attributes:
        dxy: DXY index level.
        trend: Dollar trend classification.
        trend_strength: Trend strength [0.0, 1.0].
        impacts: Cross-asset impact assessments.
        confidence: Analysis confidence.
        description: Human-readable summary.
        timestamp: Analysis timestamp.
    """

    dxy: float = 100.0
    trend: DollarTrend = DollarTrend.STABLE
    trend_strength: float = 0.5
    impacts: dict[str, str] = field(default_factory=dict)
    confidence: float = 0.5
    description: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_weakening(self) -> bool:
        return self.trend in (DollarTrend.DEPRECIATION, DollarTrend.STRONG_DEPRECIATION)

    @property
    def is_strengthening(self) -> bool:
        return self.trend in (DollarTrend.APPRECIATION, DollarTrend.STRONG_APPRECIATION)

    @property
    def gold_signal(self) -> str:
        impact = self.impacts.get("gold", "")
        if impact:
            return impact
        if self.trend in (DollarTrend.DEPRECIATION, DollarTrend.STRONG_DEPRECIATION):
            return "bullish"
        elif self.trend in (DollarTrend.APPRECIATION, DollarTrend.STRONG_APPRECIATION):
            return "bearish"
        return "neutral"

    @property
    def commodity_signal(self) -> str:
        impact = self.impacts.get("commodities", "")
        if impact:
            return impact
        if self.trend in (DollarTrend.DEPRECIATION, DollarTrend.STRONG_DEPRECIATION):
            return "bullish"
        elif self.trend in (DollarTrend.APPRECIATION, DollarTrend.STRONG_APPRECIATION):
            return "bearish"
        return "neutral"

    @property
    def emerging_market_signal(self) -> str:
        impact = self.impacts.get("emerging_markets", "")
        if impact:
            return impact
        if self.trend in (DollarTrend.DEPRECIATION, DollarTrend.STRONG_DEPRECIATION):
            return "bullish"
        elif self.trend in (DollarTrend.APPRECIATION, DollarTrend.STRONG_APPRECIATION):
            return "bearish"
        return "neutral"


class DollarIntelligenceEngine:
    """Analyzes USD dynamics and cross-asset impacts.

    Evaluates dollar strength/weakness trends and projects impacts
    on gold, commodities, emerging markets, and global risk assets.

    Attributes:
        dxy_history: Rolling DXY history.
        trend_threshold: Minimum DXY change for trend signal.
    """

    def __init__(self) -> None:
        self.dxy_history: list[float] = []
        self.trend_threshold: float = 1.0  # DXY points

    # --- Analysis ---

    def analyze(self, dxy: float, real_yield: float = 1.0, fed_stance: str = "neutral") -> dict[str, Any]:
        """Analyze dollar trend and cross-asset impacts.

        Args:
            dxy: DXY index value.
            real_yield: US real yield.
            fed_stance: Fed policy stance (dovish/neutral/hawkish).

        Returns:
            Dict with trend and impact analysis.
        """
        result = self.analyze_full(dxy, real_yield, fed_stance)
        return {
            "trend": result.trend.value.split("_")[-1].upper(),
            "dxy": result.dxy,
            "description": result.description,
            "impacts": result.impacts,
        }

    def analyze_full(self, dxy: float, real_yield: float = 1.0, fed_stance: str = "neutral") -> DollarResult:
        """Full dollar intelligence analysis.

        Args:
            dxy: DXY index value.
            real_yield: US real yield.
            fed_stance: Fed policy stance.

        Returns:
            DollarResult with comprehensive analysis.
        """
        self.dxy_history.append(dxy)
        if len(self.dxy_history) > 200:
            self.dxy_history = self.dxy_history[-200:]

        trend = self._classify_trend(dxy)
        strength = self._compute_strength(trend, real_yield, fed_stance)
        impacts = self._project_impacts(trend)
        confidence = self._compute_confidence(trend, strength)
        description = self._generate_description(trend, dxy, impacts)

        return DollarResult(
            dxy=dxy,
            trend=trend,
            trend_strength=strength,
            impacts=impacts,
            confidence=confidence,
            description=description,
        )

    # --- Impact Projections ---

    def get_gold_outlook(self, dxy: float) -> str:
        """Get gold outlook based on dollar trend."""
        trend = self._classify_trend(dxy)
        if trend in (DollarTrend.STRONG_DEPRECIATION, DollarTrend.DEPRECIATION):
            return "bullish"
        elif trend in (DollarTrend.STRONG_APPRECIATION, DollarTrend.APPRECIATION):
            return "bearish"
        return "neutral"

    def get_commodity_outlook(self, dxy: float) -> str:
        """Get commodity outlook based on dollar trend."""
        trend = self._classify_trend(dxy)
        if trend in (DollarTrend.STRONG_DEPRECIATION,):
            return "strongly_bullish"
        elif trend == DollarTrend.DEPRECIATION:
            return "bullish"
        elif trend in (DollarTrend.STRONG_APPRECIATION,):
            return "bearish"
        elif trend == DollarTrend.APPRECIATION:
            return "slightly_bearish"
        return "neutral"

    def get_em_outlook(self, dxy: float) -> str:
        """Get emerging markets outlook based on dollar trend."""
        trend = self._classify_trend(dxy)
        if trend in (DollarTrend.STRONG_DEPRECIATION,):
            return "strongly_bullish"
        elif trend == DollarTrend.DEPRECIATION:
            return "bullish"
        elif trend in (DollarTrend.STRONG_APPRECIATION,):
            return "bearish"
        elif trend == DollarTrend.APPRECIATION:
            return "slightly_bearish"
        return "neutral"

    def get_risk_asset_outlook(self, dxy: float) -> str:
        """Get risk asset outlook based on dollar trend."""
        trend = self._classify_trend(dxy)
        if trend in (DollarTrend.STRONG_DEPRECIATION, DollarTrend.DEPRECIATION):
            return "favorable"
        elif trend in (DollarTrend.STRONG_APPRECIATION,):
            return "unfavorable"
        elif trend == DollarTrend.APPRECIATION:
            return "cautious"
        return "neutral"

    # --- History ---

    def get_trend(self, window: int = 20) -> str:
        """Get DXY trend direction over window."""
        if len(self.dxy_history) < 2:
            return "stable"
        recent = self.dxy_history[-window:] if len(self.dxy_history) >= window else self.dxy_history
        mid = len(recent) // 2
        first = sum(recent[:mid]) / mid
        second = sum(recent[mid:]) / (len(recent) - mid)
        diff = second - first
        if diff > self.trend_threshold:
            return "rising"
        elif diff < -self.trend_threshold:
            return "falling"
        return "stable"

    # --- Internal ---

    def _classify_trend(self, dxy: float) -> DollarTrend:
        if len(self.dxy_history) < 5:
            return DollarTrend.STABLE
        recent = self.dxy_history[-20:] if len(self.dxy_history) >= 20 else self.dxy_history
        avg = sum(recent) / len(recent)
        change_pct = (dxy - avg) / avg * 100
        if change_pct > 3.0:
            return DollarTrend.STRONG_APPRECIATION
        elif change_pct > 1.0:
            return DollarTrend.APPRECIATION
        elif change_pct < -3.0:
            return DollarTrend.STRONG_DEPRECIATION
        elif change_pct < -1.0:
            return DollarTrend.DEPRECIATION
        return DollarTrend.STABLE

    def _compute_strength(self, trend: DollarTrend, real_yield: float, fed_stance: str) -> float:
        base = 0.5
        if trend in (DollarTrend.STRONG_APPRECIATION, DollarTrend.STRONG_DEPRECIATION):
            base += 0.3
        if trend in (DollarTrend.APPRECIATION, DollarTrend.STRONG_APPRECIATION) and real_yield > 1.5:
            base += 0.1
        if trend in (DollarTrend.DEPRECIATION, DollarTrend.STRONG_DEPRECIATION) and fed_stance == "dovish":
            base += 0.1
        return min(1.0, base)

    def _project_impacts(self, trend: DollarTrend) -> dict[str, str]:
        if trend in (DollarTrend.STRONG_DEPRECIATION, DollarTrend.DEPRECIATION):
            return {
                "gold": "bullish",
                "commodities": "bullish",
                "emerging_markets": "bullish",
                "risk_assets": "favorable",
                "us_exporters": "bullish",
                "crypto": "bullish",
            }
        elif trend in (DollarTrend.STRONG_APPRECIATION, DollarTrend.APPRECIATION):
            return {
                "gold": "bearish",
                "commodities": "bearish",
                "emerging_markets": "bearish",
                "risk_assets": "unfavorable",
                "us_importers": "favorable",
                "crypto": "bearish",
            }
        return {k: "neutral" for k in ("gold", "commodities", "emerging_markets", "risk_assets", "crypto")}

    def _compute_confidence(self, trend: DollarTrend, strength: float) -> float:
        confidence = 0.4
        if trend != DollarTrend.STABLE:
            confidence += 0.2
        if len(self.dxy_history) > 20:
            confidence += 0.15
        return min(1.0, confidence * strength)

    def _generate_description(self, trend: DollarTrend, dxy: float, impacts: dict[str, str]) -> str:
        trend_desc = {
            DollarTrend.STRONG_APPRECIATION: "Dollar strengthening strongly",
            DollarTrend.APPRECIATION: "Dollar appreciating",
            DollarTrend.STABLE: "Dollar stable",
            DollarTrend.DEPRECIATION: "Dollar weakening",
            DollarTrend.STRONG_DEPRECIATION: "Dollar weakening significantly",
        }
        base = trend_desc.get(trend, "Unknown")
        gold = impacts.get("gold", "neutral")
        return f"{base} (DXY={dxy:.1f}) → Gold: {gold}"

    def clear(self) -> None:
        self.dxy_history.clear()
