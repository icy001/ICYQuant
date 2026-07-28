"""Sentiment Intelligence Service.

Orchestrates the full AI Sentiment Intelligence pipeline:
Data Collection → NLP Analysis → Emotion Detection → Fear & Greed →
Momentum Tracking → Divergence Detection → Alpha Generation → Memory Storage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .collector import SentimentCollector, CollectionResult
from .nlp import NLPAnalyzer, NLPAnalysisResult
from .emotion import EmotionDetector, EmotionResult
from .fear_greed import FearGreedModel, FearGreedResult
from .momentum import SentimentMomentum, SentimentMomentumResult
from .divergence import DivergenceDetector, DivergenceResult
from .alpha import SentimentAlphaGenerator, SentimentAlphaResult
from .memory import SentimentMemory, SentimentMemoryEntry
from .record import (
    SentimentRecord,
    SentimentSource,
    SentimentLabel,
    EmotionState,
    FearGreedZone,
)


@dataclass
class SentimentPipelineResult:
    """Complete result of the sentiment intelligence pipeline.

    Attributes:
        nlp_results: NLP analysis results.
        emotion: Emotion detection result.
        fear_greed: Fear & Greed index result.
        momentum: Sentiment momentum result.
        divergence: Divergence detection result.
        alpha: Sentiment alpha signals.
        summary: Pipeline execution summary.
        timestamp: Execution timestamp.
        duration_ms: Pipeline execution duration in ms.
    """

    nlp_results: list[NLPAnalysisResult] = field(default_factory=list)
    emotion: EmotionResult | None = None
    fear_greed: FearGreedResult | None = None
    momentum: SentimentMomentumResult | None = None
    divergence: DivergenceResult | None = None
    alpha: SentimentAlphaResult | None = None
    summary: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0

    @property
    def overall_sentiment(self) -> str:
        if self.fear_greed:
            return self.fear_greed.zone.value
        if self.emotion:
            return self.emotion.state.value
        return "unknown"

    @property
    def has_alpha(self) -> bool:
        return self.alpha is not None and self.alpha.has_signals

    @property
    def risk_level(self) -> str:
        if self.fear_greed:
            if self.fear_greed.is_extreme_fear:
                return "high_opportunity"
            elif self.fear_greed.is_extreme_greed:
                return "high_risk"
        return "normal"


class SentimentIntelligenceService:
    """Orchestrates the full Sentiment Intelligence pipeline.

    Coordinates all sub-engines to provide a unified interface for:
    - Text sentiment analysis
    - Emotion state detection
    - Fear & Greed index tracking
    - Sentiment momentum monitoring
    - Price-sentiment divergence detection
    - Sentiment alpha factor generation

    Attributes:
        collector: Sentiment data collector.
        nlp: NLP sentiment analyzer.
        emotion: Emotion state detector.
        fear_greed: Fear & Greed model.
        momentum: Sentiment momentum tracker.
        divergence: Price-sentiment divergence detector.
        alpha: Sentiment alpha generator.
        memory: Sentiment memory store.
    """

    def __init__(
        self,
        analyzer: NLPAnalyzer | None = None,
        collector: SentimentCollector | None = None,
        emotion: EmotionDetector | None = None,
        fear_greed: FearGreedModel | None = None,
        momentum: SentimentMomentum | None = None,
        divergence: DivergenceDetector | None = None,
        alpha: SentimentAlphaGenerator | None = None,
        memory: SentimentMemory | None = None,
    ) -> None:
        self.analyzer = analyzer or NLPAnalyzer()
        self.collector = collector or SentimentCollector()
        self.emotion_detector = emotion or EmotionDetector()
        self.fear_greed_model = fear_greed or FearGreedModel()
        self.momentum_engine = momentum or SentimentMomentum()
        self.divergence_detector = divergence or DivergenceDetector()
        self.alpha_generator = alpha or SentimentAlphaGenerator()
        self.memory_store = memory or SentimentMemory()

    # --- Single Text Analysis ---

    def analyze(self, text: str) -> dict[str, Any]:
        """Analyze sentiment from a single text.

        Args:
            text: Text content to analyze.

        Returns:
            Dict with NLP analysis result including score and label.
        """
        result = self.analyzer.analyze(text)
        return {
            "score": result.score,
            "label": result.label.value,
            "confidence": result.confidence,
            "keywords": result.keywords_found,
            "events": result.events_detected,
            "summary": result.summary,
        }

    def analyze_text(self, text: str) -> NLPAnalysisResult:
        """Perform full NLP analysis on a text.

        Args:
            text: Text content to analyze.

        Returns:
            NLPAnalysisResult with detailed analysis.
        """
        return self.analyzer.analyze(text)

    def analyze_batch(self, texts: list[str]) -> list[NLPAnalysisResult]:
        """Analyze multiple texts in batch.

        Args:
            texts: List of text content.

        Returns:
            List of NLPAnalysisResult.
        """
        return self.analyzer.analyze_batch(texts)

    # --- Record Processing ---

    def process_record(self, record: SentimentRecord) -> NLPAnalysisResult:
        """Process a single sentiment record through NLP analysis.

        Args:
            record: SentimentRecord to process.

        Returns:
            NLPAnalysisResult with updated record.
        """
        return self.analyzer.analyze_record(record)

    def process_records(self, records: list[SentimentRecord]) -> list[NLPAnalysisResult]:
        """Process multiple sentiment records.

        Args:
            records: List of SentimentRecords.

        Returns:
            List of NLPAnalysisResult.
        """
        return [self.analyzer.analyze_record(r) for r in records]

    # --- Pipeline ---

    def run_pipeline(
        self,
        texts: list[str] | None = None,
        records: list[SentimentRecord] | None = None,
        fear_greed_data: dict[str, float] | None = None,
        price_data: list[float] | None = None,
        symbol: str = "",
    ) -> SentimentPipelineResult:
        """Run the full sentiment intelligence pipeline.

        Args:
            texts: Raw text content to analyze.
            records: Pre-existing sentiment records.
            fear_greed_data: Fear & Greed component data.
            price_data: Price series for divergence detection.
            symbol: Target trading symbol.

        Returns:
            SentimentPipelineResult with all analysis outputs.
        """
        start = datetime.now()

        # Step 1: NLP Analysis
        nlp_results: list[NLPAnalysisResult] = []
        all_records = list(records) if records else []

        if texts:
            nlp_results = self.analyzer.analyze_batch(texts)
            for result in nlp_results:
                all_records.append(
                    SentimentRecord(
                        source=SentimentSource.NEWS,
                        content=result.text,
                        score=result.score,
                        label=result.label,
                        confidence=result.confidence,
                        symbol=symbol,
                    )
                )

        # Step 2: Emotion Detection
        emotion: EmotionResult | None = None
        if all_records:
            emotion = self.emotion_detector.analyze_records(all_records)
        else:
            emotion = self.emotion_detector.analyze(50.0)

        # Step 3: Fear & Greed
        fear_greed: FearGreedResult | None = None
        if fear_greed_data:
            fear_greed = self.fear_greed_model.analyze(fear_greed_data)
        elif all_records:
            # Derive fear/greed from records
            avg_score = sum(r.score for r in all_records) / len(all_records)
            normalized = (avg_score + 1.0) / 2.0 * 100.0
            fg_data = {"social_sentiment": normalized, "price_momentum": 50.0}
            fear_greed = self.fear_greed_model.analyze(fg_data)

        # Step 4: Momentum
        momentum: SentimentMomentumResult | None = None
        if emotion:
            momentum = self.momentum_engine.analyze(emotion.score)

        # Step 5: Divergence
        divergence: DivergenceResult | None = None
        if price_data and all_records:
            sentiment_series = self._build_sentiment_series(all_records, len(price_data))
            divergence = self.divergence_detector.analyze(
                price_data, sentiment_series, symbol
            )

        # Step 6: Alpha Generation
        alpha: SentimentAlphaResult | None = None
        if all_records:
            fg_score = fear_greed.score if fear_greed else None
            alpha = self.alpha_generator.generate_from_records(
                symbol, all_records, fg_score
            )

        # Step 7: Memory
        if emotion:
            self.memory_store.save_sentiment(
                sentiment_score=emotion.score,
                label=self._score_to_label(emotion.score),
                emotion=emotion.state,
                symbol=symbol,
            )

        duration = (datetime.now() - start).total_seconds() * 1000

        # Build summary
        summary_parts = []
        if emotion:
            summary_parts.append(f"Emotion: {emotion.state.value}")
        if fear_greed:
            summary_parts.append(f"Fear/Greed: {fear_greed.score:.0f} ({fear_greed.zone.value})")
        if momentum and momentum.is_rapid_change:
            summary_parts.append(f"Momentum ALERT: {momentum.change:+.1f}")
        if divergence and divergence.has_divergence:
            summary_parts.append(f"Divergence: {divergence.analysis}")

        return SentimentPipelineResult(
            nlp_results=nlp_results,
            emotion=emotion,
            fear_greed=fear_greed,
            momentum=momentum,
            divergence=divergence,
            alpha=alpha,
            summary=" | ".join(summary_parts) if summary_parts else "Analysis complete.",
            duration_ms=duration,
        )

    # --- Convenience Methods ---

    def get_sentiment_for_symbol(self, symbol: str) -> dict[str, Any]:
        """Get current sentiment summary for a trading symbol.

        Args:
            symbol: Trading symbol.

        Returns:
            Dict with sentiment summary.
        """
        records = self.collector.get_by_symbol(symbol)
        if not records:
            return {"symbol": symbol, "sentiment": "unknown", "records": 0}

        avg_score = sum(r.score for r in records) / len(records)
        normalized_score = (avg_score + 1.0) / 2.0 * 100.0
        emotion = self.emotion_detector.analyze_score(avg_score)

        return {
            "symbol": symbol,
            "sentiment": emotion.value,
            "score": avg_score,
            "normalized_score": normalized_score,
            "records": len(records),
            "positive_ratio": sum(1 for r in records if r.is_positive) / len(records),
            "negative_ratio": sum(1 for r in records if r.is_negative) / len(records),
        }

    def get_market_mood(self) -> dict[str, Any]:
        """Get overall market mood assessment.

        Returns:
            Dict with market mood metrics.
        """
        fg = self.fear_greed_model.analyze()
        emotion = self.emotion_detector.analyze(50.0)
        contrarian = self.fear_greed_model.get_contrarian_signal()

        return {
            "fear_greed_score": fg.score,
            "fear_greed_zone": fg.zone.value,
            "emotion": emotion.state.value,
            "contrarian_signal": contrarian,
            "risk_adjustment": self.fear_greed_model.get_risk_adjustment(),
            "trend": self.fear_greed_model.get_trend(),
            "description": fg.description,
        }

    def get_memory_report(self) -> dict[str, Any]:
        """Get a report from sentiment memory.

        Returns:
            Dict with memory analysis.
        """
        return {
            "total_entries": self.memory_store.size,
            "accuracy_report": self.memory_store.get_accuracy_report(),
            "emotion_distribution": self.memory_store.get_emotion_distribution(),
            "most_reliable_emotion": (
                self.memory_store.get_most_reliable_emotion().value
                if self.memory_store.get_most_reliable_emotion()
                else None
            ),
        }

    # --- Internal ---

    def _build_sentiment_series(
        self, records: list[SentimentRecord], target_length: int
    ) -> list[float]:
        """Build a sentiment time series from records matching price data length.

        Args:
            records: Sentiment records.
            target_length: Desired series length.

        Returns:
            List of sentiment scores.
        """
        if not records:
            return [50.0] * target_length

        scores = [(r.score + 1.0) / 2.0 * 100.0 for r in records]
        if len(scores) >= target_length:
            return scores[-target_length:]
        # Pad at the beginning
        padding = [50.0] * (target_length - len(scores))
        return padding + scores

    def _score_to_label(self, score: float) -> SentimentLabel:
        """Convert normalized score to label."""
        if score >= 85:
            return SentimentLabel.VERY_BULLISH
        elif score >= 65:
            return SentimentLabel.BULLISH
        elif score >= 55:
            return SentimentLabel.SLIGHTLY_BULLISH
        elif score > 45:
            return SentimentLabel.NEUTRAL
        elif score > 35:
            return SentimentLabel.SLIGHTLY_BEARISH
        elif score > 15:
            return SentimentLabel.BEARISH
        else:
            return SentimentLabel.VERY_BEARISH

    def clear(self) -> None:
        """Reset all sub-engine state."""
        self.collector.clear()
        self.analyzer.clear()
        self.emotion_detector.clear()
        self.fear_greed_model.clear()
        self.momentum_engine.clear()
        self.divergence_detector.clear()
        self.alpha_generator.clear()
        self.memory_store.clear()
