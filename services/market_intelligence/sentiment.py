from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SentimentIndex(str, Enum):
    EXTREME_FEAR = "EXTREME_FEAR"
    FEAR = "FEAR"
    NEUTRAL = "NEUTRAL"
    GREED = "GREED"
    EXTREME_GREED = "EXTREME_GREED"


class SentimentSource(str, Enum):
    NEWS = "NEWS"
    SOCIAL_MEDIA = "SOCIAL_MEDIA"
    OPTIONS = "OPTIONS"
    POSITIONING = "POSITIONING"
    SURVEY = "SURVEY"


@dataclass
class SentimentData:
    source: SentimentSource
    fear_greed_score: int  # 0-100, 0=extreme fear, 100=extreme greed
    confidence: float
    put_call_ratio: float = 1.0
    vix_level: float = 0.0
    bullish_pct: float = 0.5
    volume_ratio: float = 1.0


@dataclass
class SentimentReport:
    overall_index: SentimentIndex
    score: int
    confidence: float
    components: Dict[SentimentSource, int]
    divergence_warning: bool
    contrarian_signal: bool
    interpretation: str


class SentimentAnalysisEngine:
    """Sentiment Analysis Engine - measures and interprets market sentiment."""

    def __init__(self):
        self.history: List[SentimentReport] = []
        self.extreme_fear_threshold = 20
        self.extreme_greed_threshold = 80

    def analyze(self, market):
        """Analyze market sentiment.

        Args:
            market: Market sentiment data - can be SentimentData dataclass or dict/symbol.

        Returns:
            Dict containing sentiment analysis result.
        """
        if isinstance(market, SentimentData):
            return self._analyze_sentiment(market)
        return {"sentiment": market}

    def _analyze_sentiment(self, data: SentimentData) -> dict:
        score = data.fear_greed_score
        index = self._classify_sentiment(score)
        contrarian = self._detect_contrarian(data)
        divergence = self._detect_divergence(data)

        interpretation = self._interpret_sentiment(index, contrarian, divergence)

        return {
            "sentiment": {
                "overall_index": index.value,
                "score": score,
                "confidence": round(data.confidence, 2),
                "source": data.source.value,
                "put_call_ratio": data.put_call_ratio,
                "vix_level": data.vix_level,
                "bullish_pct": round(data.bullish_pct, 2),
                "contrarian_signal": contrarian,
                "divergence_warning": divergence,
                "interpretation": interpretation,
            }
        }

    def _classify_sentiment(self, score: int) -> SentimentIndex:
        if score <= self.extreme_fear_threshold:
            return SentimentIndex.EXTREME_FEAR
        elif score <= 40:
            return SentimentIndex.FEAR
        elif score <= 60:
            return SentimentIndex.NEUTRAL
        elif score <= self.extreme_greed_threshold:
            return SentimentIndex.GREED
        return SentimentIndex.EXTREME_GREED

    def _detect_contrarian(self, data: SentimentData) -> bool:
        """Detect contrarian signals (extreme sentiment = reversal potential)."""
        return data.fear_greed_score <= self.extreme_fear_threshold or data.fear_greed_score >= self.extreme_greed_threshold

    def _detect_divergence(self, data: SentimentData) -> bool:
        """Detect divergence between sentiment and options positioning."""
        if data.put_call_ratio > 1.5 and data.bullish_pct > 0.6:
            return True
        if data.put_call_ratio < 0.5 and data.bullish_pct < 0.4:
            return True
        return False

    def _interpret_sentiment(self, index: SentimentIndex, contrarian: bool, divergence: bool) -> str:
        base = {
            SentimentIndex.EXTREME_FEAR: "Market is in extreme fear - historically bullish contrarian signal",
            SentimentIndex.FEAR: "Bearish sentiment dominates - cautious positioning recommended",
            SentimentIndex.NEUTRAL: "Market sentiment is balanced - no strong directional bias",
            SentimentIndex.GREED: "Bullish sentiment dominates - watch for overbought conditions",
            SentimentIndex.EXTREME_GREED: "Market is in extreme greed - historically bearish contrarian signal",
        }.get(index, "")

        if contrarian:
            base += " | CONTRARIAN SIGNAL: sentiment extremes often precede reversals"
        if divergence:
            base += " | DIVERGENCE WARNING: sentiment disconnected from options positioning"

        return base

    def aggregate_multi_source(self, data_sources: List[SentimentData]) -> SentimentReport:
        """Aggregate sentiment from multiple sources."""
        if not data_sources:
            return SentimentReport(
                overall_index=SentimentIndex.NEUTRAL,
                score=50,
                confidence=0.5,
                components={},
                divergence_warning=False,
                contrarian_signal=False,
                interpretation="No data available",
            )

        weighted_score = sum(d.fear_greed_score * d.confidence for d in data_sources) / max(sum(d.confidence for d in data_sources), 1)
        components = {d.source: d.fear_greed_score for d in data_sources}
        avg_confidence = sum(d.confidence for d in data_sources) / len(data_sources)

        return SentimentReport(
            overall_index=self._classify_sentiment(int(weighted_score)),
            score=int(weighted_score),
            confidence=avg_confidence,
            components=components,
            divergence_warning=any(self._detect_divergence(d) for d in data_sources),
            contrarian_signal=self._detect_contrarian(SentimentData(
                source=SentimentSource.NEWS,
                fear_greed_score=int(weighted_score),
                confidence=avg_confidence,
            )),
            interpretation="Multi-source aggregated sentiment",
        )
