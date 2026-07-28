"""Crypto Intelligence Engine.

Analyzes cryptocurrency markets (BTC, ETH, majors) as a risk appetite
barometer and cross-asset signal source. Crypto leads traditional
risk assets in liquidity cycles and provides real-time sentiment data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CryptoDominance(str, Enum):
    """Bitcoin dominance classification."""

    BTC_SEASON = "btc_season"
    ALT_SEASON = "alt_season"
    TRANSITIONING = "transitioning"


class CryptoRiskAppetite(str, Enum):
    """Crypto-derived risk appetite for global markets."""

    RISK_SEEKING = "risk_seeking"
    RISK_NEUTRAL = "risk_neutral"
    RISK_AVERSE = "risk_averse"
    EXTREME_FEAR = "extreme_fear"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class CryptoResult:
    """Result of crypto intelligence analysis.

    Attributes:
        btc_price: Bitcoin price.
        eth_price: Ethereum price.
        btc_dominance: Bitcoin market dominance percentage.
        dominance_state: BTC dominance classification.
        risk_appetite: Global risk appetite signal from crypto.
        signal: Trading signal derived from crypto.
        correlation_signal: How crypto relates to trad assets.
        description: Human-readable summary.
        confidence: Analysis confidence.
        factors: Supporting factors.
        timestamp: Analysis timestamp.
    """

    btc_price: float = 0.0
    eth_price: float = 0.0
    btc_dominance: float = 50.0
    dominance_state: CryptoDominance = CryptoDominance.TRANSITIONING
    risk_appetite: CryptoRiskAppetite = CryptoRiskAppetite.RISK_NEUTRAL
    signal: str = "NEUTRAL"
    correlation_signal: str = ""
    description: str = ""
    confidence: float = 0.5
    factors: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_bullish(self) -> bool:
        return self.signal == "BULLISH"

    @property
    def is_bearish(self) -> bool:
        return self.signal == "BEARISH"

    @property
    def is_alt_season(self) -> bool:
        return self.dominance_state == CryptoDominance.ALT_SEASON

    @property
    def is_btc_season(self) -> bool:
        return self.dominance_state == CryptoDominance.BTC_SEASON

    @property
    def is_risk_on(self) -> bool:
        return self.risk_appetite == CryptoRiskAppetite.RISK_SEEKING


class CryptoIntelligenceEngine:
    """Analyzes crypto markets for cross-asset signals.

    Evaluates BTC/ETH price action, dominance cycles, and derives
    risk appetite signals for traditional asset markets. Crypto
    often leads equity and risk asset rotations by 1-4 weeks.

    Attributes:
        btc_history: Bitcoin price history.
        eth_history: Ethereum price history.
        dominance_history: BTC dominance history.
        dominance_alt_threshold: BTC dominance threshold for alt season.
        dominance_btc_threshold: BTC dominance threshold for BTC season.
    """

    def __init__(self) -> None:
        self.btc_history: list[float] = []
        self.eth_history: list[float] = []
        self.dominance_history: list[float] = []
        self.dominance_alt_threshold: float = 45.0
        self.dominance_btc_threshold: float = 55.0
        self.trend_window: int = 20

    # --- Analysis ---

    def analyze(self, btc_price: float, eth_price: float = 0.0,
                btc_dominance: float = 50.0) -> dict[str, Any]:
        """Analyze crypto markets for cross-asset signals.

        Args:
            btc_price: Bitcoin price.
            eth_price: Ethereum price.
            btc_dominance: BTC dominance percentage.

        Returns:
            Dict with analysis results.
        """
        result = self.analyze_full(btc_price, eth_price, btc_dominance)
        return {
            "signal": result.signal,
            "risk_appetite": result.risk_appetite.value,
            "dominance_state": result.dominance_state.value,
            "btc_dominance": result.btc_dominance,
            "description": result.description,
        }

    def analyze_full(self, btc_price: float, eth_price: float = 0.0,
                     btc_dominance: float = 50.0) -> CryptoResult:
        """Full crypto intelligence analysis.

        Args:
            btc_price: Bitcoin price.
            eth_price: Ethereum price.
            btc_dominance: BTC dominance percentage.

        Returns:
            CryptoResult.
        """
        self.btc_history.append(btc_price)
        if eth_price > 0:
            self.eth_history.append(eth_price)
        self.dominance_history.append(btc_dominance)

        # Trim histories
        for hist in (self.btc_history, self.eth_history, self.dominance_history):
            if len(hist) > 200:
                hist[:] = hist[-200:]

        # Analyze components
        btc_trend = self._compute_trend(self.btc_history)
        eth_trend = self._compute_trend(self.eth_history) if self.eth_history else "stable"
        dominance_state = self._classify_dominance(btc_dominance)
        risk_appetite = self._assess_risk_appetite(btc_trend, eth_trend, dominance_state, btc_dominance)
        signal = self._derive_signal(btc_trend, eth_trend, dominance_state)
        correlation_signal = self._derive_correlation_signal(btc_trend, dominance_state)
        factors = self._collect_factors(btc_trend, eth_trend, dominance_state, btc_dominance)
        confidence = self._compute_confidence(btc_trend, dominance_state)
        description = self._generate_description(btc_price, btc_dominance, dominance_state, risk_appetite, signal)

        return CryptoResult(
            btc_price=btc_price,
            eth_price=eth_price,
            btc_dominance=btc_dominance,
            dominance_state=dominance_state,
            risk_appetite=risk_appetite,
            signal=signal,
            correlation_signal=correlation_signal,
            description=description,
            confidence=confidence,
            factors=factors,
        )

    # --- Dominance Analysis ---

    def get_dominance_cycle(self) -> str:
        """Classify the current BTC dominance cycle phase."""
        if len(self.dominance_history) < 5:
            return "unknown"
        return self._classify_dominance(self.dominance_history[-1]).value

    def is_altcoin_season(self, btc_dominance: float) -> bool:
        """Check if current conditions indicate altcoin season."""
        return btc_dominance <= self.dominance_alt_threshold

    # --- Risk Appetite ---

    def get_risk_appetite_signal(self) -> str:
        """Get crypto-derived risk appetite for traditional markets."""
        if len(self.btc_history) < 5:
            return "unknown"
        btc_trend = self._compute_trend(self.btc_history)
        dominance = self.dominance_history[-1] if self.dominance_history else 50.0
        dom_state = self._classify_dominance(dominance)
        ra = self._assess_risk_appetite(btc_trend, "stable", dom_state, dominance)
        return ra.value

    def is_crypto_leading_stocks(self) -> bool:
        """Check if crypto is leading equity markets higher."""
        if len(self.btc_history) < 10:
            return False
        btc_trend = self._compute_trend(self.btc_history)
        dominance = self.dominance_history[-1] if self.dominance_history else 50.0
        return btc_trend in ("rising", "strong_rising") and dominance < 60

    # --- Internal ---

    def _compute_trend(self, history: list[float]) -> str:
        if len(history) < 5:
            return "stable"
        recent = history[-self.trend_window:] if len(history) >= self.trend_window else history
        mid = len(recent) // 2
        first = sum(recent[:mid]) / mid
        second = sum(recent[mid:]) / (len(recent) - mid)
        if first == 0:
            return "stable"
        change = (second - first) / first * 100
        if change > 15:
            return "strong_rising"
        elif change > 5:
            return "rising"
        elif change < -15:
            return "strong_falling"
        elif change < -5:
            return "falling"
        return "stable"

    def _classify_dominance(self, dominance: float) -> CryptoDominance:
        if dominance >= self.dominance_btc_threshold:
            return CryptoDominance.BTC_SEASON
        elif dominance <= self.dominance_alt_threshold:
            return CryptoDominance.ALT_SEASON
        return CryptoDominance.TRANSITIONING

    def _assess_risk_appetite(
        self,
        btc_trend: str,
        eth_trend: str,
        dominance: CryptoDominance,
        btc_dominance: float,
    ) -> CryptoRiskAppetite:
        # Strong BTC + rising ETH = risk seeking
        if btc_trend in ("strong_rising", "rising") and eth_trend in ("strong_rising", "rising"):
            return CryptoRiskAppetite.RISK_SEEKING
        # Alt season (ETH outperforming) = risk seeking
        if dominance == CryptoDominance.ALT_SEASON:
            return CryptoRiskAppetite.RISK_SEEKING
        # Falling BTC = risk averse or fearful
        if btc_trend in ("strong_falling",):
            return CryptoRiskAppetite.EXTREME_FEAR
        if btc_trend == "falling":
            return CryptoRiskAppetite.RISK_AVERSE
        # BTC season = cautious allocation
        if dominance == CryptoDominance.BTC_SEASON and btc_trend == "stable":
            return CryptoRiskAppetite.RISK_NEUTRAL
        # Transitioning upward = risk seeking
        if btc_trend == "rising" and dominance == CryptoDominance.TRANSITIONING:
            return CryptoRiskAppetite.RISK_SEEKING
        return CryptoRiskAppetite.RISK_NEUTRAL

    def _derive_signal(self, btc_trend: str, eth_trend: str, dominance: CryptoDominance) -> str:
        # Strong bullish
        if btc_trend == "strong_rising" and eth_trend in ("strong_rising", "rising"):
            return "BULLISH"
        if btc_trend == "rising" and eth_trend == "strong_rising":
            return "BULLISH"
        # Bearish
        if btc_trend in ("strong_falling", "falling"):
            return "BEARISH"
        # Alt season = speculative but positive
        if dominance == CryptoDominance.ALT_SEASON and btc_trend != "falling":
            return "BULLISH"
        # Rising BTC alone
        if btc_trend == "rising":
            return "BULLISH"
        return "NEUTRAL"

    def _derive_correlation_signal(self, btc_trend: str, dominance: CryptoDominance) -> str:
        """How crypto action relates to traditional assets."""
        if btc_trend in ("strong_rising",) and dominance in (CryptoDominance.TRANSITIONING, CryptoDominance.ALT_SEASON):
            return "Crypto leading risk-on rotation, positive for equities"
        if btc_trend in ("strong_falling",):
            return "Crypto selling may precede risk-off in equities (1-2 week lead)"
        if dominance == CryptoDominance.BTC_SEASON:
            return "Flight to quality within crypto - cautious signal for risk assets"
        return "Crypto neutral for cross-asset signal"

    def _collect_factors(self, btc_trend: str, eth_trend: str,
                         dominance: CryptoDominance, btc_dominance: float) -> list[str]:
        factors: list[str] = []
        if btc_trend in ("strong_rising",):
            factors.append(f"BTC strong rally (dom={btc_dominance:.1f}%)")
        if eth_trend in ("strong_rising",):
            factors.append("ETH outperforming - risk appetite strong")
        if dominance == CryptoDominance.ALT_SEASON:
            factors.append("Altcoin season - speculative appetite elevated")
        if dominance == CryptoDominance.BTC_SEASON:
            factors.append("BTC dominance high - crypto risk-off within asset class")
        if btc_trend in ("strong_falling",):
            factors.append("BTC sharp decline - potential risk-off signal for equities")
        return factors

    def _compute_confidence(self, btc_trend: str, dominance: CryptoDominance) -> float:
        confidence = 0.4
        if btc_trend != "stable":
            confidence += 0.2
        if dominance != CryptoDominance.TRANSITIONING:
            confidence += 0.15
        if len(self.btc_history) > 30:
            confidence += 0.1
        return min(1.0, confidence)

    def _generate_description(self, btc: float, dom: float,
                              dom_state: CryptoDominance, risk: CryptoRiskAppetite,
                              signal: str) -> str:
        dom_label = {
            CryptoDominance.BTC_SEASON: "BTC Season",
            CryptoDominance.ALT_SEASON: "Alt Season",
            CryptoDominance.TRANSITIONING: "Transitioning",
        }
        return (f"BTC=${btc:.0f} | {dom_label.get(dom_state, '?')} "
                f"(dom={dom:.1f}%) | {risk.value} | {signal}")

    def clear(self) -> None:
        self.btc_history.clear()
        self.eth_history.clear()
        self.dominance_history.clear()
