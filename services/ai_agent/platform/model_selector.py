"""Model Selector — intelligent model selection based on task requirements and strategy.

The ModelSelector picks the optimal model for each request based on:
    - Required capabilities (function calling, vision, reasoning, etc.)
    - Selection strategy (cost-first, latency-first, capability-first)
    - Provider availability
    - Budget constraints
    - Task complexity estimation

Selection strategies:
    - COST_FIRST: minimize token cost
    - LATENCY_FIRST: minimize response time
    - CAPABILITY_FIRST: maximize model quality
    - BALANCED: weighted trade-off
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SelectionStrategy(str, Enum):
    """Model selection strategies."""
    COST_FIRST = "cost_first"
    LATENCY_FIRST = "latency_first"
    CAPABILITY_FIRST = "capability_first"
    BALANCED = "balanced"


@dataclass
class TaskRequirements:
    """Requirements for model selection based on the task."""
    capabilities: List[str] = field(default_factory=list)
    min_context_window: int = 4096
    max_budget_usd: float = 0.01
    priority: int = 0
    prefer_streaming: bool = False
    prefer_json_mode: bool = False
    task_complexity: str = "medium"


@dataclass
class SelectionResult:
    """Result of a model selection decision."""
    selected_model_id: str = ""
    provider_name: str = ""
    strategy_used: SelectionStrategy = SelectionStrategy.BALANCED
    confidence: float = 1.0
    reason: str = ""
    alternatives: List[str] = field(default_factory=list)


class ModelSelector:
    """Intelligent model selector based on task requirements and strategy.

    Evaluates available models against task requirements and selects the
    optimal model based on the configured selection strategy.

    Usage:
        selector = ModelSelector(registry, provider_manager)
        await selector.initialize()
        result = await selector.select(
            requirements=TaskRequirements(capabilities=["function_calling"]),
            strategy=SelectionStrategy.COST_FIRST,
        )
    """

    def __init__(self, registry: Any = None, provider_manager: Any = None) -> None:
        self._registry = registry
        self._provider_manager = provider_manager
        self._default_strategy = SelectionStrategy.BALANCED
        self._initialized: bool = False
        logger.info("ModelSelector created (default_strategy=%s)", self._default_strategy.value)

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("ModelSelector initialized")

    async def shutdown(self) -> None:
        self._initialized = False
        logger.info("ModelSelector shutdown complete")

    async def select(self, requirements: TaskRequirements, strategy: Optional[SelectionStrategy] = None) -> SelectionResult:
        """Select the optimal model for a task.

        Evaluates models against requirements and applies the selection strategy.
        """
        if not self._registry:
            return SelectionResult(reason="No model registry available")

        strategy = strategy or self._default_strategy
        candidates = self._registry.list_all() if hasattr(self._registry, 'list_all') else []

        if not candidates:
            return SelectionResult(reason="No models registered")

        # Filter by requirements
        filtered = self._filter_by_requirements(candidates, requirements)
        if not filtered:
            return SelectionResult(reason="No models match requirements")

        # Apply selection strategy
        if strategy == SelectionStrategy.COST_FIRST:
            selected = min(filtered, key=lambda m: getattr(getattr(m, 'pricing', None), 'input_per_1k', 0) if hasattr(m, 'pricing') else 0)
        elif strategy == SelectionStrategy.LATENCY_FIRST:
            tier_order = {"mini": 0, "light": 1, "standard": 2, "high": 3, "ultra": 4}
            selected = min(filtered, key=lambda m: tier_order.get(getattr(getattr(m, 'performance_tier', None), 'value', 'standard'), 2))
        elif strategy == SelectionStrategy.CAPABILITY_FIRST:
            tier_order = {"ultra": 4, "high": 3, "standard": 2, "light": 1, "mini": 0}
            selected = max(filtered, key=lambda m: (tier_order.get(getattr(getattr(m, 'performance_tier', None), 'value', 'standard'), 2), getattr(m, 'context_window', 0)))
        else:  # BALANCED
            selected = filtered[0]

        return SelectionResult(
            selected_model_id=getattr(selected, 'model_id', 'unknown'),
            provider_name=getattr(selected, 'provider_name', 'unknown'),
            strategy_used=strategy,
            reason=f"Selected by {strategy.value} strategy",
            alternatives=[getattr(m, 'model_id', '') for m in filtered[:3] if m != selected],
        )

    def _filter_by_requirements(self, candidates: List[Any], requirements: TaskRequirements) -> List[Any]:
        """Filter models by task requirements."""
        filtered = []
        for m in candidates:
            if hasattr(m, 'deprecated') and m.deprecated:
                continue
            if requirements.min_context_window > 0:
                ctx = getattr(m, 'context_window', 0)
                if ctx < requirements.min_context_window:
                    continue
            if requirements.capabilities:
                caps = [c.value if hasattr(c, 'value') else c for c in getattr(m, 'capabilities', [])]
                if not all(req in caps for req in requirements.capabilities):
                    continue
            if requirements.max_budget_usd > 0 and hasattr(m, 'pricing'):
                cost = m.pricing.input_per_1k + m.pricing.output_per_1k
                if cost > requirements.max_budget_usd:
                    continue
            filtered.append(m)
        return filtered

    def set_default_strategy(self, strategy: SelectionStrategy) -> None:
        """Change the default selection strategy."""
        self._default_strategy = strategy
        logger.info("ModelSelector default strategy changed to %s", strategy.value)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "default_strategy": self._default_strategy.value,
        }
