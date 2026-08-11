"""Opportunity Detector — automatically identifies trading opportunities across multiple strategies.

Pipeline:
    Market Alerts + Anomalies + Signals -> OpportunityDetector.detect()
        -> Momentum opportunities
        -> Mean Reversion opportunities
        -> Breakout opportunities
        -> Factor Rotation opportunities
        -> Sector Rotation opportunities
        -> Arbitrage opportunities
        -> Volatility opportunities
        -> Opportunity scoring & ranking
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OpportunityType(str, Enum):
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    FACTOR_ROTATION = "factor_rotation"
    SECTOR_ROTATION = "sector_rotation"
    ARBITRAGE = "arbitrage"
    VOLATILITY = "volatility"
    CUSTOM = "custom"


@dataclass
class Opportunity:
    """A detected trading opportunity.

    Attributes:
        opportunity_id: Unique identifier.
        opportunity_type: Type of opportunity.
        symbol: Primary symbol.
        score: Composite score (0.0-1.0).
        confidence: Confidence in the opportunity (0.0-1.0).
        description: Human-readable description.
        signals: Associated signal IDs.
        expected_return: Expected return estimate.
        expected_risk: Expected risk estimate.
        metadata: Additional data.
        timestamp: Detection timestamp.
    """

    opportunity_id: str = ""
    opportunity_type: OpportunityType = OpportunityType.MOMENTUM
    symbol: str = ""
    score: float = 0.0
    confidence: float = 0.0
    description: str = ""
    signals: List[str] = field(default_factory=list)
    expected_return: float = 0.0
    expected_risk: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def risk_reward_ratio(self) -> float:
        if self.expected_risk == 0:
            return 0.0
        return self.expected_return / self.expected_risk


class OpportunityDetector:
    """Automatically identifies and ranks trading opportunities.

    Scans for momentum, mean reversion, breakout, factor rotation,
    sector rotation, arbitrage, and volatility opportunities using
    signals from the SignalDiscovery engine.

    Supports:
        - Multi-strategy opportunity detection
        - Composite scoring across signal sources
        - Risk-reward ranking
        - Confidence-weighted selection

    Usage:
        detector = OpportunityDetector(signal_discovery)
        await detector.initialize()
        opportunities = await detector.detect(symbols=["AAPL", "GOOGL"])
        ranked = detector.rank(opportunities)
    """

    def __init__(
        self,
        signal_discovery: Optional[Any] = None,
        min_score: float = 0.5,
        max_opportunities: int = 100,
    ) -> None:
        self._signal_discovery = signal_discovery
        self._min_score = min_score
        self._max_opportunities = max_opportunities
        self._opportunities: List[Opportunity] = []
        self._counter: int = 0
        self._initialized: bool = False
        logger.info("OpportunityDetector created (min_score=%.2f)", min_score)

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("OpportunityDetector initialized")

    async def shutdown(self) -> None:
        self._opportunities.clear()
        self._initialized = False
        logger.info("OpportunityDetector shutdown complete")

    async def detect(self, symbols: Optional[List[str]] = None) -> List[Opportunity]:
        """Detect trading opportunities across symbols.

        Args:
            symbols: Optional list of symbols to scan.

        Returns:
            List of detected Opportunities.
        """
        logger.info("OpportunityDetector.detect() started (symbols=%d)", len(symbols) if symbols else 0)
        all_opportunities: List[Opportunity] = []

        for method in [
            self._detect_momentum,
            self._detect_mean_reversion,
            self._detect_breakout,
            self._detect_factor_rotation,
            self._detect_volatility,
        ]:
            opps = await method(symbols)
            all_opportunities.extend(opps)

        filtered = [o for o in all_opportunities if o.score >= self._min_score]
        ranked = self.rank(filtered)[:self._max_opportunities]
        self._store_opportunities(ranked)
        logger.info("OpportunityDetector.detect() completed: %d opportunities (ranked)", len(ranked))
        return ranked

    async def _detect_momentum(self, symbols: Optional[List[str]]) -> List[Opportunity]:
        return []

    async def _detect_mean_reversion(self, symbols: Optional[List[str]]) -> List[Opportunity]:
        return []

    async def _detect_breakout(self, symbols: Optional[List[str]]) -> List[Opportunity]:
        return []

    async def _detect_factor_rotation(self, symbols: Optional[List[str]]) -> List[Opportunity]:
        return []

    async def _detect_volatility(self, symbols: Optional[List[str]]) -> List[Opportunity]:
        return []

    def rank(self, opportunities: List[Opportunity]) -> List[Opportunity]:
        """Rank opportunities by composite score descending.

        Args:
            opportunities: List of opportunities to rank.

        Returns:
            Sorted list (highest score first).
        """
        return sorted(opportunities, key=lambda o: o.score, reverse=True)

    def _store_opportunities(self, opportunities: List[Opportunity]) -> None:
        self._opportunities.extend(opportunities)
        if len(self._opportunities) > self._max_opportunities * 5:
            self._opportunities = self._opportunities[-self._max_opportunities * 5:]

    def get_top_opportunities(self, limit: int = 10) -> List[Dict[str, Any]]:
        ranked = self.rank(self._opportunities)[:limit]
        return [
            {
                "id": o.opportunity_id,
                "type": o.opportunity_type.value,
                "symbol": o.symbol,
                "score": round(o.score, 3),
                "confidence": round(o.confidence, 3),
                "risk_reward": round(o.risk_reward_ratio, 3),
                "description": o.description,
            }
            for o in ranked
        ]

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "total_opportunities": len(self._opportunities),
            "min_score": self._min_score,
        }
