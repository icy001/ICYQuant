"""Market Analysis Assistant – real-time market analysis and explanation."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class MarketAnalysis:
    """Represents a market analysis result for a given symbol.

    Captures trend direction, risk level, supporting factors, and a
    human-readable summary for trader consumption.
    """

    symbol: str
    trend: str  # "bullish", "bearish", "neutral"
    risk_level: str  # "low", "medium", "high"
    factors: List[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "trend": self.trend,
            "risk_level": self.risk_level,
            "factors": self.factors,
            "summary": self.summary,
        }


class MarketAnalyst:
    """Performs multi-factor market analysis for a given symbol.

    Aggregates price momentum, volume confirmation, volatility, and
    sector/macro signals to produce a concise market analysis.
    """

    def analyze(
        self,
        symbol: str,
        price_momentum: float = 0.0,
        volume_confirmation: float = 0.0,
        volatility: float = 0.0,
        sector_strength: float = 0.0,
        news_sentiment: Optional[float] = None,
    ) -> MarketAnalysis:
        """Run multi-factor analysis and return a MarketAnalysis."""
        factors: List[str] = []
        score = 0.0

        # Price momentum
        if price_momentum > 0.5:
            factors.append("Price Momentum ↑")
            score += price_momentum
        elif price_momentum < -0.5:
            factors.append("Price Momentum ↓")
            score += price_momentum

        # Volume confirmation
        if volume_confirmation > 0.3:
            factors.append("Volume Confirmation ↑")
            score += volume_confirmation
        elif volume_confirmation < -0.3:
            factors.append("Volume Divergence ↓")
            score += volume_confirmation

        # Volatility assessment
        if volatility > 0.7:
            factors.append("Volatility Elevated")
        elif volatility < 0.3:
            factors.append("Volatility Normal")

        # Sector strength
        if sector_strength > 0.4:
            factors.append("Sector Strength ↑")
            score += sector_strength
        elif sector_strength < -0.4:
            factors.append("Sector Weakness ↓")
            score += sector_strength

        # News sentiment (optional)
        if news_sentiment is not None:
            if news_sentiment > 0.3:
                factors.append("News Sentiment Positive")
                score += news_sentiment * 0.5
            elif news_sentiment < -0.3:
                factors.append("News Sentiment Negative")
                score += news_sentiment * 0.5

        # Determine trend
        if score > 0.5:
            trend = "bullish"
        elif score < -0.5:
            trend = "bearish"
        else:
            trend = "neutral"

        # Risk level
        if volatility > 0.7 or abs(score) < 0.2:
            risk_level = "high"
        elif volatility > 0.4 or abs(score) < 0.5:
            risk_level = "medium"
        else:
            risk_level = "low"

        # Summary
        summary = f"{symbol}: Trend is {trend} (score={score:.2f}), risk={risk_level}."

        return MarketAnalysis(
            symbol=symbol,
            trend=trend,
            risk_level=risk_level,
            factors=factors,
            summary=summary,
        )
