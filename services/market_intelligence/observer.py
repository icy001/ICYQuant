from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class MarketPhase(str, Enum):
    OPENING = "OPENING"
    ACTIVE = "ACTIVE"
    LUNCH_LULL = "LUNCH_LULL"
    CLOSING = "CLOSING"
    AFTER_HOURS = "AFTER_HOURS"
    CLOSED = "CLOSED"


class MarketTrend(str, Enum):
    STRONG_UP = "STRONG_UP"
    UP = "UP"
    FLAT = "FLAT"
    DOWN = "DOWN"
    STRONG_DOWN = "STRONG_DOWN"


@dataclass
class MarketSnapshot:
    symbol: str
    price: float
    change_pct: float
    volume: int
    avg_volume: int
    volatility: float
    spread_bps: float
    timestamp: str = ""
    trend: MarketTrend = MarketTrend.FLAT


@dataclass
class MarketState:
    snapshot: MarketSnapshot
    phase: MarketPhase = MarketPhase.ACTIVE
    liquidity_score: int = 50
    volatility_regime: str = "NORMAL"
    correlation_spike: bool = False
    breadth_ratio: float = 0.5
    warnings: List[str] = field(default_factory=list)


class MarketObserver:
    """AI Market Observer - continuously watches and interprets market conditions."""

    def __init__(self):
        self.last_state: Optional[MarketState] = None
        self.observation_count: int = 0

    def observe(self, market):
        """Observe and interpret current market state.

        Args:
            market: Market data - can be MarketSnapshot dataclass or dict/symbol.

        Returns:
            Dict containing observed market state.
        """
        if isinstance(market, MarketSnapshot):
            return self._observe_snapshot(market)
        return {"state": market}

    def _observe_snapshot(self, snapshot: MarketSnapshot) -> dict:
        self.observation_count += 1

        phase = self._determine_phase(snapshot.timestamp)
        volatility_regime = self._classify_volatility(snapshot.volatility)
        liquidity_score = self._assess_liquidity(snapshot.spread_bps, snapshot.volume, snapshot.avg_volume)

        warnings = []
        if snapshot.volatility > 0.03:
            warnings.append("Elevated volatility detected")
        if snapshot.volume > snapshot.avg_volume * 3:
            warnings.append("Abnormal volume spike")
        if abs(snapshot.change_pct) > 0.05:
            warnings.append("Significant price movement")

        return {
            "state": {
                "symbol": snapshot.symbol,
                "price": snapshot.price,
                "change_pct": round(snapshot.change_pct, 4),
                "volume": snapshot.volume,
                "volatility": round(snapshot.volatility, 4),
                "spread_bps": snapshot.spread_bps,
                "phase": phase.value,
                "trend": snapshot.trend.value,
                "volatility_regime": volatility_regime,
                "liquidity_score": liquidity_score,
                "warnings": warnings,
            }
        }

    def _determine_phase(self, timestamp: str) -> MarketPhase:
        if not timestamp:
            return MarketPhase.ACTIVE
        try:
            hour = int(timestamp.split(":")[0])
            if 9 <= hour < 10:
                return MarketPhase.OPENING
            elif 12 <= hour < 13:
                return MarketPhase.LUNCH_LULL
            elif 15 <= hour < 16:
                return MarketPhase.CLOSING
            elif 10 <= hour < 16:
                return MarketPhase.ACTIVE
            else:
                return MarketPhase.CLOSED
        except (ValueError, IndexError):
            return MarketPhase.ACTIVE

    def _classify_volatility(self, vol: float) -> str:
        if vol < 0.01:
            return "LOW"
        elif vol < 0.02:
            return "NORMAL"
        elif vol < 0.04:
            return "ELEVATED"
        return "EXTREME"

    def _assess_liquidity(self, spread_bps: float, volume: int, avg_volume: int) -> int:
        score = 50
        if spread_bps < 5:
            score += 25
        elif spread_bps < 20:
            score += 10
        else:
            score -= 20

        if avg_volume > 0 and volume > avg_volume * 1.5:
            score += 15
        elif avg_volume > 0 and volume > avg_volume * 0.5:
            score += 5
        else:
            score -= 10

        return max(0, min(100, score))
