"""Market Observer Agent - real-time market observation and regime detection.

Monitors market data, news, order flow, macro conditions, and sentiment.
Produces market regime classification, trend analysis, volatility assessment,
and liquidity analysis. Communicates findings to the Trading Agent.
"""

import time
import uuid
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .agent_base import (
    BaseAgent, AgentStatus, Observation, Analysis, Decision, DecisionAction,
)

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market regime classification."""

    RISK_ON = "risk_on"
    RISK_OFF = "risk_off"
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGE_BOUND = "range_bound"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    CRISIS = "crisis"
    RECOVERY = "recovery"
    UNKNOWN = "unknown"


class TrendDirection(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class VolatilityLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class LiquidityCondition(Enum):
    TIGHT = "tight"
    NORMAL = "normal"
    AMPLE = "ample"


@dataclass
class MarketObservation(Observation):
    """Market-specific observation data."""

    symbols: List[str] = field(default_factory=list)
    regime: MarketRegime = MarketRegime.UNKNOWN
    trend: TrendDirection = TrendDirection.NEUTRAL
    volatility: VolatilityLevel = VolatilityLevel.MEDIUM
    liquidity: LiquidityCondition = LiquidityCondition.NORMAL
    macro_indicators: Dict[str, float] = field(default_factory=dict)
    sector_performance: Dict[str, float] = field(default_factory=dict)
    sentiment_score: float = 0.5
    anomalies: List[str] = field(default_factory=list)
    news_signals: List[Dict[str, Any]] = field(default_factory=list)


class MarketAgent(BaseAgent):
    """Market Observer Agent.

    Responsibilities:
    - Real-time market data monitoring
    - Regime detection (risk-on/off, trending, volatile)
    - Trend analysis across multiple timeframes
    - Volatility assessment
    - Liquidity condition evaluation
    - Macro indicator tracking
    - Sector rotation analysis
    - Sentiment aggregation from news/knowledge graph

    Outputs market state to Trading Agent for decision-making.
    """

    agent_type = "market_agent"

    def __init__(self, name: str = None, config: Dict[str, Any] = None):
        super().__init__(name=name, config=config)
        self.watchlist: List[str] = self.config.get("watchlist", [])
        self._market_data: Dict[str, Dict[str, Any]] = {}
        self._regime_history: List[Dict[str, Any]] = []
        self._max_regime_history = 500
        self._last_scan_time = 0.0
        self._scan_interval = self.config.get("scan_interval", 60.0)

    # ── Lifecycle ───────────────────────────────────────────────

    def start(self) -> None:
        super().start()
        self.memory.set_working("watchlist", self.watchlist)
        self.memory.set_working("scans", 0)
        logger.info("MarketAgent [%s] started with %d symbols", self.name, len(self.watchlist))

    # ── Main Loop ───────────────────────────────────────────────

    def observe(self) -> Optional[Observation]:
        """Scan market conditions across watchlist and macro indicators."""
        now = time.time()
        if now - self._last_scan_time < self._scan_interval:
            return None

        self._last_scan_time = now
        scans = self.memory.get_working("scans", 0) + 1
        self.memory.set_working("scans", scans)

        # Analyze market data for watchlist
        sector_perf: Dict[str, float] = {}
        for symbol in self.watchlist:
            data = self._market_data.get(symbol, {})
            sector = data.get("sector", "unknown")
            change_pct = data.get("change_pct", 0)
            if sector not in sector_perf:
                sector_perf[sector] = 0
            sector_perf[sector] += change_pct

        # Determine regime
        regime = self._detect_regime()
        trend = self._detect_trend()
        volatility = self._assess_volatility()
        liquidity = self._assess_liquidity()

        obs = MarketObservation(
            source=self.name,
            symbols=self.watchlist,
            regime=regime,
            trend=trend,
            volatility=volatility,
            liquidity=liquidity,
            sector_performance=sector_perf,
            data={
                "regime": regime.value,
                "trend": trend.value,
                "volatility": volatility.value,
                "liquidity": liquidity.value,
                "sector_performance": sector_perf,
                "watchlist_size": len(self.watchlist),
                "scan_number": scans,
            },
            tags=["market", regime.value, trend.value],
        )

        # Record regime in history
        self._regime_history.append({
            "timestamp": now,
            "regime": regime.value,
            "trend": trend.value,
            "volatility": volatility.value,
        })
        if len(self._regime_history) > self._max_regime_history:
            self._regime_history = self._regime_history[-self._max_regime_history:]

        # Store in memory
        self.memory.set_working("current_regime", regime.value)
        self.memory.set_working("current_trend", trend.value)
        self.memory.set_working("current_volatility", volatility.value)

        return obs

    def analyze(self, observation: Optional[Observation]) -> Optional[Analysis]:
        """Analyze market observation and generate trading signals."""
        if observation is None:
            return None

        obs_data = observation.data
        regime = obs_data.get("regime", "unknown")
        trend = obs_data.get("trend", "neutral")
        volatility = obs_data.get("volatility", "medium")

        # Generate signals based on market conditions
        signals = []
        confidence = 0.5

        if regime == "risk_on" and trend == "bullish":
            signals.append({
                "type": "MARKET_REGIME",
                "signal": "BUY_BIAS",
                "strength": 0.7,
                "reason": f"Risk-on regime with {trend} trend",
            })
            confidence = 0.7
        elif regime == "risk_off" and trend == "bearish":
            signals.append({
                "type": "MARKET_REGIME",
                "signal": "SELL_BIAS",
                "strength": 0.7,
                "reason": f"Risk-off regime with {trend} trend",
            })
            confidence = 0.7
        elif volatility == "high" or volatility == "extreme":
            signals.append({
                "type": "VOLATILITY",
                "signal": "REDUCE_SIZE",
                "strength": 0.6,
                "reason": f"High volatility: {volatility}",
            })
            confidence = 0.5

        if not signals:
            signals.append({
                "type": "MARKET_REGIME",
                "signal": "NEUTRAL",
                "strength": 0.3,
                "reason": f"No strong signal: regime={regime}, trend={trend}",
            })

        # Send market state to trading agent
        self.send_to(
            recipient="trading_agent",
            event="MARKET_STATE",
            data={
                "regime": regime,
                "trend": trend,
                "volatility": volatility,
                "liquidity": obs_data.get("liquidity", "normal"),
                "sector_performance": obs_data.get("sector_performance", {}),
            },
        )

        analysis = Analysis(
            agent=self.name,
            summary=f"Market: {regime}, Trend: {trend}, Vol: {volatility}",
            metrics={
                "regime": regime,
                "trend": trend,
                "volatility": volatility,
                "liquidity": obs_data.get("liquidity", "normal"),
            },
            signals=signals,
            confidence=confidence,
        )

        return analysis

    def decide(self, analysis: Optional[Analysis]) -> Optional[Decision]:
        """Market agent doesn't make direct trading decisions.
        It provides analysis to the Trading Agent.
        """
        # Market agent's "decision" is whether to send alerts
        if analysis and analysis.confidence > 0.7:
            self.send_to(
                recipient="trading_agent",
                event="MARKET_ALERT",
                data={
                    "summary": analysis.summary,
                    "signals": analysis.signals,
                    "confidence": analysis.confidence,
                },
            )

        # Market agent itself holds - it provides information, not decisions
        return Decision(
            agent=self.name,
            action=DecisionAction.HOLD,
            symbol="MARKET",
            confidence=analysis.confidence if analysis else 0.5,
            reason=["Market observation only"],
        )

    # ── Market Analysis Methods ─────────────────────────────────

    def _detect_regime(self) -> MarketRegime:
        """Detect current market regime from watchlist data."""
        if not self.watchlist:
            return MarketRegime.UNKNOWN

        # Simple heuristic based on price changes
        changes = []
        for symbol in self.watchlist:
            data = self._market_data.get(symbol, {})
            change = data.get("change_pct", 0)
            changes.append(change)

        if not changes:
            return MarketRegime.UNKNOWN

        avg_change = sum(changes) / len(changes)
        positive_ratio = sum(1 for c in changes if c > 0) / len(changes)

        if avg_change > 2.0 and positive_ratio > 0.7:
            return MarketRegime.RISK_ON
        elif avg_change > 1.0:
            return MarketRegime.TRENDING_UP
        elif avg_change < -2.0 and positive_ratio < 0.3:
            return MarketRegime.RISK_OFF
        elif avg_change < -1.0:
            return MarketRegime.TRENDING_DOWN
        elif abs(avg_change) < 0.5:
            return MarketRegime.RANGE_BOUND

        return MarketRegime.UNKNOWN

    def _detect_trend(self) -> TrendDirection:
        """Detect trend direction."""
        changes = [
            self._market_data.get(s, {}).get("change_pct", 0)
            for s in self.watchlist
        ]
        if not changes:
            return TrendDirection.NEUTRAL

        avg = sum(changes) / len(changes)
        if avg > 0.5:
            return TrendDirection.BULLISH
        elif avg < -0.5:
            return TrendDirection.BEARISH
        return TrendDirection.NEUTRAL

    def _assess_volatility(self) -> VolatilityLevel:
        """Assess market volatility."""
        changes = [
            self._market_data.get(s, {}).get("change_pct", 0)
            for s in self.watchlist
        ]
        if not changes:
            return VolatilityLevel.MEDIUM

        avg_change = sum(abs(c) for c in changes) / len(changes)
        if avg_change > 5.0:
            return VolatilityLevel.EXTREME
        elif avg_change > 3.0:
            return VolatilityLevel.HIGH
        elif avg_change > 1.0:
            return VolatilityLevel.MEDIUM
        return VolatilityLevel.LOW

    def _assess_liquidity(self) -> LiquidityCondition:
        """Assess liquidity conditions."""
        volumes = [
            self._market_data.get(s, {}).get("volume", 0)
            for s in self.watchlist
        ]
        if not volumes:
            return LiquidityCondition.NORMAL

        avg_vol = sum(volumes) / len(volumes)
        # Simple heuristic - high volume = ample liquidity
        if avg_vol > 10000000:
            return LiquidityCondition.AMPLE
        elif avg_vol < 100000:
            return LiquidityCondition.TIGHT
        return LiquidityCondition.NORMAL

    # ── Data Feed Methods ───────────────────────────────────────

    def update_market_data(
        self, symbol: str, price: float, change_pct: float = 0,
        volume: int = 0, sector: str = "", **kwargs
    ) -> None:
        """Update market data for a symbol."""
        self._market_data[symbol] = {
            "price": price,
            "change_pct": change_pct,
            "volume": volume,
            "sector": sector,
            "updated_at": time.time(),
            **kwargs,
        }
        if symbol not in self.watchlist:
            self.watchlist.append(symbol)
            self.memory.set_working("watchlist", self.watchlist)

    def update_macro(
        self, indicator: str, value: float
    ) -> None:
        """Update a macro indicator."""
        self.memory.learn_fact(f"macro.{indicator}", value)

    def get_regime_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get historical regime data."""
        return self._regime_history[-limit:]

    def get_current_state(self) -> Dict[str, Any]:
        """Get current market state summary."""
        return {
            "regime": self.memory.get_working("current_regime", "unknown"),
            "trend": self.memory.get_working("current_trend", "neutral"),
            "volatility": self.memory.get_working("current_volatility", "medium"),
            "watchlist_size": len(self.watchlist),
            "last_scan": self._last_scan_time,
        }

    def get_status_report(self) -> Dict[str, Any]:
        report = super().get_status_report()
        report.update({
            "watchlist_size": len(self.watchlist),
            "market_data_symbols": len(self._market_data),
            "current_state": self.get_current_state(),
        })
        return report
