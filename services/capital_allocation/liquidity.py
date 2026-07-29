from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class LiquidityLevel(str, Enum):
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    ILLIQUID = "ILLIQUID"
    FROZEN = "FROZEN"


class LiquidityRisk(str, Enum):
    NONE = "NONE"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class LiquidityProfile:
    symbol: str
    level: LiquidityLevel
    avg_daily_volume: float
    market_depth: float
    bid_ask_spread: float
    turnover_ratio: float
    days_to_liquidate: float
    exit_difficulty: str
    risk: LiquidityRisk


@dataclass
class LiquidityAnalysis:
    analysis_id: str
    profiles: List[LiquidityProfile]
    portfolio_liquidity_score: float  # 0-100
    bottleneck_symbols: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class LiquidityOptimizationEngine:
    """Liquidity Optimization Engine - analyzes and optimizes portfolio liquidity."""

    def __init__(self):
        self.analyses: List[LiquidityAnalysis] = []
        self.analysis_count = 0

    def analyze(self, market):
        """Analyze liquidity conditions.

        Args:
            market: Market data (str, dict, list, or LiquidityAnalysis).

        Returns:
            Dict containing liquidity analysis.
        """
        if isinstance(market, LiquidityAnalysis):
            return self._process_analysis(market)
        if isinstance(market, list):
            return self._analyze_list(market)
        if isinstance(market, dict):
            return self._analyze_dict(market)
        return {"liquidity": market}

    def _process_analysis(self, analysis: LiquidityAnalysis) -> dict:
        self.analyses.append(analysis)
        return self._to_dict(analysis)

    def _analyze_list(self, positions: list) -> dict:
        self.analysis_count += 1
        profiles = []

        for pos in positions:
            if isinstance(pos, LiquidityProfile):
                profiles.append(pos)
            elif isinstance(pos, dict):
                profiles.append(self._build_profile(pos))
            else:
                profiles.append(LiquidityProfile(
                    symbol=str(pos), level=LiquidityLevel.MODERATE,
                    avg_daily_volume=0, market_depth=0, bid_ask_spread=0.01,
                    turnover_ratio=0, days_to_liquidate=1, exit_difficulty="Low",
                    risk=LiquidityRisk.NONE,
                ))

        # Portfolio liquidity score
        score = self._calc_portfolio_score(profiles)

        # Identify bottlenecks
        bottlenecks = [p.symbol for p in profiles if p.risk in (LiquidityRisk.HIGH, LiquidityRisk.CRITICAL)]

        # Generate recommendations
        recommendations = self._generate_recommendations(profiles, bottlenecks)

        analysis = LiquidityAnalysis(
            analysis_id=f"LIQ_{self.analysis_count:04d}",
            profiles=profiles,
            portfolio_liquidity_score=round(score, 1),
            bottleneck_symbols=bottlenecks,
            recommendations=recommendations,
        )
        self.analyses.append(analysis)
        return self._to_dict(analysis)

    def _analyze_dict(self, data: dict) -> dict:
        positions = data.get("positions", [data])
        return self._analyze_list(positions)

    def _build_profile(self, data: dict) -> LiquidityProfile:
        symbol = data.get("symbol", "UNKNOWN")
        avg_volume = data.get("avg_daily_volume", data.get("volume", 1000000.0))
        spread = data.get("bid_ask_spread", data.get("spread", 0.005))
        depth = data.get("market_depth", data.get("depth", avg_volume * 0.1))
        turnover = data.get("turnover_ratio", 0.5)

        # Determine liquidity level
        if avg_volume <= 0:
            level = LiquidityLevel.ILLIQUID
        elif spread > 0.02:
            level = LiquidityLevel.LOW
        elif spread > 0.01:
            level = LiquidityLevel.MODERATE
        else:
            level = LiquidityLevel.HIGH

        # Estimate days to liquidate
        position_size = data.get("position_size", data.get("value", 0))
        if avg_volume > 0:
            days = (position_size * 0.3) / (avg_volume * 0.1)
        else:
            days = 999
        days = min(999, max(0, days))

        # Exit difficulty
        if days < 1:
            difficulty = "Easy - same day exit"
        elif days < 3:
            difficulty = "Manageable - 1-3 days"
        elif days < 7:
            difficulty = "Moderate - up to 1 week"
        elif days < 30:
            difficulty = "Difficult - 1-4 weeks"
        else:
            difficulty = "Very difficult - 1+ month"

        # Liquidity risk
        if days > 7:
            risk = LiquidityRisk.CRITICAL
        elif days > 3:
            risk = LiquidityRisk.HIGH
        elif days > 1:
            risk = LiquidityRisk.ELEVATED
        else:
            risk = LiquidityRisk.NONE

        return LiquidityProfile(
            symbol=symbol,
            level=level,
            avg_daily_volume=round(avg_volume, 2),
            market_depth=round(depth, 2),
            bid_ask_spread=round(spread, 4),
            turnover_ratio=round(turnover, 4),
            days_to_liquidate=round(days, 1),
            exit_difficulty=difficulty,
            risk=risk,
        )

    def _calc_portfolio_score(self, profiles: List[LiquidityProfile]) -> float:
        if not profiles:
            return 100.0

        level_scores = {
            LiquidityLevel.HIGH: 100, LiquidityLevel.MODERATE: 75,
            LiquidityLevel.LOW: 40, LiquidityLevel.ILLIQUID: 15, LiquidityLevel.FROZEN: 0,
        }
        scores = [level_scores.get(p.level, 50) for p in profiles]
        return sum(scores) / len(scores)

    def _generate_recommendations(self, profiles: List[LiquidityProfile], bottlenecks: List[str]) -> List[str]:
        recs = []
        if bottlenecks:
            recs.append(f"Reduce position in low-liquidity assets: {', '.join(bottlenecks)}")

        illiquid = [p for p in profiles if p.level in (LiquidityLevel.LOW, LiquidityLevel.ILLIQUID)]
        if illiquid:
            recs.append(f"Consider TWAP/VWAP execution for {len(illiquid)} illiquid positions")

        high_spread = [p for p in profiles if p.bid_ask_spread > 0.015]
        if high_spread:
            recs.append("Avoid market orders - use limit orders for wide-spread assets")

        if not recs:
            recs.append("Liquidity profile is healthy - no action needed")
        return recs

    def _to_dict(self, analysis: LiquidityAnalysis) -> dict:
        return {
            "liquidity": {
                "analysis_id": analysis.analysis_id,
                "profiles": [
                    {
                        "symbol": p.symbol,
                        "level": p.level.value,
                        "avg_daily_volume": p.avg_daily_volume,
                        "market_depth": p.market_depth,
                        "bid_ask_spread": p.bid_ask_spread,
                        "turnover_ratio": p.turnover_ratio,
                        "days_to_liquidate": p.days_to_liquidate,
                        "exit_difficulty": p.exit_difficulty,
                        "risk": p.risk.value,
                    }
                    for p in analysis.profiles
                ],
                "portfolio_liquidity_score": analysis.portfolio_liquidity_score,
                "bottleneck_symbols": analysis.bottleneck_symbols,
                "recommendations": analysis.recommendations,
            }
        }

    def get_analysis(self) -> Optional[LiquidityAnalysis]:
        """Get the latest liquidity analysis."""
        return self.analyses[-1] if self.analyses else None
