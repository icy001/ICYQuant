"""Systemic Risk Detector.

Continuously monitors global markets for systemic risk accumulation.
Tracks equities, rates, credit spreads, VIX, FX, commodities, and
crypto to produce a unified risk level classification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RiskLevel(str, Enum):
    """Global systemic risk level."""

    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


class MarketDomain(str, Enum):
    """Monitored market domains."""

    EQUITY = "equity"
    RATES = "rates"
    CREDIT = "credit"
    VIX = "vix"
    FX = "fx"
    COMMODITY = "commodity"
    CRYPTO = "crypto"
    FUNDING = "funding"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class DomainRisk:
    """Risk assessment for a single market domain.

    Attributes:
        domain: Market domain.
        stress: Stress level [0.0, 1.0].
        signal: Indicator signals.
        description: Human-readable summary.
    """

    domain: MarketDomain = MarketDomain.EQUITY
    stress: float = 0.0
    signal: str = ""
    description: str = ""
    indicators: dict[str, float] = field(default_factory=dict)

    @property
    def is_alarming(self) -> bool:
        return self.stress >= 0.5


@dataclass
class SystemicRiskAssessment:
    """Complete systemic risk assessment.

    Attributes:
        level: Overall risk level.
        score: Composite risk score [0.0, 1.0].
        domain_risks: Per-domain risk breakdown.
        alarming_domains: Domains with stress >= 0.5.
        description: Human-readable summary.
        timestamp: Assessment timestamp.
        metadata: Additional context.
    """

    level: RiskLevel = RiskLevel.NORMAL
    score: float = 0.0
    domain_risks: dict[str, DomainRisk] = field(default_factory=dict)
    alarming_domains: list[str] = field(default_factory=list)
    description: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def requires_action(self) -> bool:
        return self.level in (RiskLevel.WARNING, RiskLevel.CRITICAL)

    @property
    def defense_ratio(self) -> float:
        """Suggested defense allocation ratio."""
        if self.level == RiskLevel.CRITICAL:
            return 0.80
        elif self.level == RiskLevel.WARNING:
            return 0.40
        return 0.05


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class SystemicRiskDetector:
    """Detects systemic risk across global financial markets.

    Monitors seven core domains with domain-specific indicators:
      - Equity: drawdown, breadth, volatility
      - Rates: yield curve, real yield
      - Credit: IG/HY spreads, CDS
      - VIX: level, term structure, VVIX
      - FX: dollar strength, EM pressure
      - Commodity: gold/oil ratio, copper decline
      - Crypto: drawdown, stablecoin flows

    Attributes:
        thresholds: Domain-specific stress thresholds.
        history: Historical readings per domain.
        domain_weights: Weights for composite scoring.
    """

    DOMAIN_WEIGHTS: dict[str, float] = {
        "equity": 0.20,
        "rates": 0.10,
        "credit": 0.20,
        "vix": 0.15,
        "fx": 0.10,
        "commodity": 0.10,
        "crypto": 0.10,
        "funding": 0.05,
    }

    def __init__(self) -> None:
        self.history: dict[str, list[float]] = {}

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect(self, market_data: Optional[dict[str, Any]] = None,
               **kwargs: Any) -> SystemicRiskAssessment:
        """Run full systemic risk detection.

        Args:
            market_data: Optional dict with per-domain indicators:
                equity_drawdown, equity_breadth, equity_vol,
                yield_curve, real_yield,
                ig_spread, hy_spread, cds_spread,
                vix, vix_term, vvix,
                dxy_change, em_fx_pressure,
                gold_oil_ratio, copper_change,
                crypto_drawdown, crypto_dominance, stablecoin_flows,
                funding_spread, repo_stress.

        Returns:
            SystemicRiskAssessment with comprehensive analysis.
        """
        data = market_data or {}
        data.update(kwargs)

        domain_risks: dict[str, DomainRisk] = {}

        # Equity
        domain_risks["equity"] = self._assess_equity(
            data.get("equity_drawdown", 0.0),
            data.get("equity_breadth", 0.5),
            data.get("equity_vol", 0.15),
        )

        # Rates
        domain_risks["rates"] = self._assess_rates(
            data.get("yield_curve", 0.008),
            data.get("real_yield", 0.015),
        )

        # Credit
        domain_risks["credit"] = self._assess_credit(
            data.get("ig_spread", 1.0),
            data.get("hy_spread", 3.0),
            data.get("cds_spread", 0.5),
        )

        # VIX
        domain_risks["vix"] = self._assess_vix(
            data.get("vix", 15.0),
            data.get("vix_term", "contango"),
            data.get("vvix", 85.0),
        )

        # FX
        domain_risks["fx"] = self._assess_fx(
            data.get("dxy_change", 0.0),
            data.get("em_fx_pressure", 0.0),
        )

        # Commodity
        domain_risks["commodity"] = self._assess_commodity(
            data.get("gold_oil_ratio", 25.0),
            data.get("copper_change", 0.0),
        )

        # Crypto
        domain_risks["crypto"] = self._assess_crypto(
            data.get("crypto_drawdown", 0.0),
            data.get("crypto_dominance", 0.50),
            data.get("stablecoin_flows", 0.0),
        )

        # Funding
        domain_risks["funding"] = self._assess_funding(
            data.get("funding_spread", 0.15),
            data.get("repo_stress", 0.0),
        )

        # Composite score (weighted)
        score = sum(
            domain_risks[domain].stress * self.DOMAIN_WEIGHTS.get(domain, 0.1)
            for domain in domain_risks
        )
        score = min(1.0, max(0.0, score))

        # Alarming domains
        alarming = [
            domain for domain, r in domain_risks.items() if r.is_alarming
        ]

        # Classification
        level = self._classify(score, len(alarming))

        description = self._describe(level, score, alarming, domain_risks)

        return SystemicRiskAssessment(
            level=level,
            score=score,
            domain_risks=domain_risks,
            alarming_domains=alarming,
            description=description,
        )

    # ------------------------------------------------------------------
    # Per-domain assessment
    # ------------------------------------------------------------------

    def _assess_equity(self, drawdown: float, breadth: float,
                       vol: float) -> DomainRisk:
        stress = 0.0
        indicators: dict[str, float] = {}
        signals: list[str] = []

        # Drawdown
        if drawdown >= 0.2:
            stress += 0.4
            signals.append("Deep drawdown")
            indicators["drawdown_stress"] = min(1.0, drawdown * 2)
        elif drawdown >= 0.1:
            stress += 0.2
            indicators["drawdown_stress"] = drawdown
        else:
            indicators["drawdown_stress"] = drawdown

        # Breadth
        if breadth <= 0.3:
            stress += 0.35
            signals.append("Narrow breadth")
            indicators["breadth_stress"] = 1.0 - breadth
        elif breadth <= 0.5:
            stress += 0.15
            indicators["breadth_stress"] = 1.0 - breadth
        else:
            indicators["breadth_stress"] = 0.0

        # Volatility
        if vol >= 0.4:
            stress += 0.25
            signals.append("High volatility")
            indicators["vol_stress"] = min(1.0, vol)
        elif vol >= 0.25:
            stress += 0.1
            indicators["vol_stress"] = vol

        stress = min(1.0, stress)
        desc = "Equity: " + (", ".join(signals) if signals else "stable")
        return DomainRisk(
            domain=MarketDomain.EQUITY,
            stress=stress,
            signal="risk_off" if stress >= 0.5 else "normal",
            description=desc,
            indicators=indicators,
        )

    def _assess_rates(self, yield_curve: float, real_yield: float) -> DomainRisk:
        stress = 0.0
        indicators: dict[str, float] = {}
        signals: list[str] = []

        # Yield curve (inversion = stress)
        if yield_curve <= -0.005:
            stress += 0.4
            signals.append("Inverted curve")
            indicators["curve_stress"] = min(1.0, abs(yield_curve) * 100)
        elif yield_curve <= 0.003:
            stress += 0.2
            signals.append("Flat curve")
            indicators["curve_stress"] = 0.3
        else:
            indicators["curve_stress"] = 0.0

        # Real yield (high = tightening)
        if real_yield >= 0.03:
            stress += 0.35
            signals.append("High real yield")
            indicators["real_yield_stress"] = min(1.0, real_yield * 20)
        elif real_yield >= 0.02:
            stress += 0.15
            indicators["real_yield_stress"] = 0.4
        else:
            indicators["real_yield_stress"] = 0.0

        stress = min(1.0, stress)
        desc = "Rates: " + (", ".join(signals) if signals else "stable")
        return DomainRisk(
            domain=MarketDomain.RATES,
            stress=stress,
            signal="tight" if stress >= 0.4 else "normal",
            description=desc,
            indicators=indicators,
        )

    def _assess_credit(self, ig_spread: float, hy_spread: float,
                       cds_spread: float) -> DomainRisk:
        stress = 0.0
        indicators: dict[str, float] = {}
        signals: list[str] = []

        # IG spread
        if ig_spread >= 2.5:
            stress += 0.4
            signals.append("IG stress")
            indicators["ig_stress"] = min(1.0, (ig_spread - 1.0) / 2.0)
        elif ig_spread >= 1.5:
            stress += 0.2
            indicators["ig_stress"] = min(1.0, (ig_spread - 1.0) / 2.0)
        else:
            indicators["ig_stress"] = 0.0

        # HY spread
        if hy_spread >= 6.0:
            stress += 0.35
            signals.append("HY stress")
            indicators["hy_stress"] = min(1.0, (hy_spread - 3.0) / 4.0)
        elif hy_spread >= 4.5:
            stress += 0.15
            indicators["hy_stress"] = min(1.0, (hy_spread - 3.0) / 4.0)

        # CDS
        if cds_spread >= 1.0:
            stress += 0.25
            signals.append("CDS widening")
            indicators["cds_stress"] = min(1.0, cds_spread)

        stress = min(1.0, stress)
        desc = "Credit: " + (", ".join(signals) if signals else "stable")
        return DomainRisk(
            domain=MarketDomain.CREDIT,
            stress=stress,
            signal="stress" if stress >= 0.4 else "normal",
            description=desc,
            indicators=indicators,
        )

    def _assess_vix(self, vix_val: float, vix_term: str,
                    vvix: float) -> DomainRisk:
        stress = 0.0
        indicators: dict[str, float] = {}
        signals: list[str] = []

        if vix_val >= 40:
            stress += 0.5
            signals.append("VIX extreme")
            indicators["vix_stress"] = min(1.0, vix_val / 50)
        elif vix_val >= 28:
            stress += 0.35
            signals.append("VIX elevated")
            indicators["vix_stress"] = vix_val / 50
        elif vix_val >= 22:
            stress += 0.15
            indicators["vix_stress"] = vix_val / 50
        else:
            indicators["vix_stress"] = vix_val / 50

        if vix_term == "backwardation":
            stress += 0.3
            signals.append("Backwardation")
            indicators["term_stress"] = 0.6

        if vvix >= 120:
            stress += 0.2
            signals.append("VVIX spike")
            indicators["vvix_stress"] = min(1.0, vvix / 150)

        stress = min(1.0, stress)
        desc = "VIX: " + (", ".join(signals) if signals else "calm")
        return DomainRisk(
            domain=MarketDomain.VIX,
            stress=stress,
            signal="fear" if stress >= 0.4 else "calm",
            description=desc,
            indicators=indicators,
        )

    def _assess_fx(self, dxy_change: float, em_fx_pressure: float) -> DomainRisk:
        stress = 0.0
        indicators: dict[str, float] = {}
        signals: list[str] = []

        if dxy_change >= 0.03:
            stress += 0.4
            signals.append("USD surge")
            indicators["dxy_stress"] = min(1.0, dxy_change * 10)
        elif dxy_change >= 0.015:
            stress += 0.2
            indicators["dxy_stress"] = dxy_change * 10

        if em_fx_pressure >= 0.5:
            stress += 0.35
            signals.append("EM FX pressure")
            indicators["em_fx_stress"] = em_fx_pressure
        elif em_fx_pressure >= 0.25:
            stress += 0.15
            indicators["em_fx_stress"] = em_fx_pressure

        stress = min(1.0, stress)
        desc = "FX: " + (", ".join(signals) if signals else "stable")
        return DomainRisk(
            domain=MarketDomain.FX,
            stress=stress,
            signal="stress" if stress >= 0.4 else "normal",
            description=desc,
            indicators=indicators,
        )

    def _assess_commodity(self, gold_oil_ratio: float,
                           copper_change: float) -> DomainRisk:
        stress = 0.0
        indicators: dict[str, float] = {}
        signals: list[str] = []

        if gold_oil_ratio >= 35:
            stress += 0.45
            signals.append("Gold/oil ratio elevated")
            indicators["gold_oil_stress"] = min(1.0, (gold_oil_ratio - 25) / 20)
        elif gold_oil_ratio >= 28:
            stress += 0.2
            indicators["gold_oil_stress"] = (gold_oil_ratio - 25) / 20

        if copper_change <= -0.05:
            stress += 0.35
            signals.append("Copper decline")
            indicators["copper_stress"] = min(1.0, abs(copper_change) * 10)

        stress = min(1.0, stress)
        desc = "Commodity: " + (", ".join(signals) if signals else "stable")
        return DomainRisk(
            domain=MarketDomain.COMMODITY,
            stress=stress,
            signal="risk_off" if stress >= 0.4 else "normal",
            description=desc,
            indicators=indicators,
        )

    def _assess_crypto(self, drawdown: float, dominance: float,
                        stablecoin_flows: float) -> DomainRisk:
        stress = 0.0
        indicators: dict[str, float] = {}
        signals: list[str] = []

        if drawdown >= 0.5:
            stress += 0.4
            signals.append("Crypto crash")
            indicators["crypto_dd_stress"] = drawdown
        elif drawdown >= 0.2:
            stress += 0.2
            indicators["crypto_dd_stress"] = drawdown
        else:
            indicators["crypto_dd_stress"] = 0.0

        # BTC dominance spike = risk-off in crypto
        if dominance >= 0.60:
            stress += 0.3
            signals.append("BTC dominance spike")
            indicators["dominance_stress"] = min(1.0, (dominance - 0.4) * 3)

        # Stablecoin outflow = liquidity leaving
        if stablecoin_flows <= -0.05:
            stress += 0.3
            signals.append("Stablecoin outflow")
            indicators["stablecoin_stress"] = min(1.0, abs(stablecoin_flows) * 10)

        stress = min(1.0, stress)
        desc = "Crypto: " + (", ".join(signals) if signals else "stable")
        return DomainRisk(
            domain=MarketDomain.CRYPTO,
            stress=stress,
            signal="risk_off" if stress >= 0.4 else "normal",
            description=desc,
            indicators=indicators,
        )

    def _assess_funding(self, funding_spread: float,
                        repo_stress: float) -> DomainRisk:
        stress = 0.0
        indicators: dict[str, float] = {}
        signals: list[str] = []

        if funding_spread >= 0.5:
            stress += 0.5
            signals.append("Funding stress")
            indicators["funding_stress"] = min(1.0, funding_spread)
        elif funding_spread >= 0.3:
            stress += 0.3
            indicators["funding_stress"] = funding_spread

        if repo_stress >= 0.5:
            stress += 0.5
            signals.append("Repo stress")
            indicators["repo_stress"] = repo_stress
        elif repo_stress >= 0.2:
            stress += 0.25
            indicators["repo_stress"] = repo_stress

        stress = min(1.0, stress)
        desc = "Funding: " + (", ".join(signals) if signals else "stable")
        return DomainRisk(
            domain=MarketDomain.FUNDING,
            stress=stress,
            signal="stress" if stress >= 0.3 else "normal",
            description=desc,
            indicators=indicators,
        )

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def _classify(self, score: float, alarming_count: int) -> RiskLevel:
        if score >= 0.7 or alarming_count >= 4:
            return RiskLevel.CRITICAL
        elif score >= 0.4 or alarming_count >= 2:
            return RiskLevel.WARNING
        return RiskLevel.NORMAL

    def _describe(self, level: RiskLevel, score: float,
                  alarming: list[str],
                  domain_risks: dict[str, DomainRisk]) -> str:
        if level == RiskLevel.CRITICAL:
            return (f"CRITICAL systemic risk (score={score:.2f}). "
                    f"Alarming domains: {', '.join(alarming)}")
        elif level == RiskLevel.WARNING:
            return (f"WARNING: elevated systemic risk (score={score:.2f}). "
                    f"Watch: {', '.join(alarming)}")
        return f"Normal systemic conditions (score={score:.2f})"

    # ------------------------------------------------------------------
    # Quick scan
    # ------------------------------------------------------------------

    def quick_scan(self, vix: float = 15.0,
                   ig_spread: float = 1.0) -> dict[str, Any]:
        """Quick risk scan from minimal inputs."""
        assessment = self.detect(vix=vix, ig_spread=ig_spread)
        return {
            "level": assessment.level.value,
            "score": assessment.score,
            "requires_action": assessment.requires_action,
            "alarming_domains": assessment.alarming_domains,
        }

    def clear(self) -> None:
        self.history.clear()
