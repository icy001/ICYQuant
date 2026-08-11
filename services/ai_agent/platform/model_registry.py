"""Model Registry — catalog of all available AI models with capabilities and costs.

The ModelRegistry maintains a comprehensive catalog of all LLM models across
all providers, with metadata about capabilities, context windows, pricing,
and performance characteristics.

Model metadata:
    - Provider and model identifier
    - Context window size
    - Capabilities (text, vision, function calling, streaming, etc.)
    - Pricing (input/output per 1K tokens)
    - Performance tier
    - Recommended use cases
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ModelCapability(str, Enum):
    """Model capabilities for routing decisions."""
    TEXT = "text"
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"
    STREAMING = "streaming"
    JSON_MODE = "json_mode"
    PARALLEL_TOOLS = "parallel_tools"
    CODE_GENERATION = "code_generation"
    REASONING = "reasoning"
    LONG_CONTEXT = "long_context"


class PerformanceTier(str, Enum):
    """Performance classification for models."""
    ULTRA = "ultra"
    HIGH = "high"
    STANDARD = "standard"
    LIGHT = "light"
    MINI = "mini"


@dataclass
class ModelPricing:
    """Cost per 1000 tokens."""
    input_per_1k: float = 0.0
    output_per_1k: float = 0.0
    currency: str = "USD"


@dataclass
class ModelRecord:
    """Complete metadata for a registered model."""
    model_id: str
    provider_name: str
    display_name: str = ""
    context_window: int = 8192
    max_output_tokens: int = 4096
    capabilities: List[ModelCapability] = field(default_factory=list)
    performance_tier: PerformanceTier = PerformanceTier.STANDARD
    pricing: ModelPricing = field(default_factory=ModelPricing)
    tags: List[str] = field(default_factory=list)
    recommended_for: List[str] = field(default_factory=list)
    deprecated: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class ModelRegistry:
    """Catalog of all available AI models with capabilities and costs.

    Serves as the single source of truth for model metadata used by the
    ModelSelector and ModelRouter.

    Usage:
        mr = ModelRegistry()
        await mr.initialize()
        mr.register(ModelRecord(model_id="gpt-4o", provider_name="openai_main", ...))
        models = mr.find_by_capability(ModelCapability.FUNCTION_CALLING)
    """

    def __init__(self) -> None:
        self._models: Dict[str, ModelRecord] = {}
        self._initialized: bool = False
        logger.info("ModelRegistry created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("ModelRegistry initialized")

    async def shutdown(self) -> None:
        self._models.clear()
        self._initialized = False
        logger.info("ModelRegistry shutdown complete")

    def register(self, model: ModelRecord) -> None:
        """Register a model in the catalog."""
        self._models[model.model_id] = model
        logger.info("ModelRegistry: registered %s (%s)", model.model_id, model.provider_name)

    def unregister(self, model_id: str) -> bool:
        """Remove a model from the catalog."""
        if model_id in self._models:
            del self._models[model_id]
            return True
        return False

    def get(self, model_id: str) -> Optional[ModelRecord]:
        """Get model metadata by ID."""
        return self._models.get(model_id)

    def list_all(self) -> List[ModelRecord]:
        """List all registered models."""
        return list(self._models.values())

    def find_by_provider(self, provider_name: str) -> List[ModelRecord]:
        """Find models for a specific provider."""
        return [m for m in self._models.values() if m.provider_name == provider_name]

    def find_by_capability(self, capability: ModelCapability) -> List[ModelRecord]:
        """Find models with a specific capability."""
        return [m for m in self._models.values() if capability in m.capabilities and not m.deprecated]

    def find_by_capabilities(self, capabilities: List[ModelCapability]) -> List[ModelRecord]:
        """Find models that have ALL specified capabilities."""
        cap_set = set(capabilities)
        return [m for m in self._models.values() if cap_set.issubset(set(m.capabilities)) and not m.deprecated]

    def find_by_tier(self, tier: PerformanceTier) -> List[ModelRecord]:
        """Find models by performance tier."""
        return [m for m in self._models.values() if m.performance_tier == tier and not m.deprecated]

    def find_by_tag(self, tag: str) -> List[ModelRecord]:
        """Find models by tag."""
        return [m for m in self._models.values() if tag in m.tags and not m.deprecated]

    def get_cheapest_for_capability(self, capability: ModelCapability) -> Optional[ModelRecord]:
        """Get the cheapest model with a given capability."""
        candidates = self.find_by_capability(capability)
        if not candidates:
            return None
        return min(candidates, key=lambda m: m.pricing.input_per_1k + m.pricing.output_per_1k)

    def get_fastest_for_capability(self, capability: ModelCapability) -> Optional[ModelRecord]:
        """Get the fastest model (lowest tier) with a given capability."""
        candidates = self.find_by_capability(capability)
        if not candidates:
            return None
        tier_order = {PerformanceTier.MINI: 0, PerformanceTier.LIGHT: 1, PerformanceTier.STANDARD: 2, PerformanceTier.HIGH: 3, PerformanceTier.ULTRA: 4}
        return min(candidates, key=lambda m: tier_order.get(m.performance_tier, 99))

    def get_most_capable(self) -> Optional[ModelRecord]:
        """Get the most capable model available."""
        tier_order = {PerformanceTier.ULTRA: 4, PerformanceTier.HIGH: 3, PerformanceTier.STANDARD: 2, PerformanceTier.LIGHT: 1, PerformanceTier.MINI: 0}
        active = [m for m in self._models.values() if not m.deprecated]
        if not active:
            return None
        return max(active, key=lambda m: (tier_order.get(m.performance_tier, 0), m.context_window))

    def get_summary(self) -> Dict[str, Any]:
        providers = {}
        for m in self._models.values():
            providers.setdefault(m.provider_name, 0)
            providers[m.provider_name] += 1
        return {
            "initialized": self._initialized,
            "total_models": len(self._models),
            "active_models": len([m for m in self._models.values() if not m.deprecated]),
            "by_provider": providers,
        }
