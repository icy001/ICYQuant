"""News Agent — specialized agent for news monitoring, sentiment analysis, and event detection.

Pipeline:
    News feed / data source
        -> NewsAgent.monitor() (watch for relevant news)
        -> NewsAgent.analyze_sentiment() (NLP sentiment analysis)
        -> NewsAgent.detect_events() (identify market-moving events)
        -> publish to blackboard / message bus
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from services.ai_agent.collaboration.message_bus import MessageBus, Message, MessageType

logger = logging.getLogger(__name__)


class SentimentLabel(str, Enum):
    """Sentiment labels."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class EventImpact(str, Enum):
    """Impact level of a news event."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class NewsItem:
    """A news article or headline.

    Attributes:
        news_id: Unique news identifier.
        headline: News headline.
        source: News source.
        symbols: Related symbols.
        sentiment: Sentiment label.
        sentiment_score: Sentiment score (-1.0 to 1.0).
        impact: Estimated market impact.
        published_at: Publication timestamp.
    """

    news_id: str = field(default_factory=lambda: uuid4().hex)
    headline: str = ""
    source: str = ""
    symbols: List[str] = field(default_factory=list)
    sentiment: SentimentLabel = SentimentLabel.NEUTRAL
    sentiment_score: float = 0.0
    impact: EventImpact = EventImpact.LOW
    published_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class NewsAgent:
    """Specialized agent for news monitoring and sentiment analysis.

    Monitors news feeds, analyzes sentiment, detects market-moving events,
    and publishes findings for other agents.

    Supports:
        - News monitoring and filtering
        - Sentiment analysis (positive/negative/neutral)
        - Event impact assessment
        - Symbol association
        - News alerting

    Usage:
        agent = NewsAgent(agent_id="news_1", message_bus=bus)
        await agent.initialize()
        items = await agent.monitor(["AAPL", "TSLA"])
        analyzed = await agent.analyze_sentiment(items)
    """

    def __init__(
        self,
        agent_id: str = "",
        message_bus: Optional[MessageBus] = None,
    ) -> None:
        """Initialize the News Agent.

        Args:
            agent_id: Unique agent identifier.
            message_bus: Message bus for communication.
        """
        self._agent_id: str = agent_id or uuid4().hex[:12]
        self._message_bus: Optional[MessageBus] = message_bus
        self._initialized: bool = False
        self._news_items: List[NewsItem] = []
        self._watched_symbols: List[str] = []
        logger.info("NewsAgent created: %s", self._agent_id)

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the news agent."""
        if self._initialized:
            return
        self._initialized = True
        logger.info("NewsAgent initialized: %s", self._agent_id)

    async def shutdown(self) -> None:
        """Shut down the news agent."""
        self._news_items.clear()
        self._watched_symbols.clear()
        self._initialized = False
        logger.info("NewsAgent shutdown: %s", self._agent_id)

    # ── Monitoring ──

    async def monitor(self, symbols: Optional[List[str]] = None) -> List[NewsItem]:
        """Monitor news for specified symbols.

        Args:
            symbols: List of symbols to monitor. Uses watched symbols if not provided.

        Returns:
            List of relevant news items.
        """
        targets = symbols or self._watched_symbols
        items: List[NewsItem] = []

        for symbol in targets:
            item = NewsItem(
                headline=f"Market update for {symbol}",
                source="market_feed",
                symbols=[symbol],
                sentiment=SentimentLabel.NEUTRAL,
                impact=EventImpact.LOW,
            )
            items.append(item)
            self._news_items.append(item)

        logger.info("NewsAgent monitored %d symbols, found %d items",
                    len(targets), len(items))
        return items

    # ── Sentiment Analysis ──

    async def analyze_sentiment(self, items: List[NewsItem]) -> List[NewsItem]:
        """Analyze sentiment for news items.

        Args:
            items: News items to analyze.

        Returns:
            News items with sentiment scores.
        """
        for item in items:
            # Simple keyword-based sentiment
            positive_words = ["surge", "rally", "beat", "upgrade", "growth", "profit"]
            negative_words = ["drop", "fall", "miss", "downgrade", "loss", "risk"]

            headline_lower = item.headline.lower()
            pos_count = sum(1 for w in positive_words if w in headline_lower)
            neg_count = sum(1 for w in negative_words if w in headline_lower)

            if pos_count > neg_count:
                item.sentiment = SentimentLabel.POSITIVE
                item.sentiment_score = 0.5
            elif neg_count > pos_count:
                item.sentiment = SentimentLabel.NEGATIVE
                item.sentiment_score = -0.5
            else:
                item.sentiment = SentimentLabel.NEUTRAL
                item.sentiment_score = 0.0

        # Publish high-impact items
        for item in items:
            if item.impact in (EventImpact.HIGH, EventImpact.CRITICAL):
                await self._publish_alert(item)

        return items

    async def detect_events(self, items: List[NewsItem]) -> List[NewsItem]:
        """Detect market-moving events from news items.

        Args:
            items: News items to analyze.

        Returns:
            Items with impact assessment.
        """
        for item in items:
            if abs(item.sentiment_score) > 0.7:
                item.impact = EventImpact.HIGH
            elif abs(item.sentiment_score) > 0.3:
                item.impact = EventImpact.MEDIUM
            else:
                item.impact = EventImpact.LOW

        high_impact = [i for i in items if i.impact in (EventImpact.HIGH, EventImpact.CRITICAL)]
        logger.info("NewsAgent detected %d high-impact events", len(high_impact))
        return items

    # ── Publication ──

    async def _publish_alert(self, item: NewsItem) -> None:
        """Publish a news alert.

        Args:
            item: The news item.
        """
        if self._message_bus:
            await self._message_bus.publish(Message(
                msg_type=MessageType.PUBLISH,
                topic="news.alert",
                sender_id=self._agent_id,
                payload={
                    "headline": item.headline,
                    "symbols": item.symbols,
                    "sentiment": item.sentiment.value,
                    "impact": item.impact.value,
                },
            ))

    async def watch_symbols(self, symbols: List[str]) -> None:
        """Add symbols to the watch list.

        Args:
            symbols: Symbols to watch.
        """
        for sym in symbols:
            if sym not in self._watched_symbols:
                self._watched_symbols.append(sym)

    # ── Properties ──

    @property
    def agent_id(self) -> str:
        """Return the agent ID."""
        return self._agent_id

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the news agent state.

        Returns:
            Dict with item count and watched symbols.
        """
        return {
            "agent_id": self._agent_id,
            "initialized": self._initialized,
            "total_items": len(self._news_items),
            "watched_symbols": self._watched_symbols,
        }
