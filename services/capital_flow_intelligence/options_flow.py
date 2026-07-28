"""Options Flow Analyzer.

Analyzes options market capital flows including call/put volume,
large block trades, gamma exposure, and unusual options activity
to detect institutional positioning and sentiment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .record import CapitalFlowRecord, FlowSource, FlowDirection


@dataclass
class OptionsFlowResult:
    """Result of options flow analysis.

    Attributes:
        asset: Underlying asset.
        call_volume: Total call option volume.
        put_volume: Total put option volume.
        put_call_ratio: Put/call volume ratio.
        bias: Directional bias (bullish/neutral/bearish).
        confidence: Analysis confidence [0.0, 1.0].
        large_trades: Number of large block trades detected.
        gamma_exposure: Estimated gamma exposure.
        unusual_activity: Whether unusual options activity detected.
        description: Human-readable summary.
        timestamp: Analysis timestamp.
    """

    asset: str = ""
    call_volume: float = 0.0
    put_volume: float = 0.0
    put_call_ratio: float = 1.0
    bias: str = "neutral"
    confidence: float = 0.5
    large_trades: int = 0
    gamma_exposure: float = 0.0
    unusual_activity: bool = False
    description: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_bullish(self) -> bool:
        return self.bias == "bullish"

    @property
    def is_bearish(self) -> bool:
        return self.bias == "bearish"

    @property
    def is_strong_bias(self) -> bool:
        return self.bias in ("bullish", "bearish") and self.confidence >= 0.6

    @property
    def has_large_trades(self) -> bool:
        return self.large_trades > 0


class OptionsFlowAnalyzer:
    """Analyzes options market flow for institutional positioning signals.

    Monitors call/put volume, put/call ratio, large block trades,
    gamma exposure, and unusual options activity to detect informed
    capital flow through the options market.

    Attributes:
        call_put_history: Historical put/call ratios per asset.
        trade_history: Historical trade data.
        pcr_bullish_threshold: Put/call ratio below which = bullish.
        pcr_bearish_threshold: Put/call ratio above which = bearish.
        large_trade_threshold: Minimum value to classify as large trade.
    """

    def __init__(self) -> None:
        self.call_put_history: dict[str, list[float]] = {}
        self.trade_history: dict[str, list[dict[str, Any]]] = {}
        self.pcr_bullish_threshold: float = 0.7
        self.pcr_bearish_threshold: float = 1.3
        self.large_trade_threshold: float = 1000000.0  # $1M

    # --- Analysis ---

    def analyze(
        self,
        asset: str,
        options: dict[str, Any] | None = None,
        flows: list[CapitalFlowRecord] | None = None,
    ) -> dict[str, Any]:
        """Analyze options flow for an asset.

        Args:
            asset: Underlying asset ticker.
            options: Optional raw options data dict.
            flows: Optional capital flow records.

        Returns:
            Dict with options flow analysis.
        """
        call_vol = 0.0
        put_vol = 0.0
        large_trades = 0

        if flows:
            call_vol = sum(abs(f.amount) for f in flows if f.is_inflow)
            put_vol = sum(abs(f.amount) for f in flows if f.is_outflow)
            large_trades = sum(1 for f in flows if abs(f.amount) >= self.large_trade_threshold)

        # Compute put/call ratio
        # All-puts = very high PCR (bearish), all-calls = very low PCR (bullish)
        if call_vol > 0:
            pcr = put_vol / call_vol
        elif put_vol > 0:
            pcr = 2.0  # All puts = extreme bearish
        else:
            pcr = 1.0  # No flow data

        # Determine bias
        if pcr < self.pcr_bullish_threshold:
            bias = "bullish"
        elif pcr > self.pcr_bearish_threshold:
            bias = "bearish"
        else:
            bias = "neutral"

        # Unusual activity
        unusual = abs(pcr - 1.0) > 0.5 or large_trades >= 3

        # Track history
        self.call_put_history.setdefault(asset, []).append(pcr)

        return {
            "asset": asset,
            "bias": bias,
            "put_call_ratio": pcr,
            "call_volume": call_vol,
            "put_volume": put_vol,
            "large_trades": large_trades,
            "unusual_activity": unusual,
        }

    def analyze_full(
        self,
        asset: str,
        options: dict[str, Any] | None = None,
        flows: list[CapitalFlowRecord] | None = None,
    ) -> OptionsFlowResult:
        """Full options flow analysis with detailed result.

        Args:
            asset: Underlying asset ticker.
            options: Optional raw options data.
            flows: Optional capital flow records.

        Returns:
            OptionsFlowResult with complete analysis.
        """
        basic = self.analyze(asset, options, flows)
        pcr = basic.get("put_call_ratio", 1.0)

        # Gamma exposure estimation
        gamma = self._estimate_gamma(asset, pcr, flows)

        # Confidence
        confidence = self._compute_confidence(asset, flows or [], pcr, basic.get("large_trades", 0))

        # Description
        description = self._generate_description(
            asset,
            basic.get("bias", "neutral"),
            pcr,
            basic.get("large_trades", 0),
            basic.get("unusual_activity", False),
        )

        return OptionsFlowResult(
            asset=asset,
            call_volume=basic.get("call_volume", 0.0),
            put_volume=basic.get("put_volume", 0.0),
            put_call_ratio=pcr,
            bias=basic.get("bias", "neutral"),
            confidence=confidence,
            large_trades=basic.get("large_trades", 0),
            gamma_exposure=gamma,
            unusual_activity=basic.get("unusual_activity", False),
            description=description,
        )

    # --- History Analysis ---

    def get_pcr_trend(self, asset: str) -> str:
        """Get put/call ratio trend.

        Args:
            asset: Asset ticker.

        Returns:
            'rising', 'falling', or 'stable'.
        """
        history = self.call_put_history.get(asset, [])
        if len(history) < 2:
            return "stable"

        mid = len(history) // 2
        first_half = sum(history[:mid]) / mid
        second_half = sum(history[mid:]) / (len(history) - mid)

        diff = second_half - first_half
        if diff > 0.1:
            return "rising"
        elif diff < -0.1:
            return "falling"
        return "stable"

    def detect_unusual_options_activity(
        self, asset: str, flows: list[CapitalFlowRecord]
    ) -> list[dict[str, Any]]:
        """Detect unusual options flow patterns.

        Args:
            asset: Asset ticker.
            flows: Flow records.

        Returns:
            List of unusual activity events.
        """
        unusual: list[dict[str, Any]] = []

        large_flows = [f for f in flows if abs(f.amount) >= self.large_trade_threshold]
        for f in large_flows:
            unusual.append({
                "asset": asset,
                "amount": f.amount,
                "direction": f.direction.value,
                "description": f"Large trade: {f.amount:,.0f} ({f.direction.value})",
            })

        return unusual

    # --- Internal ---

    def _estimate_gamma(
        self,
        asset: str,
        pcr: float,
        flows: list[CapitalFlowRecord] | None,
    ) -> float:
        """Estimate gamma exposure from options flow.

        Args:
            asset: Asset ticker.
            pcr: Put/call ratio.
            flows: Flow records.

        Returns:
            Estimated gamma exposure (positive=dealers long gamma).
        """
        # Simplified: gamma is negative when PCR is high (dealers short gamma)
        base_gamma = (1.0 - pcr) * 100.0
        if flows:
            large_sum = sum(f.amount for f in flows if abs(f.amount) >= self.large_trade_threshold)
            base_gamma += large_sum * 0.0001
        return base_gamma

    def _compute_confidence(
        self,
        asset: str,
        flows: list[CapitalFlowRecord],
        pcr: float,
        large_trades: int,
    ) -> float:
        """Compute analysis confidence."""
        confidence = 0.3

        # Extreme PCR = higher confidence
        if abs(pcr - 1.0) > 0.5:
            confidence += 0.3
        elif abs(pcr - 1.0) > 0.3:
            confidence += 0.15

        # More flow data = higher confidence
        if len(flows) >= 10:
            confidence += 0.2

        # Large trades increase confidence
        if large_trades >= 3:
            confidence += 0.2
        elif large_trades >= 1:
            confidence += 0.1

        return min(1.0, confidence)

    def _generate_description(
        self,
        asset: str,
        bias: str,
        pcr: float,
        large_trades: int,
        unusual: bool,
    ) -> str:
        """Generate human-readable description."""
        parts = [f"{asset}: options flow {bias} (PCR={pcr:.2f})"]

        if large_trades:
            parts.append(f"({large_trades} large trade(s))")

        if unusual:
            parts.append("[UNUSUAL ACTIVITY]")

        return " ".join(parts)

    def clear(self) -> None:
        """Reset analyzer state."""
        self.call_put_history.clear()
        self.trade_history.clear()
