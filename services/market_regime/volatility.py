"""Volatility Regime Detector – identify volatility environment."""

from typing import Any, Dict, List, Optional


class VolatilityDetector:
    """Detects market volatility regimes.

    Analyzes:
    - VIX / implied volatility level
    - Historical volatility (realized vol)
    - Volatility trend (increasing/decreasing)
    - Volatility regime transitions

    Outputs a volatility classification that drives risk management decisions.
    """

    # Volatility regime levels
    EXTREMELY_LOW = "EXTREMELY_LOW"
    LOW = "LOW"
    NORMAL = "NORMAL"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    EXTREME = "EXTREME"

    VOL_REGIMES = [EXTREMELY_LOW, LOW, NORMAL, ELEVATED, HIGH, EXTREME]

    # VIX-based thresholds (configurable)
    VIX_EXTREMELY_LOW = 12.0
    VIX_LOW = 15.0
    VIX_NORMAL_HIGH = 20.0
    VIX_ELEVATED = 25.0
    VIX_HIGH = 30.0
    # > 30 = EXTREME

    def __init__(self,
                 vix_low: float = 15.0,
                 vix_elevated: float = 25.0,
                 vix_high: float = 30.0):
        self.VIX_LOW = vix_low
        self.VIX_ELEVATED = vix_elevated
        self.VIX_HIGH = vix_high

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, value: float) -> str:
        """Detect volatility regime from a VIX/volatility value (legacy interface).

        Returns "HIGH", "NORMAL", or "LOW".
        """
        if value > self.VIX_HIGH:
            return "HIGH"
        elif value > self.VIX_ELEVATED:
            return "ELEVATED"
        elif value < self.VIX_LOW:
            return "LOW"
        return "NORMAL"

    def classify_volatility(self, vix: Optional[float] = None,
                            historical_vol: Optional[float] = None,
                            vol_percentile: Optional[float] = None,
                            vol_change: Optional[float] = None) -> str:
        """Classify volatility regime from multiple inputs.

        Args:
            vix: Current VIX or implied volatility index value
            historical_vol: Realized historical volatility (annualized %)
            vol_percentile: Current vol as percentile of 1-year range (0-100)
            vol_change: Recent change in volatility (positive = increasing)

        Returns:
            Volatility regime string
        """
        # Primary: VIX-based
        if vix is not None:
            if vix > self.VIX_HIGH:
                return self.EXTREME
            elif vix > self.VIX_ELEVATED:
                return self.HIGH
            elif vix > self.VIX_NORMAL_HIGH:
                return self.ELEVATED
            elif vix < self.VIX_EXTREMELY_LOW:
                return self.EXTREMELY_LOW
            elif vix < self.VIX_LOW:
                return self.LOW

        # Secondary: historical vol
        if historical_vol is not None:
            if historical_vol > 50:
                return self.EXTREME
            elif historical_vol > 35:
                return self.HIGH
            elif historical_vol > 25:
                return self.ELEVATED
            elif historical_vol < 8:
                return self.EXTREMELY_LOW
            elif historical_vol < 12:
                return self.LOW

        # Tertiary: percentile
        if vol_percentile is not None:
            if vol_percentile > 90:
                return self.EXTREME
            elif vol_percentile > 75:
                return self.HIGH
            elif vol_percentile > 60:
                return self.ELEVATED
            elif vol_percentile < 10:
                return self.EXTREMELY_LOW
            elif vol_percentile < 25:
                return self.LOW

        return self.NORMAL

    def volatility_level(self, vix: Optional[float] = None,
                         historical_vol: Optional[float] = None) -> float:
        """Return a normalized volatility level (0.0 to 1.0)."""
        if vix is not None:
            # Map VIX to 0-1 range (0=low, 1=extreme)
            # VIX 10 → 0.0, VIX 40+ → 1.0
            return round(min(1.0, max(0.0, (vix - 10) / 30)), 3)

        if historical_vol is not None:
            return round(min(1.0, max(0.0, (historical_vol - 5) / 55)), 3)

        return 0.5

    def detect_with_details(self, vix: Optional[float] = None,
                            historical_vol: Optional[float] = None,
                            vol_percentile: Optional[float] = None,
                            vol_change: Optional[float] = None) -> dict:
        """Full volatility detection with details."""
        regime = self.classify_volatility(vix, historical_vol, vol_percentile, vol_change)
        level = self.volatility_level(vix, historical_vol)

        # Determine if volatility is accelerating or decelerating
        vol_trend = "stable"
        if vol_change is not None:
            if vol_change > 20:
                vol_trend = "spiking"
            elif vol_change > 5:
                vol_trend = "rising"
            elif vol_change < -20:
                vol_trend = "collapsing"
            elif vol_change < -5:
                vol_trend = "falling"

        return {
            "regime": regime,
            "level": level,
            "vol_trend": vol_trend,
            "vix": vix,
            "historical_vol": historical_vol,
        }

    # ------------------------------------------------------------------
    # Regime mapping
    # ------------------------------------------------------------------

    def to_macro_signal(self, regime: str) -> str:
        """Map volatility regime to macro risk signal."""
        if regime in (self.EXTREME, self.HIGH):
            return "RISK_OFF"
        elif regime == self.ELEVATED:
            return "FLIGHT_TO_QUALITY"
        else:
            return "RISK_ON"

    def suggested_exposure(self, regime: str) -> float:
        """Suggest equity exposure based on volatility regime."""
        exposure_map = {
            self.EXTREMELY_LOW: 1.0,
            self.LOW: 1.0,
            self.NORMAL: 0.9,
            self.ELEVATED: 0.7,
            self.HIGH: 0.5,
            self.EXTREME: 0.3,
        }
        return exposure_map.get(regime, 0.8)
