"""Systemic Risk Detection.

Monitors global financial system stability indicators to detect
systemic risk accumulation before it manifests as a market crisis.
Analyzes cross-asset contagion channels, credit chain vulnerabilities,
and liquidity-stress amplification loops.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SystemicRiskLevel(str, Enum):
    """Systemic risk severity classification."""

    SAFE = "safe"
    WATCH = "watch"
    CAUTION = "caution"
    DANGER = "danger"
    CRISIS = "crisis"


class ContagionChannel(str, Enum):
    """Channels through which systemic risk propagates."""

    CORRELATION = "correlation"
    CREDIT = "credit"
    LIQUIDITY = "liquidity"
    CURRENCY = "currency"
    COUNTERPARTY = "counterparty"
    SOVEREIGN = "sovereign"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class ContagionSignal:
    """A contagion risk signal from a specific channel.

    Attributes:
        channel: Propagation channel.
        source: Source market/asset of the risk.
        target: Target market/asset potentially affected.
        severity: Contagion severity score [0.0, 1.0].
        probability: Probability of contagion materializing.
        description: Human-readable explanation.
    """

    channel: ContagionChannel = ContagionChannel.CORRELATION
    source: str = ""
    target: str = ""
    severity: float = 0.0
    probability: float = 0.0
    description: str = ""

    @property
    def risk_score(self) -> float:
        return self.severity * self.probability

    @property
    def is_critical(self) -> bool:
        return self.risk_score >= 0.5


@dataclass
class SystemicRiskResult:
    """Comprehensive systemic risk assessment.

    Attributes:
        level: Overall systemic risk level.
        score: Composite systemic risk score [0.0, 1.0].
        contagion_signals: Active contagion risk signals.
        correlation_risk: Cross-asset correlation breakdown risk.
        credit_risk: Credit chain stress level.
        liquidity_risk: System-wide liquidity stress.
        currency_risk: Currency contagion risk.
        description: Human-readable summary.
        confidence: Assessment confidence [0.0, 1.0].
        early_warning: Whether early warning signal is active.
        timestamp: Assessment timestamp.
    """

    level: SystemicRiskLevel = SystemicRiskLevel.SAFE
    score: float = 0.0
    contagion_signals: list[ContagionSignal] = field(default_factory=list)
    correlation_risk: float = 0.0
    credit_risk: float = 0.0
    liquidity_risk: float = 0.0
    currency_risk: float = 0.0
    description: str = ""
    confidence: float = 0.5
    early_warning: bool = False
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_alarming(self) -> bool:
        return self.level in (SystemicRiskLevel.DANGER, SystemicRiskLevel.CRISIS)

    @property
    def critical_channels(self) -> list[ContagionSignal]:
        return [s for s in self.contagion_signals if s.is_critical]

    @property
    def defense_multiplier(self) -> float:
        """Suggested defense multiplier (lower = more defensive)."""
        return max(0.1, 1.0 - self.score)


class SystemicRiskDetector:
    """Detects systemic risk accumulation across global markets.

    Monitors correlation breakdowns, credit chain stress, liquidity
    compression, and currency contagion to identify systemic risk
    before it triggers a market-wide crisis.

    Attributes:
        correlation_threshold: Cross-asset correlation crisis threshold.
        credit_stress_threshold: Credit spread stress threshold.
        liquidity_stress_threshold: Liquidity compression threshold.
        vix_history: Historical VIX readings.
        correlation_history: Historical correlation readings.
    """

    def __init__(self) -> None:
        self.correlation_threshold: float = 0.7
        self.credit_stress_threshold: float = 3.0
        self.liquidity_stress_threshold: float = 0.5
        self.vix_history: list[float] = []
        self.correlation_history: list[float] = []
        self.credit_history: list[float] = []
        self._contagion_map: dict[str, list[str]] = self._build_contagion_map()

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def assess(self,
               avg_correlation: float = 0.2,
               credit_spread: float = 1.0,
               liquidity_stress: float = 0.1,
               vix: float = 15.0,
               dollar_trend: str = "stable",
               em_spread: float = 2.0) -> SystemicRiskResult:
        """Comprehensive systemic risk assessment.

        Args:
            avg_correlation: Average cross-asset correlation.
            credit_spread: Investment grade credit spread.
            liquidity_stress: Composite liquidity stress (0-1).
            vix: VIX index level.
            dollar_trend: USD trend direction.
            em_spread: EM sovereign spread.

        Returns:
            SystemicRiskResult.
        """
        self.vix_history.append(vix)
        self.correlation_history.append(avg_correlation)
        self.credit_history.append(credit_spread)

        # Trim
        for hist in (self.vix_history, self.correlation_history, self.credit_history):
            if len(hist) > 200:
                hist[:] = hist[-200:]

        # Assess each dimension
        corr_risk = self._assess_correlation_risk(avg_correlation)
        cr_risk = self._assess_credit_risk(credit_spread, em_spread)
        liq_risk = self._assess_liquidity_risk(liquidity_stress)
        cur_risk = self._assess_currency_risk(dollar_trend, em_spread)

        # Composite score (weighted)
        score = (
            corr_risk * 0.30
            + cr_risk * 0.25
            + liq_risk * 0.25
            + cur_risk * 0.20
        )
        score = min(1.0, max(0.0, score))

        # Level classification
        level = self._classify_level(score)
        early_warning = score >= 0.5

        # Contagion signals
        contagion_signals = self._detect_contagion(
            avg_correlation, credit_spread, liquidity_stress,
            dollar_trend, em_spread, score,
        )

        confidence = self._compute_confidence(
            avg_correlation, credit_spread, liquidity_stress, vix,
        )

        description = self._generate_description(level, score, contagion_signals)

        return SystemicRiskResult(
            level=level,
            score=score,
            contagion_signals=contagion_signals,
            correlation_risk=corr_risk,
            credit_risk=cr_risk,
            liquidity_risk=liq_risk,
            currency_risk=cur_risk,
            description=description,
            confidence=confidence,
            early_warning=early_warning,
        )

    # ------------------------------------------------------------------
    # Dimension Assessment
    # ------------------------------------------------------------------

    def _assess_correlation_risk(self, avg_corr: float) -> float:
        """Assess correlation breakdown risk."""
        if avg_corr >= 0.8:
            return 0.9
        elif avg_corr >= 0.7:
            return 0.7
        elif avg_corr >= 0.5:
            return 0.5
        elif avg_corr >= 0.3:
            return 0.3
        return 0.1

    def _assess_credit_risk(self, ig_spread: float, em_spread: float) -> float:
        """Assess credit chain systemic risk."""
        score = 0.1
        if ig_spread >= self.credit_stress_threshold:
            score += 0.4
        elif ig_spread >= 2.0:
            score += 0.25
        if em_spread >= 5.0:
            score += 0.3
        elif em_spread >= 3.5:
            score += 0.15
        return min(1.0, score)

    def _assess_liquidity_risk(self, liquidity_stress: float) -> float:
        """Assess systemic liquidity risk."""
        if liquidity_stress >= 0.8:
            return 0.95
        elif liquidity_stress >= self.liquidity_stress_threshold:
            return 0.6 + (liquidity_stress - 0.5) * 0.8
        elif liquidity_stress >= 0.3:
            return 0.35
        return max(0.05, liquidity_stress)

    def _assess_currency_risk(self, dollar_trend: str, em_spread: float) -> float:
        """Assess currency contagion risk."""
        score = 0.1
        if dollar_trend in ("strong_appreciation",):
            score += 0.4
        elif dollar_trend in ("appreciation",):
            score += 0.2
        if em_spread >= 5.0:
            score += 0.3
        elif em_spread >= 4.0:
            score += 0.15
        return min(1.0, score)

    # ------------------------------------------------------------------
    # Contagion Detection
    # ------------------------------------------------------------------

    def _detect_contagion(self, avg_corr: float, credit_spread: float,
                          liquidity_stress: float, dollar_trend: str,
                          em_spread: float, score: float) -> list[ContagionSignal]:
        signals: list[ContagionSignal] = []

        # Correlation contagion
        if avg_corr >= self.correlation_threshold:
            signals.append(ContagionSignal(
                channel=ContagionChannel.CORRELATION,
                source="multi_asset",
                target="diversified_portfolios",
                severity=min(1.0, (avg_corr - 0.5) / 0.5),
                probability=0.7,
                description=f"Diversification failing (corr={avg_corr:.2f})",
            ))

        # Credit contagion
        if credit_spread >= 2.0:
            signals.append(ContagionSignal(
                channel=ContagionChannel.CREDIT,
                source="corporate_credit",
                target="equities",
                severity=min(1.0, (credit_spread - 1.0) / 1.5),
                probability=0.6,
                description=f"Credit market stress propagating (spread={credit_spread:.1f}%)",
            ))

        # Liquidity contagion
        if liquidity_stress >= 0.4:
            signals.append(ContagionSignal(
                channel=ContagionChannel.LIQUIDITY,
                source="funding_markets",
                target="risk_assets",
                severity=liquidity_stress,
                probability=0.65,
                description="Liquidity compression forcing asset sales",
            ))

        # Currency contagion
        if dollar_trend == "strong_appreciation":
            signals.append(ContagionSignal(
                channel=ContagionChannel.CURRENCY,
                source="USD",
                target="emerging_markets",
                severity=0.7,
                probability=0.75,
                description="Strong dollar pressuring EM currencies and debt",
            ))

        # EM sovereign contagion
        if em_spread >= 4.0:
            signals.append(ContagionSignal(
                channel=ContagionChannel.SOVEREIGN,
                source="em_sovereign",
                target="global_risk_assets",
                severity=min(1.0, (em_spread - 2.0) / 3.0),
                probability=0.55,
                description=f"EM sovereign stress (spread={em_spread:.1f}%)",
            ))

        return signals

    # ------------------------------------------------------------------
    # Cross-Asset Contagion Map
    # ------------------------------------------------------------------

    def _build_contagion_map(self) -> dict[str, list[str]]:
        return {
            "equities": ["credit", "volatility", "funding"],
            "credit": ["equities", "funding", "banks"],
            "funding": ["equities", "credit", "commodities"],
            "USD": ["emerging_markets", "commodities", "crypto"],
            "volatility": ["equities", "credit", "options"],
        }

    def get_contagion_paths(self, source: str) -> list[str]:
        """Get potential contagion paths from a source market."""
        return self._contagion_map.get(source, [])

    def get_vulnerable_assets(self, source: str) -> list[str]:
        """Get assets vulnerable to contagion from a source."""
        return self.get_contagion_paths(source)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _classify_level(self, score: float) -> SystemicRiskLevel:
        if score >= 0.8:
            return SystemicRiskLevel.CRISIS
        elif score >= 0.6:
            return SystemicRiskLevel.DANGER
        elif score >= 0.4:
            return SystemicRiskLevel.CAUTION
        elif score >= 0.2:
            return SystemicRiskLevel.WATCH
        return SystemicRiskLevel.SAFE

    def _compute_confidence(self, avg_corr: float, credit_spread: float,
                            liquidity_stress: float, vix: float) -> float:
        confidence = 0.35
        # More extreme signals → higher confidence
        if avg_corr > 0.5 or avg_corr < -0.3:
            confidence += 0.15
        if credit_spread > 2.0:
            confidence += 0.15
        if liquidity_stress > 0.3:
            confidence += 0.1
        if vix > 25:
            confidence += 0.1
        if len(self.vix_history) > 30:
            confidence += 0.1
        return min(1.0, confidence)

    def _generate_description(self, level: SystemicRiskLevel, score: float,
                              signals: list[ContagionSignal]) -> str:
        level_desc = {
            SystemicRiskLevel.SAFE: "Normal conditions – no systemic stress",
            SystemicRiskLevel.WATCH: "Watch – early stress indicators present",
            SystemicRiskLevel.CAUTION: "Caution – systemic risk building",
            SystemicRiskLevel.DANGER: "DANGER – elevated systemic risk",
            SystemicRiskLevel.CRISIS: "CRISIS – systemic event risk high",
        }
        base = level_desc.get(level, "Unknown")
        active = [s.channel.value for s in signals if s.is_critical]
        if active:
            return f"{base}. Active contagion: {', '.join(active)} (score={score:.2f})"
        return f"{base} (score={score:.2f})"

    def clear(self) -> None:
        self.vix_history.clear()
        self.correlation_history.clear()
        self.credit_history.clear()
