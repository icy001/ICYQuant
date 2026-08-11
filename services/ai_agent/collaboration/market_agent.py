"""Market Agent — specialized agent for market data analysis and monitoring.

Pipeline:
    Market data event / Coordinator assignment
        -> MarketAgent.analyze() (market analysis)
        -> MarketAgent.detect_signals() (signal detection)
        -> MarketAgent.publish_observation() (post to blackboard)
        -> MessageBus (notify other agents)

Responsible for all market-related analysis: price movements, volatility,
trend detection, market regime identification.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from services.ai_agent.collaboration.agent_registry import (
    AgentRegistration,
    AgentRegistry,
    AgentRole,
    AgentStatus,
)
from services.ai_agent.collaboration.message_bus import MessageBus, Message, MessageType

logger = logging.getLogger(__name__)


class MarketRegime(str, Enum):
    """Market regime classifications."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    SIDEWAYS = "sideways"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


@dataclass
class MarketObservation:
    """A market analysis observation.

    Attributes:
        symbol: Trading symbol.
        price: Current price.
        regime: Detected market regime.
        volatility: Volatility measure.
        trend_strength: Trend strength (0.0 - 1.0).
        signals: Detected signals.
        timestamp: Observation timestamp.
    """

    symbol: str = ""
    price: float = 0.0
    regime: MarketRegime = MarketRegime.UNKNOWN
    volatility: float = 0.0
    trend_strength: float = 0.0
    signals: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MarketAgent:
    """Specialized agent for market data analysis and monitoring.

    Analyzes market conditions, detects trends and regimes, identifies
    trading signals, and publishes observations for other agents.

    Supports:
        - Market regime detection
        - Trend and volatility analysis
        - Signal detection
        - Market data subscription
        - Observation publishing

    Usage:
        agent = MarketAgent(agent_id="market_1", message_bus=bus)
        await agent.initialize()
        obs = await agent.analyze("AAPL", market_data)
    """

    def __init__(
        self,
        agent_id: str = "",
        message_bus: Optional[MessageBus] = None,
    ) -> None:
        """Initialize the Market Agent.

        Args:
            agent_id: Unique agent identifier.
            message_bus: Message bus for communication.
        """
        self._agent_id: str = agent_id or uuid4().hex[:12]
        self._message_bus: Optional[MessageBus] = message_bus
        self._initialized: bool = False
        self._observations: List[MarketObservation] = []
        self._subscribed_symbols: List[str] = []
        logger.info("MarketAgent created: %s", self._agent_id)

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the market agent."""
        if self._initialized:
            return
        self._initialized = True
        logger.info("MarketAgent initialized: %s", self._agent_id)

    async def shutdown(self) -> None:
        """Shut down the market agent."""
        self._observations.clear()
        self._subscribed_symbols.clear()
        self._initialized = False
        logger.info("MarketAgent shutdown: %s", self._agent_id)

    # ── Analysis ──

    async def analyze(self, symbol: str, market_data: Optional[Dict[str, Any]] = None) -> MarketObservation:
        """Analyze market conditions for a symbol.

        Args:
            symbol: Trading symbol.
            market_data: Optional market data.

        Returns:
            MarketObservation with analysis results.
        """
        data = market_data or {}
        price = data.get("price", 0.0)
        change_pct = data.get("change_pct", 0.0)
        volatility = data.get("volatility", 0.0)

        # Detect regime
        regime = self._detect_regime(change_pct, volatility)

        # Detect signals
        signals = self._detect_signals(data)

        obs = MarketObservation(
            symbol=symbol,
            price=price,
            regime=regime,
            volatility=volatility,
            trend_strength=abs(change_pct) / 5.0 if abs(change_pct) > 0 else 0.0,
            signals=signals,
        )
        self._observations.append(obs)

        # Publish to message bus
        if self._message_bus:
            await self._message_bus.publish(Message(
                msg_type=MessageType.PUBLISH,
                topic="market.analysis",
                sender_id=self._agent_id,
                payload={
                    "symbol": symbol,
                    "regime": regime.value,
                    "price": price,
                    "signals": signals,
                },
            ))

        logger.debug("MarketAgent analyzed %s: regime=%s, signals=%s",
                     symbol, regime.value, signals)
        return obs

    # ── Detection ──

    def _detect_regime(self, change_pct: float, volatility: float) -> MarketRegime:
        """Detect market regime from indicators.

        Args:
            change_pct: Price change percentage.
            volatility: Volatility measure.

        Returns:
            Detected market regime.
        """
        if volatility > 0.3:
            return MarketRegime.VOLATILE
        if change_pct > 2.0:
            return MarketRegime.BULLISH
        if change_pct < -2.0:
            return MarketRegime.BEARISH
        if abs(change_pct) < 0.5:
            return MarketRegime.SIDEWAYS
        return MarketRegime.UNKNOWN

    def _detect_signals(self, data: Dict[str, Any]) -> List[str]:
        """Detect trading signals from market data.

        Args:
            data: Market data dictionary.

        Returns:
            List of detected signal strings.
        """
        signals: List[str] = []
        rsi = data.get("rsi", 50)
        macd = data.get("macd_signal", 0)

        if rsi < 30:
            signals.append("oversold")
        elif rsi > 70:
            signals.append("overbought")
        if macd > 0:
            signals.append("macd_bullish")
        elif macd < 0:
            signals.append("macd_bearish")

        return signals

    # ── Subscription ──

    async def subscribe_symbol(self, symbol: str) -> None:
        """Subscribe to market data for a symbol.

        Args:
            symbol: Trading symbol.
        """
        if symbol not in self._subscribed_symbols:
            self._subscribed_symbols.append(symbol)
            logger.debug("MarketAgent subscribed to %s", symbol)

    # ── Properties ──

    @property
    def agent_id(self) -> str:
        """Return the agent ID."""
        return self._agent_id

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the market agent state.

        Returns:
            Dict with analysis count and subscriptions.
        """
        return {
            "agent_id": self._agent_id,
            "initialized": self._initialized,
            "observations": len(self._observations),
            "subscribed_symbols": self._subscribed_symbols,
        }
