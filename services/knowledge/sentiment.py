"""
Sentiment Analysis Engine.

Computes market sentiment with:
- Document-level sentiment scoring
- Aggregate sentiment per symbol/sector
- Sentiment momentum and acceleration
- Multi-dimensional sentiment tracking
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Enums ────────────────────────────────────────────────────────────────────

class SentimentDirection(str, Enum):
    VERY_BULLISH = "very_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    VERY_BEARISH = "very_bearish"


class SentimentTrend(str, Enum):
    STRENGTHENING = "strengthening"
    WEAKENING = "weakening"
    STABLE = "stable"
    REVERSING = "reversing"


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class SentimentResult:
    """Sentiment analysis result for a single document."""

    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""
    symbol: str = ""

    # Primary scores
    direction: SentimentDirection = SentimentDirection.NEUTRAL
    score: float = 0.5  # 0=very bearish, 1=very bullish

    # Confidence
    confidence: float = 0.0

    # Dimensions
    dimensions: Dict[str, float] = field(default_factory=dict)
    # e.g. {"earnings": 0.8, "technical": 0.3, "macro": -0.2}

    # Keywords and evidence
    evidence_keywords: List[str] = field(default_factory=list)
    evidence_phrases: List[str] = field(default_factory=list)

    # Timestamp
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Metadata
    source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "document_id": self.document_id,
            "symbol": self.symbol,
            "direction": self.direction.value,
            "score": self.score,
            "confidence": self.confidence,
            "dimensions": self.dimensions,
            "evidence_keywords": self.evidence_keywords,
            "analyzed_at": self.analyzed_at.isoformat(),
            "source": self.source,
        }


@dataclass
class SentimentMomentum:
    """Sentiment momentum tracking over time."""

    symbol: str = ""
    current_score: float = 0.5
    previous_score: float = 0.5
    change: float = 0.0
    direction: SentimentDirection = SentimentDirection.NEUTRAL
    trend: SentimentTrend = SentimentTrend.STABLE
    volatility: float = 0.0
    num_samples: int = 0
    window_days: int = 30
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "current_score": self.current_score,
            "previous_score": self.previous_score,
            "change": self.change,
            "direction": self.direction.value,
            "trend": self.trend.value,
            "volatility": self.volatility,
            "num_samples": self.num_samples,
            "window_days": self.window_days,
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class SentimentAcceleration:
    """Sentiment acceleration (second derivative of sentiment)."""

    symbol: str = ""
    momentum: float = 0.0  # current momentum
    previous_momentum: float = 0.0
    acceleration: float = 0.0  # change in momentum
    accelerating: bool = False
    decelerating: bool = False
    inflection_detected: bool = False
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "momentum": self.momentum,
            "previous_momentum": self.previous_momentum,
            "acceleration": self.acceleration,
            "accelerating": self.accelerating,
            "decelerating": self.decelerating,
            "inflection_detected": self.inflection_detected,
        }


@dataclass
class SentimentConfig:
    """Configuration for sentiment engine."""

    # Direction thresholds
    very_bullish_threshold: float = 0.8
    bullish_threshold: float = 0.6
    bearish_threshold: float = 0.4
    very_bearish_threshold: float = 0.2

    # Momentum
    momentum_window_days: int = 30
    acceleration_window_days: int = 7
    min_samples_for_momentum: int = 5

    # Trend detection
    trend_change_threshold: float = 0.1  # minimum score change for trend shift

    # Confidence
    min_confidence: float = 0.1

    # Dimension weights
    dimension_weights: Dict[str, float] = field(default_factory=lambda: {
        "earnings": 1.0,
        "technical": 0.8,
        "macro": 0.9,
        "sentiment": 1.2,
        "regulation": 0.7,
        "industry": 0.6,
    })


# ── Sentiment Engine ─────────────────────────────────────────────────────────

class SentimentEngine:
    """
    Sentiment analysis engine for financial text.

    Features:
    - Document-level sentiment scoring
    - Multi-dimensional sentiment decomposition
    - Sentiment momentum (rate of change)
    - Sentiment acceleration (second derivative)
    - Aggregate sentiment per symbol/sector
    """

    # Sentiment lexicon
    BULLISH_TERMS: Dict[str, float] = {
        # Strong bullish
        "surge": 0.9, "soar": 0.95, "rocket": 0.95, "breakthrough": 0.9,
        "record high": 0.9, "blowout": 0.9, "blockbuster": 0.9,
        # Moderate bullish
        "beat": 0.75, "exceed": 0.7, "outperform": 0.8, "upgrade": 0.8,
        "growth": 0.7, "expansion": 0.7, "positive": 0.7,
        "strong": 0.75, "robust": 0.7, "impressive": 0.7,
        "bullish": 0.85, "optimistic": 0.75, "momentum": 0.65,
        "rally": 0.8, "rebound": 0.65, "upside": 0.7,
        "guidance raised": 0.8, "raised target": 0.8,
        # Mild bullish
        "improve": 0.6, "increase": 0.6, "gain": 0.6, "advance": 0.6,
        "opportunity": 0.65, "potential": 0.6, "promising": 0.65,
    }

    BEARISH_TERMS: Dict[str, float] = {
        # Strong bearish
        "plunge": 0.1, "crash": 0.05, "collapse": 0.05, "crisis": 0.05,
        "bankruptcy": 0.02, "default": 0.05, "catastrophic": 0.05,
        # Moderate bearish
        "miss": 0.25, "decline": 0.3, "downgrade": 0.2, "underperform": 0.2,
        "loss": 0.2, "weak": 0.25, "concern": 0.3, "warning": 0.25,
        "risk": 0.3, "bearish": 0.15, "pessimistic": 0.25,
        "sell-off": 0.2, "downturn": 0.25, "headwind": 0.3,
        "guidance lowered": 0.2, "cut target": 0.2,
        # Mild bearish
        "slow": 0.35, "pressure": 0.35, "challenge": 0.35, "uncertain": 0.35,
        "volatile": 0.4, "cautious": 0.35,
    }

    def __init__(self, config: Optional[SentimentConfig] = None):
        self.config = config or SentimentConfig()
        self._results: List[SentimentResult] = []
        self._momentum_cache: Dict[str, SentimentMomentum] = {}
        self._acceleration_cache: Dict[str, SentimentAcceleration] = {}

    # ── Document-Level Sentiment ─────────────────────────────────────────────

    def analyze(
        self,
        document_id: str,
        text: str,
        symbol: str = "",
        source: str = "",
        **kwargs,
    ) -> SentimentResult:
        """
        Analyze sentiment of a document.

        Args:
            document_id: Document identifier.
            text: Text content to analyze.
            symbol: Associated stock symbol.
            source: Data source.

        Returns:
            SentimentResult with scores and evidence.
        """
        text_lower = text.lower()

        # Score from lexicon
        raw_score, hits, total = self._lexicon_score(text_lower)

        # Evidence
        evidence = [kw for kw, _ in hits]

        # Determine direction
        direction = self._score_to_direction(raw_score)

        # Confidence based on hit density
        confidence = min(total / 20.0, 1.0) if total > 0 else 0.1

        # Multi-dimensional breakdown
        dimensions = self._dimension_breakdown(text_lower)

        result = SentimentResult(
            document_id=document_id,
            symbol=symbol,
            direction=direction,
            score=raw_score,
            confidence=confidence,
            dimensions=dimensions,
            evidence_keywords=evidence,
            source=source,
        )

        self._results.append(result)
        return result

    def analyze_batch(
        self,
        documents: List[Tuple[str, str, str]],
    ) -> List[SentimentResult]:
        """Batch sentiment analysis. Each tuple: (doc_id, text, symbol)."""
        return [
            self.analyze(doc_id, text, symbol)
            for doc_id, text, symbol in documents
        ]

    # ── Lexicon Scoring ──────────────────────────────────────────────────────

    def _lexicon_score(
        self, text: str
    ) -> Tuple[float, List[Tuple[str, float]], int]:
        """Score text using sentiment lexicon."""
        hits: List[Tuple[str, float]] = []

        for term, score in self.BULLISH_TERMS.items():
            if term in text:
                hits.append((term, score))
        for term, score in self.BEARISH_TERMS.items():
            if term in text:
                hits.append((term, score))

        if not hits:
            return 0.5, [], 0

        # Weighted average of hits (weighted by distance from neutral 0.5)
        total_weight = sum(abs(s - 0.5) for _, s in hits)
        if total_weight == 0:
            return 0.5, hits, len(hits)

        weighted_sum = sum(s * abs(s - 0.5) for _, s in hits)
        return weighted_sum / total_weight, hits, len(hits)

    def _score_to_direction(self, score: float) -> SentimentDirection:
        """Convert numeric score to sentiment direction."""
        if score >= self.config.very_bullish_threshold:
            return SentimentDirection.VERY_BULLISH
        elif score >= self.config.bullish_threshold:
            return SentimentDirection.BULLISH
        elif score <= self.config.very_bearish_threshold:
            return SentimentDirection.VERY_BEARISH
        elif score <= self.config.bearish_threshold:
            return SentimentDirection.BEARISH
        else:
            return SentimentDirection.NEUTRAL

    # ── Dimension Breakdown ──────────────────────────────────────────────────

    DIMENSION_KEYWORDS: Dict[str, Dict[str, float]] = {
        "earnings": {
            "earnings": 0.7, "revenue": 0.6, "profit": 0.7, "eps": 0.8,
            "margin": 0.5, "beat": 0.75, "miss": 0.25, "guidance": 0.6,
        },
        "technical": {
            "breakout": 0.8, "support": 0.5, "resistance": 0.5,
            "moving average": 0.4, "rsi": 0.4, "volume": 0.4,
        },
        "macro": {
            "gdp": 0.5, "inflation": 0.4, "fed": 0.6, "interest rate": 0.6,
            "recession": 0.2, "growth": 0.7, "stimulus": 0.7,
        },
        "sentiment": {
            "bullish": 0.85, "bearish": 0.15, "sentiment": 0.5,
            "fear": 0.2, "greed": 0.8,
        },
        "regulation": {
            "regulation": 0.3, "approval": 0.7, "investigation": 0.2,
            "fine": 0.1, "compliance": 0.5,
        },
        "industry": {
            "sector": 0.5, "industry": 0.5, "competition": 0.4,
            "market share": 0.7, "disruption": 0.6,
        },
    }

    def _dimension_breakdown(self, text: str) -> Dict[str, float]:
        """Compute sentiment score per dimension."""
        dimensions: Dict[str, float] = {}
        for dim, keywords in self.DIMENSION_KEYWORDS.items():
            hits = [s for kw, s in keywords.items() if kw in text]
            if hits:
                dimensions[dim] = sum(hits) / len(hits)
            else:
                dimensions[dim] = 0.5  # neutral default

        return dimensions

    # ── Aggregate Sentiment ──────────────────────────────────────────────────

    def get_symbol_sentiment(
        self, symbol: str, window_days: Optional[int] = None
    ) -> SentimentResult:
        """Get aggregate sentiment for a symbol."""
        results = [r for r in self._results if r.symbol == symbol]

        if window_days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
            results = [r for r in results if r.analyzed_at >= cutoff]

        if not results:
            return SentimentResult(symbol=symbol, direction=SentimentDirection.NEUTRAL, score=0.5)

        avg_score = sum(r.score for r in results) / len(results)
        avg_confidence = sum(r.confidence for r in results) / len(results)

        # Aggregate dimensions
        dim_sums: Dict[str, List[float]] = defaultdict(list)
        for r in results:
            for dim, score in r.dimensions.items():
                dim_sums[dim].append(score)
        agg_dims = {dim: sum(scores) / len(scores) for dim, scores in dim_sums.items()}

        return SentimentResult(
            symbol=symbol,
            direction=self._score_to_direction(avg_score),
            score=avg_score,
            confidence=avg_confidence,
            dimensions=agg_dims,
            evidence_keywords=list(set(
                kw for r in results for kw in r.evidence_keywords
            )),
        )

    # ── Sentiment Momentum ───────────────────────────────────────────────────

    def compute_momentum(
        self, symbol: str, window_days: Optional[int] = None
    ) -> SentimentMomentum:
        """
        Compute sentiment momentum for a symbol.

        Momentum = current sentiment - previous period sentiment.
        """
        window = window_days or self.config.momentum_window_days
        results = [r for r in self._results if r.symbol == symbol]

        if len(results) < self.config.min_samples_for_momentum:
            return SentimentMomentum(
                symbol=symbol,
                num_samples=len(results),
                window_days=window,
            )

        # Sort by time
        results.sort(key=lambda r: r.analyzed_at)

        # Current window
        cutoff = datetime.now(timezone.utc) - timedelta(days=window)
        current = [r for r in results if r.analyzed_at >= cutoff]
        previous = [r for r in results if r.analyzed_at < cutoff]

        if not current or not previous:
            return SentimentMomentum(
                symbol=symbol,
                current_score=(
                    sum(r.score for r in current) / len(current)
                    if current else 0.5
                ),
                num_samples=len(results),
                window_days=window,
            )

        current_score = sum(r.score for r in current) / len(current)
        previous_score = sum(r.score for r in previous) / len(previous)
        change = current_score - previous_score

        # Trend detection
        if abs(change) < self.config.trend_change_threshold:
            trend = SentimentTrend.STABLE
        elif change > 0:
            trend = SentimentTrend.STRENGTHENING
        else:
            trend = SentimentTrend.WEAKENING

        # Volatility
        all_scores = [r.score for r in results[-30:]]
        volatility = (
            (sum((s - current_score) ** 2 for s in all_scores) / len(all_scores)) ** 0.5
            if all_scores else 0.0
        )

        momentum = SentimentMomentum(
            symbol=symbol,
            current_score=current_score,
            previous_score=previous_score,
            change=change,
            direction=self._score_to_direction(current_score),
            trend=trend,
            volatility=volatility,
            num_samples=len(results),
            window_days=window,
        )
        self._momentum_cache[symbol] = momentum
        return momentum

    # ── Sentiment Acceleration ───────────────────────────────────────────────

    def compute_acceleration(self, symbol: str) -> SentimentAcceleration:
        """
        Compute sentiment acceleration (second derivative).

        Positive acceleration = sentiment improving at increasing rate.
        """
        momentum = self.compute_momentum(symbol)

        prev = self._momentum_cache.get(symbol)
        if prev is None:
            return SentimentAcceleration(
                symbol=symbol,
                momentum=momentum.change,
                acceleration=0.0,
            )

        accel = momentum.change - prev.change
        accelerating = accel > 0
        decelerating = accel < 0
        inflection = (momentum.change > 0) != (prev.change > 0)

        acceleration = SentimentAcceleration(
            symbol=symbol,
            momentum=momentum.change,
            previous_momentum=prev.change,
            acceleration=accel,
            accelerating=accelerating,
            decelerating=decelerating,
            inflection_detected=inflection,
        )
        self._acceleration_cache[symbol] = acceleration
        return acceleration

    # ── Query Methods ────────────────────────────────────────────────────────

    def get_results(
        self,
        symbol: Optional[str] = None,
        direction: Optional[SentimentDirection] = None,
        min_confidence: float = 0.0,
        limit: int = 100,
    ) -> List[SentimentResult]:
        """Query sentiment results."""
        results = self._results

        if symbol:
            results = [r for r in results if r.symbol == symbol]
        if direction:
            results = [r for r in results if r.direction == direction]
        if min_confidence > 0:
            results = [r for r in results if r.confidence >= min_confidence]

        return results[-limit:]

    def get_momentum(self, symbol: str) -> Optional[SentimentMomentum]:
        """Get cached momentum for a symbol."""
        return self._momentum_cache.get(symbol)

    def get_acceleration(self, symbol: str) -> Optional[SentimentAcceleration]:
        """Get cached acceleration for a symbol."""
        return self._acceleration_cache.get(symbol)

    def clear(self) -> None:
        """Clear all data."""
        self._results.clear()
        self._momentum_cache.clear()
        self._acceleration_cache.clear()
