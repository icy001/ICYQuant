"""AI Alternative Data Intelligence Engine — package exports."""

from .record import (
    AlphaCandidate,
    AlternativeFeature,
    AlternativeRecord,
    DataSource,
    FusionResult,
    MemoryEntry,
    NewsArticle,
    SatelliteObservation,
    SentimentPolarity,
    SignalStrength,
    SocialPost,
    WebMetric,
)
from .collector import AlternativeDataCollector
from .news import NewsAnalysis, NewsIntelligence
from .sentiment import AssetSentiment, SentimentResult, SocialSentimentEngine
from .web import AssetWebProfile, WebIntelligenceEngine, WebIntelligenceResult
from .satellite import SatelliteIntelligenceEngine, SatelliteResult
from .alpha import AlphaDiscoveryResult, AlternativeAlphaDiscovery
from .fusion import AlternativeDataFusion, FusionReport
from .memory import AlternativeMemory
from .service import AlternativeIntelligenceReport, AlternativeIntelligenceService

__all__ = [
    # Data models
    "AlternativeRecord",
    "AlternativeFeature",
    "AlphaCandidate",
    "FusionResult",
    "MemoryEntry",
    "NewsArticle",
    "SocialPost",
    "WebMetric",
    "SatelliteObservation",
    # Enums
    "DataSource",
    "SentimentPolarity",
    "SignalStrength",
    # Engines
    "AlternativeDataCollector",
    "NewsIntelligence",
    "NewsAnalysis",
    "SocialSentimentEngine",
    "SentimentResult",
    "AssetSentiment",
    "WebIntelligenceEngine",
    "WebIntelligenceResult",
    "AssetWebProfile",
    "SatelliteIntelligenceEngine",
    "SatelliteResult",
    "AlternativeAlphaDiscovery",
    "AlphaDiscoveryResult",
    "AlternativeDataFusion",
    "FusionReport",
    "AlternativeMemory",
    # Service
    "AlternativeIntelligenceService",
    "AlternativeIntelligenceReport",
]
