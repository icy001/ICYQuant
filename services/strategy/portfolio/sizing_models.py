"""
Sizing Models Registry
======================
Base model and registry for position sizing models.
Supports custom model registration and discovery.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SizingContext:
    """Context passed to sizing models during computation."""

    account_equity: float = 0.0
    risk_free_rate: float = 0.0
    max_leverage: float = 1.0
    portfolio_volatility: float = 0.0
    num_positions: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseSizingModel(ABC):
    """
    Abstract base class for position sizing models.

    All sizing models must implement compute() which takes a dict
    of parameters and returns a dict with at minimum:
    - position_size
    - position_value
    - position_weight
    - reason
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._name = self.__class__.__name__
        self._version = "1.0.0"

    async def initialize(self) -> None:
        """Optional async initialization."""
        pass

    async def shutdown(self) -> None:
        """Optional async cleanup."""
        pass

    @abstractmethod
    async def compute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute position size from input parameters.

        Args:
            params: Dictionary with sizing inputs (account_equity, risk_budget, etc.)

        Returns:
            Dict with position_size, position_value, position_weight, risk_exposure, reason.
        """
        ...

    def validate_params(self, params: Dict[str, Any]) -> List[str]:
        """Validate input parameters. Returns list of error messages."""
        errors = []
        if params.get("account_equity", 0) <= 0:
            errors.append("account_equity must be positive")
        if params.get("current_price", 0) <= 0:
            errors.append("current_price must be positive")
        return errors

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return self._version


class SizingModelRegistry:
    """
    Registry for position sizing models.

    Allows registration, discovery, and lookup of sizing models
    by name or method enum.
    """

    def __init__(self):
        self._models: Dict[str, BaseSizingModel] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}

    def register(
        self,
        name: str,
        model: BaseSizingModel,
        description: str = "",
        tags: Optional[List[str]] = None,
    ) -> None:
        """Register a sizing model."""
        self._models[name] = model
        self._metadata[name] = {
            "description": description,
            "tags": tags or [],
            "version": model.version,
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("Sizing model registered: %s v%s", name, model.version)

    def get(self, name: str) -> Optional[BaseSizingModel]:
        return self._models.get(name)

    def list_models(self) -> List[Dict[str, Any]]:
        """List all registered models with metadata."""
        return [
            {"name": name, **self._metadata.get(name, {})}
            for name in self._models
        ]

    def unregister(self, name: str) -> bool:
        if name in self._models:
            del self._models[name]
            self._metadata.pop(name, None)
            return True
        return False

    @property
    def count(self) -> int:
        return len(self._models)
