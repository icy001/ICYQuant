"""Portfolio Registry — central registry for optimizers, risk models, and constraints.

Maintains dynamic registrations of optimizer types, risk model
implementations, constraint definitions, and allocation methods
discoverable at runtime.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class PortfolioCategory(str, Enum):
    """Predefined portfolio categories."""

    LONG_ONLY = "long_only"
    LONG_SHORT = "long_short"
    MARKET_NEUTRAL = "market_neutral"
    ENHANCED_INDEX = "enhanced_index"
    ABSOLUTE_RETURN = "absolute_return"
    RISK_PARITY = "risk_parity"
    CUSTOM = "custom"


class OptimizationObjective(str, Enum):
    """Common optimization objectives."""

    MAX_SHARPE = "max_sharpe"
    MIN_VARIANCE = "min_variance"
    MAX_RETURN = "max_return"
    RISK_PARITY = "risk_parity"
    MAX_DIVERSIFICATION = "max_diversification"
    MAX_DECORRELATION = "max_decorrelation"
    CUSTOM = "custom"


class PortfolioRegistry:
    """Central registry for portfolio research components.

    Registers:
    * Optimizer types → factory callables
    * Risk model types → factory callables
    * Constraint types → constraint definitions
    * Allocation methods → allocation callables
    * Benchmark configurations
    * Alpha pool definitions
    """

    def __init__(self) -> None:
        self._optimizer_types: Dict[str, Type] = {}
        self._optimizer_factories: Dict[str, Callable] = {}
        self._risk_models: Dict[str, Type] = {}
        self._risk_factories: Dict[str, Callable] = {}
        self._constraint_types: Dict[str, Type] = {}
        self._allocation_methods: Dict[str, Callable] = {}
        self._benchmarks: Dict[str, Dict[str, Any]] = {}
        self._alpha_pools: Dict[str, Dict[str, Any]] = {}

    # ── optimizer registry ─────────────────────────────────────────────────

    def register_optimizer(
        self, name: str, optimizer_type: Type, factory: Optional[Callable] = None
    ) -> None:
        self._optimizer_types[name] = optimizer_type
        if factory:
            self._optimizer_factories[name] = factory
        logger.debug("Registered optimizer: %s", name)

    def get_optimizer(self, name: str) -> Optional[Type]:
        return self._optimizer_types.get(name)

    def create_optimizer(self, name: str, **kwargs: Any) -> Any:
        factory = self._optimizer_factories.get(name)
        if factory is None:
            raise ValueError(f"No factory registered for optimizer '{name}'")
        return factory(**kwargs)

    def list_optimizers(self) -> List[str]:
        return sorted(self._optimizer_types.keys())

    # ── risk model registry ────────────────────────────────────────────────

    def register_risk_model(
        self, name: str, model_type: Type, factory: Optional[Callable] = None
    ) -> None:
        self._risk_models[name] = model_type
        if factory:
            self._risk_factories[name] = factory
        logger.debug("Registered risk model: %s", name)

    def get_risk_model(self, name: str) -> Optional[Type]:
        return self._risk_models.get(name)

    def create_risk_model(self, name: str, **kwargs: Any) -> Any:
        factory = self._risk_factories.get(name)
        if factory is None:
            raise ValueError(f"No factory registered for risk model '{name}'")
        return factory(**kwargs)

    def list_risk_models(self) -> List[str]:
        return sorted(self._risk_models.keys())

    # ── constraint registry ────────────────────────────────────────────────

    def register_constraint_type(
        self, name: str, constraint_type: Type
    ) -> None:
        self._constraint_types[name] = constraint_type
        logger.debug("Registered constraint type: %s", name)

    def get_constraint_type(self, name: str) -> Optional[Type]:
        return self._constraint_types.get(name)

    def list_constraint_types(self) -> List[str]:
        return sorted(self._constraint_types.keys())

    # ── allocation registry ────────────────────────────────────────────────

    def register_allocation_method(
        self, name: str, method: Callable
    ) -> None:
        self._allocation_methods[name] = method
        logger.debug("Registered allocation method: %s", name)

    def get_allocation_method(self, name: str) -> Optional[Callable]:
        return self._allocation_methods.get(name)

    def list_allocation_methods(self) -> List[str]:
        return sorted(self._allocation_methods.keys())

    # ── benchmark registry ─────────────────────────────────────────────────

    def register_benchmark(
        self, name: str, config: Dict[str, Any]
    ) -> None:
        self._benchmarks[name] = config
        logger.debug("Registered benchmark: %s", name)

    def get_benchmark(self, name: str) -> Optional[Dict[str, Any]]:
        return self._benchmarks.get(name)

    def list_benchmarks(self) -> List[str]:
        return sorted(self._benchmarks.keys())

    # ── alpha pool registry ────────────────────────────────────────────────

    def register_alpha_pool(
        self, name: str, config: Dict[str, Any]
    ) -> None:
        self._alpha_pools[name] = config
        logger.debug("Registered alpha pool: %s", name)

    def get_alpha_pool(self, name: str) -> Optional[Dict[str, Any]]:
        return self._alpha_pools.get(name)

    def list_alpha_pools(self) -> List[str]:
        return sorted(self._alpha_pools.keys())

    # ── summary ────────────────────────────────────────────────────────────

    def summary(self) -> Dict[str, Any]:
        return {
            "optimizers": self.list_optimizers(),
            "risk_models": self.list_risk_models(),
            "constraint_types": self.list_constraint_types(),
            "allocation_methods": self.list_allocation_methods(),
            "benchmarks": self.list_benchmarks(),
            "alpha_pools": self.list_alpha_pools(),
        }
