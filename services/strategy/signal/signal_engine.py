"""
Signal Engine — Unified entry point for signal generation, validation and publishing.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

Pipeline:
    Strategy Context → Generate → Validate → Normalize → Rank → Publish
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from services.strategy.signal.signal_runtime import SignalRuntime
from services.strategy.signal.signal_manager import SignalManager
from services.strategy.signal.signal_generator import SignalGenerator
from services.strategy.signal.signal_validator import SignalValidator
from services.strategy.signal.signal_normalizer import SignalNormalizer
from services.strategy.signal.signal_ranker import SignalRanker
from services.strategy.signal.signal_dispatcher import SignalDispatcher
from services.strategy.signal.signal_cache import SignalCache
from services.strategy.signal.signal_expiration import SignalExpiration
from services.strategy.signal.confidence_engine import ConfidenceEngine
from services.strategy.signal.explainability_engine import ExplainabilityEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SignalDirection(str, Enum):
    """Unified signal direction."""
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


class SignalStatus(str, Enum):
    """Signal processing status."""
    GENERATED = "GENERATED"
    VALIDATED = "VALIDATED"
    NORMALIZED = "NORMALIZED"
    RANKED = "RANKED"
    PUBLISHED = "PUBLISHED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class SignalStrength(str, Enum):
    """Signal conviction level."""
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"
    VERY_STRONG = "VERY_STRONG"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class Signal:
    """Standardized trading signal.

    All strategies MUST output this structure for downstream consumption.
    """
    signal_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    strategy_id: str = ""
    instrument: str = ""
    direction: SignalDirection = SignalDirection.FLAT
    strength: SignalStrength = SignalStrength.MODERATE
    confidence: float = 0.0
    reason: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expiration: Optional[datetime] = None
    status: SignalStatus = SignalStatus.GENERATED

    # Rich metadata
    alpha_scores: Dict[str, float] = field(default_factory=dict)
    factor_contributions: Dict[str, float] = field(default_factory=dict)
    market_regime: Optional[str] = None
    explanation: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "strategy_id": self.strategy_id,
            "instrument": self.instrument,
            "direction": self.direction.value,
            "strength": self.strength.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
            "expiration": self.expiration.isoformat() if self.expiration else None,
            "status": self.status.value,
            "alpha_scores": self.alpha_scores,
            "factor_contributions": self.factor_contributions,
            "market_regime": self.market_regime,
            "explanation": self.explanation,
            "tags": self.tags,
            "metadata": self.metadata,
        }


@dataclass
class SignalBatch:
    """Batch of signals for bulk processing."""
    batch_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    signals: List[Signal] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __len__(self) -> int:
        return len(self.signals)


@dataclass
class GenerateRequest:
    """Request to generate signals from strategy context."""
    strategy_id: str
    instruments: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    max_signals: int = 20
    min_confidence: float = 0.0


@dataclass
class GenerateResult:
    """Result of signal generation."""
    request: GenerateRequest
    signals: List[Signal] = field(default_factory=list)
    rejected: List[Signal] = field(default_factory=list)
    elapsed_ms: float = 0.0


# ---------------------------------------------------------------------------
# Signal Engine
# ---------------------------------------------------------------------------

class SignalEngine:
    """Unified Signal Engine — the central entry point for signal processing.

    Responsibilities:
        - Generate signals from strategy context via SignalGenerator
        - Validate signals through multi-stage SignalValidator
        - Normalize semantics via SignalNormalizer
        - Rank signals by priority via SignalRanker
        - Score confidence via ConfidenceEngine
        - Generate explanations via ExplainabilityEngine
        - Dispatch to downstream consumers via SignalDispatcher
        - Cache active signals in SignalCache
        - Expire stale signals via SignalExpiration

    Usage::

        engine = SignalEngine()
        await engine.initialize()

        request = GenerateRequest(strategy_id="momentum_v2", instruments=["AAPL", "TSLA"])
        result = await engine.generate(request)
        await engine.publish(result.signals)
    """

    def __init__(self):
        self._initialized = False

        # Subsystems
        self.runtime: Optional[SignalRuntime] = None
        self.manager: Optional[SignalManager] = None
        self.generator: Optional[SignalGenerator] = None
        self.validator: Optional[SignalValidator] = None
        self.normalizer: Optional[SignalNormalizer] = None
        self.ranker: Optional[SignalRanker] = None
        self.dispatcher: Optional[SignalDispatcher] = None
        self.cache: Optional[SignalCache] = None
        self.expiration: Optional[SignalExpiration] = None
        self.confidence_engine: Optional[ConfidenceEngine] = None
        self.explainability_engine: Optional[ExplainabilityEngine] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize all signal subsystems."""
        if self._initialized:
            return

        logger.info("Initializing Signal Engine")

        self.manager = SignalManager()
        await self.manager.initialize()

        self.runtime = SignalRuntime()
        await self.runtime.initialize()

        self.generator = SignalGenerator()
        self.validator = SignalValidator()
        self.normalizer = SignalNormalizer()
        self.ranker = SignalRanker()
        self.cache = SignalCache()
        self.expiration = SignalExpiration(cache=self.cache)
        self.confidence_engine = ConfidenceEngine()
        self.explainability_engine = ExplainabilityEngine()

        self.dispatcher = SignalDispatcher(
            manager=self.manager,
            cache=self.cache,
        )
        await self.dispatcher.initialize()

        self._initialized = True
        logger.info("Signal Engine initialized")

    async def shutdown(self) -> None:
        """Gracefully shut down all subsystems."""
        logger.info("Shutting down Signal Engine")
        if self.dispatcher:
            await self.dispatcher.shutdown()
        if self.runtime:
            await self.runtime.shutdown()
        if self.manager:
            await self.manager.shutdown()
        self._initialized = False
        logger.info("Signal Engine shut down")

    # ------------------------------------------------------------------
    # Core Operations
    # ------------------------------------------------------------------

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        """Full pipeline: generate → validate → normalize → rank → confidence → explain.

        This is the primary entry point for strategy-to-signal conversion.
        """
        self._ensure_initialized()
        start = datetime.now(timezone.utc)
        rejected: List[Signal] = []

        # 1. Generate raw signals from strategy context
        raw_signals = await self.generator.generate(
            strategy_id=request.strategy_id,
            instruments=request.instruments,
            context=request.context,
            max_signals=request.max_signals,
        )

        # 2. Validate each signal
        valid_signals: List[Signal] = []
        for sig in raw_signals:
            validation = await self.validator.validate(sig)
            if validation.passed:
                sig.status = SignalStatus.VALIDATED
                valid_signals.append(sig)
            else:
                sig.status = SignalStatus.REJECTED
                rejected.append(sig)

        # 3. Normalize semantics
        for sig in valid_signals:
            sig.direction = await self.normalizer.normalize_direction(sig)
            sig.strength = await self.normalizer.normalize_strength(sig)

        # 4. Score confidence
        for sig in valid_signals:
            sig.confidence = await self.confidence_engine.score(sig)

        # 5. Generate explanations
        for sig in valid_signals:
            sig.explanation = await self.explainability_engine.explain(sig)

        # 6. Rank by priority
        ranked = await self.ranker.rank(valid_signals)
        for sig in ranked:
            sig.status = SignalStatus.RANKED

        # 7. Filter by minimum confidence
        final = [s for s in ranked if s.confidence >= request.min_confidence]
        rejected.extend([s for s in ranked if s.confidence < request.min_confidence])

        elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        result = GenerateResult(
            request=request,
            signals=final,
            rejected=rejected,
            elapsed_ms=elapsed,
        )

        logger.info(
            "Signal generation complete: generated=%d, valid=%d, rejected=%d, elapsed=%.2fms",
            len(raw_signals), len(final), len(rejected), elapsed,
        )
        return result

    async def validate(self, signal: Signal) -> bool:
        """Validate a single signal."""
        self._ensure_initialized()
        result = await self.validator.validate(signal)
        return result.passed

    async def publish(self, signals: List[Signal]) -> None:
        """Publish signals to downstream consumers.

        Steps:
            1. Cache active signals
            2. Dispatch to all registered consumers
            3. Mark as PUBLISHED
        """
        self._ensure_initialized()
        batch = SignalBatch(signals=signals)
        await self.dispatcher.dispatch(batch)
        for sig in signals:
            sig.status = SignalStatus.PUBLISHED
        logger.info("Published %d signals", len(signals))

    async def cancel(self, signal_id: str) -> bool:
        """Cancel an active signal."""
        self._ensure_initialized()
        cancelled = await self.cache.cancel(signal_id)
        if cancelled:
            logger.info("Signal %s cancelled", signal_id)
        return cancelled

    async def expire_check(self) -> List[str]:
        """Check and expire stale signals. Returns list of expired signal IDs."""
        self._ensure_initialized()
        expired = await self.expiration.expire()
        if expired:
            logger.info("Expired %d signals", len(expired))
        return expired

    async def get_active_signals(self, strategy_id: Optional[str] = None) -> List[Signal]:
        """Retrieve all currently active signals, optionally filtered by strategy."""
        self._ensure_initialized()
        return await self.cache.get_active(strategy_id=strategy_id)

    async def get_signal(self, signal_id: str) -> Optional[Signal]:
        """Retrieve a specific signal by ID."""
        self._ensure_initialized()
        return await self.cache.get(signal_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError("SignalEngine not initialized. Call initialize() first.")

    @property
    def is_initialized(self) -> bool:
        return self._initialized
