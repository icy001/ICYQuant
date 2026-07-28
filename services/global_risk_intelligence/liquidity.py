"""Liquidity Stress Analyzer.

Monitors funding stress, credit spreads, repo market conditions,
and dollar liquidity to produce a unified liquidity stress score.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class LiquidityLevel(str, Enum):
    """Liquidity stress level."""

    AMPLE = "ample"
    NORMAL = "normal"
    TIGHT = "tight"
    STRESSED = "stressed"
    FREEZE = "freeze"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class LiquidityComponent:
    """Liquidity assessment for a single channel.

    Attributes:
        channel: Liquidity channel name.
        stress: Stress level [0.0, 1.0].
        indicators: Raw indicators for this channel.
        signal: Signal label.
    """

    channel: str = ""
    stress: float = 0.0
    indicators: dict[str, float] = field(default_factory=dict)
    signal: str = "normal"


@dataclass
class LiquidityAssessment:
    """Complete liquidity stress assessment.

    Attributes:
        level: Overall liquidity level.
        score: Composite liquidity stress score [0.0, 1.0].
        components: Per-channel breakdown.
        stressed_channels: Channels under stress.
        description: Human-readable summary.
        timestamp: Assessment timestamp.
    """

    level: LiquidityLevel = LiquidityLevel.NORMAL
    score: float = 0.0
    components: dict[str, LiquidityComponent] = field(default_factory=dict)
    stressed_channels: list[str] = field(default_factory=list)
    description: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def requires_liquidity_reduction(self) -> bool:
        return self.level in (LiquidityLevel.STRESSED, LiquidityLevel.FREEZE)

    @property
    def position_size_cap(self) -> float:
        """Maximum position size given liquidity conditions."""
        mapping = {
            LiquidityLevel.AMPLE: 1.0,
            LiquidityLevel.NORMAL: 0.9,
            LiquidityLevel.TIGHT: 0.65,
            LiquidityLevel.STRESSED: 0.35,
            LiquidityLevel.FREEZE: 0.10,
        }
        return mapping.get(self.level, 0.5)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class LiquidityStressAnalyzer:
    """Analyzes multi-channel liquidity conditions.

    Monitors four core channels:
      - Funding: TED spread, LIBOR-OIS, commercial paper spreads
      - Credit: IG/HY bid-ask spreads, new issue premiums
      - Repo: repo rates, fails-to-deliver, collateral scarcity
      - Dollar: cross-currency basis, dollar index liquidity
    """

    CHANNEL_WEIGHTS: dict[str, float] = {
        "funding": 0.30,
        "credit": 0.25,
        "repo": 0.25,
        "dollar": 0.20,
    }

    def __init__(self) -> None:
        self.history: list[LiquidityAssessment] = []

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def analyze(self,
                funding_spread: float = 0.15,
                libor_ois: float = 0.10,
                commercial_paper_spread: float = 0.05,
                ig_bid_ask: float = 0.03,
                hy_bid_ask: float = 0.10,
                new_issue_premium: float = 0.02,
                repo_rate: float = 0.02,
                fails_to_deliver: float = 0.0,
                cross_currency_basis: float = -0.1,
                dollar_index_liquidity: float = 0.0,
                ) -> LiquidityAssessment:
        """Run full liquidity stress analysis.

        Args:
            funding_spread: Funding spread vs risk-free.
            libor_ois: LIBOR-OIS spread (interbank stress).
            commercial_paper_spread: CP spread.
            ig_bid_ask: IG corporate bond bid-ask spread.
            hy_bid_ask: HY corporate bond bid-ask spread.
            new_issue_premium: New bond issue premium.
            repo_rate: Repo rate vs general collateral.
            fails_to_deliver: Fails-to-deliver rate.
            cross_currency_basis: Cross-currency basis swap.
            dollar_index_liquidity: Dollar liquidity index.

        Returns:
            LiquidityAssessment.
        """
        # Funding channel
        funding = self._assess_funding(
            funding_spread, libor_ois, commercial_paper_spread,
        )

        # Credit channel
        credit = self._assess_credit_liquidity(
            ig_bid_ask, hy_bid_ask, new_issue_premium,
        )

        # Repo channel
        repo = self._assess_repo(repo_rate, fails_to_deliver)

        # Dollar channel
        dollar = self._assess_dollar_liquidity(
            cross_currency_basis, dollar_index_liquidity,
        )

        components = {
            "funding": funding,
            "credit": credit,
            "repo": repo,
            "dollar": dollar,
        }

        # Weighted composite
        score = sum(
            components[ch].stress * self.CHANNEL_WEIGHTS.get(ch, 0.1)
            for ch in components
        )
        score = min(1.0, max(0.0, score))

        # Stressed channels
        stressed = [ch for ch, c in components.items() if c.stress >= 0.5]

        # Level classification
        level = self._classify_level(score, len(stressed))

        description = self._describe(level, score, stressed, components)

        assessment = LiquidityAssessment(
            level=level,
            score=score,
            components=components,
            stressed_channels=stressed,
            description=description,
        )
        self.history.append(assessment)
        return assessment

    # ------------------------------------------------------------------
    # Channel assessment
    # ------------------------------------------------------------------

    def _assess_funding(self, funding_spread: float,
                        libor_ois: float,
                        cp_spread: float) -> LiquidityComponent:
        stress = 0.0
        indicators: dict[str, float] = {}
        signals: list[str] = []

        if funding_spread >= 0.5:
            stress += 0.5
            signals.append("Funding stress")
        elif funding_spread >= 0.3:
            stress += 0.3
            signals.append("Funding tight")
        indicators["funding"] = min(1.0, funding_spread)

        if libor_ois >= 0.5:
            stress += 0.5
            signals.append("Interbank stress")
        elif libor_ois >= 0.25:
            stress += 0.3
            signals.append("Interbank tight")
        indicators["libor_ois"] = min(1.0, libor_ois)

        if cp_spread >= 0.15:
            stress += 0.3
            signals.append("CP stress")
            indicators["cp"] = min(1.0, cp_spread * 3)
        else:
            indicators["cp"] = 0.0

        stress = min(1.0, stress)
        return LiquidityComponent(
            channel="funding",
            stress=stress,
            indicators=indicators,
            signal="stress" if stress >= 0.3 else "normal",
        )

    def _assess_credit_liquidity(self, ig_ba: float, hy_ba: float,
                                   nip: float) -> LiquidityComponent:
        stress = 0.0
        indicators: dict[str, float] = {}
        signals: list[str] = []

        if ig_ba >= 0.08:
            stress += 0.4
            signals.append("IG illiquid")
        elif ig_ba >= 0.05:
            stress += 0.2
            signals.append("IG widening")
        indicators["ig_ba"] = min(1.0, ig_ba * 10)

        if hy_ba >= 0.25:
            stress += 0.35
            signals.append("HY illiquid")
        elif hy_ba >= 0.15:
            stress += 0.15
            signals.append("HY widening")
        indicators["hy_ba"] = min(1.0, hy_ba * 3)

        if nip >= 0.05:
            stress += 0.25
            signals.append("New issue stress")
            indicators["nip"] = min(1.0, nip * 10)

        stress = min(1.0, stress)
        return LiquidityComponent(
            channel="credit",
            stress=stress,
            indicators=indicators,
            signal="stress" if stress >= 0.3 else "normal",
        )

    def _assess_repo(self, repo_rate: float,
                     fails: float) -> LiquidityComponent:
        stress = 0.0
        indicators: dict[str, float] = {}
        signals: list[str] = []

        if repo_rate >= 0.08:
            stress += 0.5
            signals.append("Repo stress")
        elif repo_rate >= 0.04:
            stress += 0.3
            signals.append("Repo tight")
        indicators["repo_rate"] = min(1.0, repo_rate * 8)

        if fails >= 0.03:
            stress += 0.4
            signals.append("Fails-to-deliver spike")
        elif fails >= 0.01:
            stress += 0.2
        indicators["fails"] = min(1.0, fails * 20)

        stress = min(1.0, stress)
        return LiquidityComponent(
            channel="repo",
            stress=stress,
            indicators=indicators,
            signal="stress" if stress >= 0.3 else "normal",
        )

    def _assess_dollar_liquidity(self, ccy_basis: float,
                                   dx_liq: float) -> LiquidityComponent:
        stress = 0.0
        indicators: dict[str, float] = {}
        signals: list[str] = []

        # Negative cross-currency basis = dollar scarcity
        if ccy_basis <= -0.5:
            stress += 0.5
            signals.append("Dollar scarcity (severe)")
        elif ccy_basis <= -0.25:
            stress += 0.3
            signals.append("Dollar scarcity")
        indicators["ccy_basis"] = min(1.0, abs(ccy_basis) * 2)

        if dx_liq >= 0.5:
            stress += 0.5
            signals.append("Dollar liquidity strain")
        elif dx_liq >= 0.25:
            stress += 0.25
            signals.append("Dollar tight")
        indicators["dx_liq"] = dx_liq

        stress = min(1.0, stress)
        return LiquidityComponent(
            channel="dollar",
            stress=stress,
            indicators=indicators,
            signal="stress" if stress >= 0.3 else "normal",
        )

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def _classify_level(self, score: float, stressed_count: int) -> LiquidityLevel:
        if score >= 0.8 or stressed_count >= 3:
            return LiquidityLevel.FREEZE
        elif score >= 0.55:
            return LiquidityLevel.STRESSED
        elif score >= 0.3:
            return LiquidityLevel.TIGHT
        elif score >= 0.1:
            return LiquidityLevel.NORMAL
        return LiquidityLevel.AMPLE

    def _describe(self, level: LiquidityLevel, score: float,
                  stressed: list[str],
                  components: dict[str, LiquidityComponent]) -> str:
        ch_desc = ", ".join(
            f"{ch}={c.stress:.2f}" for ch, c in components.items()
        )
        base = f"Liquidity: {level.value} (score={score:.2f})"
        if stressed:
            base += f". Stressed: {', '.join(stressed)}"
        base += f". Detail: [{ch_desc}]"
        return base

    # ------------------------------------------------------------------
    # Quick scan
    # ------------------------------------------------------------------

    def quick_scan(self, funding_spread: float = 0.15,
                   ig_ba: float = 0.03) -> dict[str, Any]:
        """Fast liquidity scan from key indicators."""
        assessment = self.analyze(
            funding_spread=funding_spread,
            ig_bid_ask=ig_ba,
        )
        return {
            "level": assessment.level.value,
            "score": assessment.score,
            "requires_reduction": assessment.requires_liquidity_reduction,
            "position_cap": assessment.position_size_cap,
        }

    def clear(self) -> None:
        self.history.clear()
