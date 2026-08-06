"""Factor Registry — central registry for factor types, transformations, and evaluators.

Maintains dynamic registrations of factor categories, normalization methods,
neutralization targets, and evaluation modules discoverable at runtime.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class FactorType(str, Enum):
    """Predefined factor categories."""

    MOMENTUM = "momentum"
    REVERSAL = "reversal"
    VALUE = "value"
    GROWTH = "growth"
    QUALITY = "quality"
    VOLATILITY = "volatility"
    SIZE = "size"
    LIQUIDITY = "liquidity"
    SENTIMENT = "sentiment"
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    MACRO = "macro"
    ALTERNATIVE = "alternative"
    CUSTOM = "custom"
    COMPOSITE = "composite"


class FactorRegistry:
    """Central registry for factor research components.

    Registers:
    * Factor types → factory callables
    * Normalization methods → transformer callables
    * Neutralization targets → neutralizer callables
    * Evaluation methods → evaluator callables
    * Feature generators → feature callables
    """

    def __init__(self) -> None:
        self._factor_types: Dict[str, Type] = {}
        self._factor_factories: Dict[str, Callable] = {}
        self._normalizers: Dict[str, Callable] = {}
        self._neutralizers: Dict[str, Callable] = {}
        self._evaluators: Dict[str, Callable] = {}
        self._feature_generators: Dict[str, Callable] = {}
        self._winsorizers: Dict[str, Callable] = {}
        self._orthogonalizers: Dict[str, Callable] = {}

    # ── factor type registry ──────────────────────────────────────────────

    def register_factor_type(
        self, name: str, cls: Type, factory: Optional[Callable] = None
    ) -> None:
        self._factor_types[name] = cls
        if factory:
            self._factor_factories[name] = factory
        logger.debug("Registered factor type: %s", name)

    def get_factor_type(self, name: str) -> Optional[Type]:
        return self._factor_types.get(name)

    def create_factor(self, name: str, **kwargs) -> Any:
        factory = self._factor_factories.get(name)
        if factory is None:
            raise ValueError(f"No factory registered for factor type: {name}")
        return factory(**kwargs)

    def list_factor_types(self) -> List[str]:
        return list(self._factor_types.keys())

    # ── normalizer registry ───────────────────────────────────────────────

    def register_normalizer(self, name: str, callable_fn: Callable) -> None:
        self._normalizers[name] = callable_fn
        logger.debug("Registered normalizer: %s", name)

    def get_normalizer(self, name: str) -> Optional[Callable]:
        return self._normalizers.get(name)

    def list_normalizers(self) -> List[str]:
        return list(self._normalizers.keys())

    # ── neutralizer registry ──────────────────────────────────────────────

    def register_neutralizer(self, name: str, callable_fn: Callable) -> None:
        self._neutralizers[name] = callable_fn
        logger.debug("Registered neutralizer: %s", name)

    def get_neutralizer(self, name: str) -> Optional[Callable]:
        return self._neutralizers.get(name)

    def list_neutralizers(self) -> List[str]:
        return list(self._neutralizers.keys())

    # ── evaluator registry ────────────────────────────────────────────────

    def register_evaluator(self, name: str, callable_fn: Callable) -> None:
        self._evaluators[name] = callable_fn
        logger.debug("Registered evaluator: %s", name)

    def get_evaluator(self, name: str) -> Optional[Callable]:
        return self._evaluators.get(name)

    def list_evaluators(self) -> List[str]:
        return list(self._evaluators.keys())

    # ── feature generator registry ────────────────────────────────────────

    def register_feature_generator(self, name: str, callable_fn: Callable) -> None:
        self._feature_generators[name] = callable_fn
        logger.debug("Registered feature generator: %s", name)

    def get_feature_generator(self, name: str) -> Optional[Callable]:
        return self._feature_generators.get(name)

    def list_feature_generators(self) -> List[str]:
        return list(self._feature_generators.keys())

    # ── winsorizer registry ───────────────────────────────────────────────

    def register_winsorizer(self, name: str, callable_fn: Callable) -> None:
        self._winsorizers[name] = callable_fn
        logger.debug("Registered winsorizer: %s", name)

    def get_winsorizer(self, name: str) -> Optional[Callable]:
        return self._winsorizers.get(name)

    def list_winsorizers(self) -> List[str]:
        return list(self._winsorizers.keys())

    # ── orthogonalizer registry ───────────────────────────────────────────

    def register_orthogonalizer(self, name: str, callable_fn: Callable) -> None:
        self._orthogonalizers[name] = callable_fn
        logger.debug("Registered orthogonalizer: %s", name)

    def get_orthogonalizer(self, name: str) -> Optional[Callable]:
        return self._orthogonalizers.get(name)

    def list_orthogonalizers(self) -> List[str]:
        return list(self._orthogonalizers.keys())

    # ── summary ───────────────────────────────────────────────────────────

    def summary(self) -> Dict[str, List[str]]:
        return {
            "factor_types": self.list_factor_types(),
            "normalizers": self.list_normalizers(),
            "neutralizers": self.list_neutralizers(),
            "evaluators": self.list_evaluators(),
            "feature_generators": self.list_feature_generators(),
            "winsorizers": self.list_winsorizers(),
            "orthogonalizers": self.list_orthogonalizers(),
        }
