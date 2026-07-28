"""AI Sentiment Intelligence Engine.

Captures market participant sentiment changes and converts emotional information
from news, social media, capital flows, and trading data into quantifiable factors
for market risk prediction, sentiment turning point detection, and alpha signal
enhancement.
"""

from __future__ import annotations

from .record import (
    SentimentRecord,
    SentimentSource,
    SentimentLabel,
    EmotionState,
    FearGreedZone,
    SentimentEvent,
    SentimentDivergence,
    SentimentAlphaSignal,
)
from .collector import SentimentCollector, CollectionResult
from .nlp import NLPAnalyzer, NLPAnalysisResult
from .emotion import EmotionDetector, EmotionResult
from .fear_greed import FearGreedModel, FearGreedResult
from .momentum import SentimentMomentum, SentimentMomentumResult
from .divergence import DivergenceDetector, DivergenceResult
from .alpha import SentimentAlphaGenerator, SentimentAlphaResult
from .memory import SentimentMemory, SentimentMemoryEntry
from .service import SentimentIntelligenceService, SentimentPipelineResult

__all__ = [
    # Data Models
    "SentimentRecord",
    "SentimentSource",
    "SentimentLabel",
    "EmotionState",
    "FearGreedZone",
    "SentimentEvent",
    "SentimentDivergence",
    "SentimentAlphaSignal",
    # Collector
    "SentimentCollector",
    "CollectionResult",
    # NLP
    "NLPAnalyzer",
    "NLPAnalysisResult",
    # Emotion
    "EmotionDetector",
    "EmotionResult",
    # Fear & Greed
    "FearGreedModel",
    "FearGreedResult",
    # Momentum
    "SentimentMomentum",
    "SentimentMomentumResult",
    # Divergence
    "DivergenceDetector",
    "DivergenceResult",
    # Alpha
    "SentimentAlphaGenerator",
    "SentimentAlphaResult",
    # Memory
    "SentimentMemory",
    "SentimentMemoryEntry",
    # Service
    "SentimentIntelligenceService",
    "SentimentPipelineResult",
]
