"""
Signal & Alpha Engine

Commit 13 Part 1.2 — Production Signal & Alpha Engine

Architecture:

    Market Data → Feature Pipeline → Alpha Engine → Signal Engine → Order Intent

Modules:

    Signal Engine
        signal_engine.py        — Unified signal entry point (generate / validate / publish)
        signal_runtime.py       — Signal execution sandbox & concurrency control
        signal_manager.py       — Central coordinator & event bus
        signal_registry.py      — Signal type & source registration
        signal_repository.py    — Signal persistence & query

    Signal Pipeline
        signal_generator.py     — Signal generation from strategy context
        signal_dispatcher.py    — Fan-out delivery to downstream consumers
        signal_normalizer.py    — Semantic unification (BUY→LONG, etc.)
        signal_validator.py     — Multi-stage signal validation
        signal_ranker.py        — Priority-based signal ordering

    Signal Lifecycle
        signal_cache.py         — In-memory signal store with TTL
        signal_expiration.py    — Time-based & event-based expiration
        signal_snapshot.py      — Runtime state capture for recovery
        signal_metrics.py       — Signal-specific Prometheus metrics

    Alpha Engine
        alpha_engine.py         — Unified alpha generation & evaluation
        alpha_runtime.py        — Alpha execution sandbox
        alpha_registry.py       — Alpha model registration & discovery
        alpha_repository.py     — Alpha persistence & versioning
        alpha_pipeline.py       — Raw factor → Alpha score pipeline

    Alpha Pipeline
        alpha_combiner.py       — Multi-alpha fusion strategies
        alpha_weighting.py      — Dynamic weight assignment
        alpha_decay.py          — Half-life based alpha decay
        alpha_quality.py        — Alpha quality & stability scoring
        factor_mapper.py        — Research factor → Alpha factor mapping

    Intelligence
        market_regime_filter.py — Market regime detection & filtering
        confidence_engine.py    — Multi-dimensional confidence scoring
        explainability_engine.py— Factor/Alpha contribution analysis

    Observability
        diagnostics.py          — Diagnostic analysis & issue detection
        metrics.py              — Alpha/Signal Prometheus metrics
        telemetry.py            — Distributed tracing & audit
        health.py               — Component health checking
"""

from services.strategy.signal.signal_engine import SignalEngine
from services.strategy.signal.signal_runtime import SignalRuntime
from services.strategy.signal.signal_manager import SignalManager
from services.strategy.signal.signal_registry import SignalRegistry
from services.strategy.signal.signal_repository import SignalRepository
from services.strategy.signal.signal_generator import SignalGenerator
from services.strategy.signal.signal_dispatcher import SignalDispatcher
from services.strategy.signal.signal_normalizer import SignalNormalizer
from services.strategy.signal.signal_validator import SignalValidator
from services.strategy.signal.signal_ranker import SignalRanker
from services.strategy.signal.signal_cache import SignalCache
from services.strategy.signal.signal_expiration import SignalExpiration
from services.strategy.signal.signal_snapshot import SignalSnapshot
from services.strategy.signal.signal_metrics import SignalMetrics

from services.strategy.signal.alpha_engine import AlphaEngine
from services.strategy.signal.alpha_runtime import AlphaRuntime
from services.strategy.signal.alpha_registry import AlphaRegistry
from services.strategy.signal.alpha_repository import AlphaRepository
from services.strategy.signal.alpha_pipeline import AlphaPipeline
from services.strategy.signal.alpha_combiner import AlphaCombiner
from services.strategy.signal.alpha_weighting import AlphaWeighting
from services.strategy.signal.alpha_decay import AlphaDecay
from services.strategy.signal.alpha_quality import AlphaQuality
from services.strategy.signal.factor_mapper import FactorMapper

from services.strategy.signal.market_regime_filter import MarketRegimeFilter
from services.strategy.signal.confidence_engine import ConfidenceEngine
from services.strategy.signal.explainability_engine import ExplainabilityEngine

from services.strategy.signal.diagnostics import SignalDiagnostics
from services.strategy.signal.metrics import AlphaSignalMetrics
from services.strategy.signal.telemetry import AlphaSignalTelemetry
from services.strategy.signal.health import AlphaSignalHealthChecker

__all__ = [
    # Signal Engine
    "SignalEngine",
    "SignalRuntime",
    "SignalManager",
    "SignalRegistry",
    "SignalRepository",
    # Signal Pipeline
    "SignalGenerator",
    "SignalDispatcher",
    "SignalNormalizer",
    "SignalValidator",
    "SignalRanker",
    # Signal Lifecycle
    "SignalCache",
    "SignalExpiration",
    "SignalSnapshot",
    "SignalMetrics",
    # Alpha Engine
    "AlphaEngine",
    "AlphaRuntime",
    "AlphaRegistry",
    "AlphaRepository",
    "AlphaPipeline",
    # Alpha Pipeline
    "AlphaCombiner",
    "AlphaWeighting",
    "AlphaDecay",
    "AlphaQuality",
    "FactorMapper",
    # Intelligence
    "MarketRegimeFilter",
    "ConfidenceEngine",
    "ExplainabilityEngine",
    # Observability
    "SignalDiagnostics",
    "AlphaSignalMetrics",
    "AlphaSignalTelemetry",
    "AlphaSignalHealthChecker",
]
