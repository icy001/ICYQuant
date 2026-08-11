"""
Alpha Engine — Unified alpha generation, combination and evaluation.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

Pipeline:
    Research Factor → Alpha → Quality Score → Alpha Pool

Supports future integration of:
    - Rule Alpha
    - Statistical Alpha
    - ML Alpha
    - Deep Learning Alpha
    - LLM Generated Alpha
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from services.strategy.signal.alpha_runtime import AlphaRuntime
from services.strategy.signal.alpha_registry import AlphaRegistry
from services.strategy.signal.alpha_repository import AlphaRepository
from services.strategy.signal.alpha_pipeline import AlphaPipeline
from services.strategy.signal.alpha_combiner import AlphaCombiner
from services.strategy.signal.alpha_weighting import AlphaWeighting
from services.strategy.signal.alpha_decay import AlphaDecay
from services.strategy.signal.alpha_quality import AlphaQuality
from services.strategy.signal.factor_mapper import FactorMapper

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AlphaType(str, Enum):
    """Types of alpha models."""
    RULE = "rule"
    STATISTICAL = "statistical"
    ML = "ml"
    DEEP_LEARNING = "deep_learning"
    LLM = "llm"
    CUSTOM = "custom"


class AlphaStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DECAYING = "DECAYING"
    INACTIVE = "INACTIVE"
    DEPRECATED = "DEPRECATED"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class AlphaScore:
    """Output of a single alpha model."""
    alpha_id: str = ""
    alpha_name: str = ""
    alpha_type: AlphaType = AlphaType.CUSTOM
    instrument: str = ""
    raw_score: float = 0.0
    normalized_score: float = 0.0
    quality_score: float = 0.0
    decay_factor: float = 1.0
    weight: float = 1.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CombinedAlpha:
    """Result of combining multiple alpha scores."""
    instrument: str = ""
    combined_score: float = 0.0
    alpha_scores: Dict[str, float] = field(default_factory=dict)
    alpha_weights: Dict[str, float] = field(default_factory=dict)
    contribution_breakdown: Dict[str, float] = field(default_factory=dict)
    quality: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AlphaGenerateRequest:
    """Request to generate alpha scores."""
    strategy_id: str = ""
    instruments: List[str] = field(default_factory=list)
    factors: Dict[str, Dict[str, float]] = field(default_factory=dict)  # factor_name → {instrument → value}
    alpha_ids: Optional[List[str]] = None  # Specific alphas to run, None = all active
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AlphaGenerateResult:
    """Result of alpha generation."""
    request: AlphaGenerateRequest
    alpha_scores: List[AlphaScore] = field(default_factory=list)
    combined: Dict[str, CombinedAlpha] = field(default_factory=dict)
    elapsed_ms: float = 0.0
    errors: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Alpha Engine
# ---------------------------------------------------------------------------

class AlphaEngine:
    """Unified Alpha Engine — generates, combines, and evaluates alpha scores.

    Pipeline:
        1. Map raw factors via FactorMapper
        2. Run alpha pipeline per instrument
        3. Apply quality scoring
        4. Apply decay factors
        5. Combine multiple alphas via AlphaCombiner
        6. Return CombinedAlpha per instrument
    """

    def __init__(self):
        self._initialized = False

        self.runtime: Optional[AlphaRuntime] = None
        self.registry: Optional[AlphaRegistry] = None
        self.repository: Optional[AlphaRepository] = None
        self.pipeline: Optional[AlphaPipeline] = None
        self.combiner: Optional[AlphaCombiner] = None
        self.weighting: Optional[AlphaWeighting] = None
        self.decay: Optional[AlphaDecay] = None
        self.quality: Optional[AlphaQuality] = None
        self.factor_mapper: Optional[FactorMapper] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._initialized:
            return

        logger.info("Initializing Alpha Engine")

        self.registry = AlphaRegistry()
        await self.registry.initialize()

        self.repository = AlphaRepository()
        await self.repository.initialize()

        self.runtime = AlphaRuntime()
        await self.runtime.initialize()

        self.factor_mapper = FactorMapper()
        self.pipeline = AlphaPipeline()
        self.combiner = AlphaCombiner()
        self.weighting = AlphaWeighting()
        self.decay = AlphaDecay(registry=self.registry)
        self.quality = AlphaQuality()

        self._initialized = True
        logger.info("Alpha Engine initialized")

    async def shutdown(self) -> None:
        logger.info("Shutting down Alpha Engine")
        if self.runtime:
            await self.runtime.shutdown()
        if self.repository:
            await self.repository.shutdown()
        if self.registry:
            await self.registry.shutdown()
        self._initialized = False
        logger.info("Alpha Engine shut down")

    # ------------------------------------------------------------------
    # Core Operations
    # ------------------------------------------------------------------

    async def generate(self, request: AlphaGenerateRequest) -> AlphaGenerateResult:
        """Full alpha pipeline: factor mapping → alpha generation → quality → combine."""
        self._ensure_initialized()
        start = datetime.now(timezone.utc)
        errors: List[str] = []

        # 1. Map raw factors to alpha-ready inputs
        mapped_factors = await self.factor_mapper.map_factors(request.factors, request.instruments)

        # 2. Get active alpha models
        alpha_ids = request.alpha_ids
        if not alpha_ids:
            active_alphas = self.registry.list_active()
            alpha_ids = [a.alpha_id for a in active_alphas]

        # 3. Run alpha pipeline per alpha per instrument
        all_scores: List[AlphaScore] = []
        for alpha_id in alpha_ids:
            alpha_info = self.registry.get_alpha(alpha_id)
            if not alpha_info:
                errors.append(f"Alpha {alpha_id} not found in registry")
                continue

            # Check decay
            decay_factor = await self.decay.get_decay_factor(alpha_id)
            if decay_factor <= 0.0:
                logger.debug("Alpha %s fully decayed, skipping", alpha_id)
                continue

            # Run pipeline
            try:
                scores = await self.pipeline.run(
                    alpha_info=alpha_info,
                    instruments=request.instruments,
                    factors=mapped_factors,
                    context=request.context,
                )

                # Apply quality
                for score in scores:
                    score.alpha_type = alpha_info.alpha_type
                    score.quality_score = await self.quality.evaluate(score)
                    score.decay_factor = decay_factor
                    score.normalized_score = score.raw_score * decay_factor * score.quality_score

                all_scores.extend(scores)
            except Exception as e:
                errors.append(f"Alpha {alpha_id} failed: {str(e)}")
                logger.exception("Alpha %s pipeline error", alpha_id)

        # 4. Apply weighting
        weighted_scores = await self.weighting.apply_weights(all_scores)

        # 5. Combine alphas per instrument
        combined = {}
        for inst in request.instruments:
            inst_scores = [s for s in weighted_scores if s.instrument == inst]
            if inst_scores:
                combined[inst] = await self.combiner.combine(inst, inst_scores)

        # 6. Persist
        await self.repository.save_batch(all_scores)

        elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        result = AlphaGenerateResult(
            request=request,
            alpha_scores=all_scores,
            combined=combined,
            elapsed_ms=elapsed,
            errors=errors,
        )

        logger.info(
            "Alpha generation complete: %d scores, %d combined, %d errors, %.2fms",
            len(all_scores), len(combined), len(errors), elapsed,
        )
        return result

    async def combine(self, instrument: str, scores: List[AlphaScore]) -> CombinedAlpha:
        """Combine multiple alpha scores for a single instrument."""
        self._ensure_initialized()
        weighted = await self.weighting.apply_weights(scores)
        return await self.combiner.combine(instrument, weighted)

    async def evaluate(self, scores: List[AlphaScore]) -> List[AlphaScore]:
        """Evaluate alpha quality for a batch of scores."""
        self._ensure_initialized()
        for score in scores:
            score.quality_score = await self.quality.evaluate(score)
        return scores

    # ------------------------------------------------------------------
    # Alpha Lifecycle
    # ------------------------------------------------------------------

    async def decay_check(self) -> List[str]:
        """Check and update decay for all active alphas. Returns decayed alpha IDs."""
        self._ensure_initialized()
        return await self.decay.update_decay()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError("AlphaEngine not initialized. Call initialize() first.")

    @property
    def is_initialized(self) -> bool:
        return self._initialized
