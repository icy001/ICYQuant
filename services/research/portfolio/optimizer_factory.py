"""Optimizer Factory — create optimizer instances by type.

Provides a unified factory for instantiating any optimizer type
with consistent configuration.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .optimizer import Optimizer, OptimizerType
from .mean_variance import MeanVarianceOptimizer
from .risk_parity import RiskParityOptimizer
from .black_litterman import BlackLittermanOptimizer
from .hierarchical_risk_parity import HRPOptimizer

logger = logging.getLogger(__name__)


class OptimizerFactory:
    """Create optimizer instances by type with unified config."""

    # Registry of optimizer types
    _registry: Dict[str, type] = {
        OptimizerType.MEAN_VARIANCE.value: MeanVarianceOptimizer,
        OptimizerType.RISK_PARITY.value: RiskParityOptimizer,
        OptimizerType.BLACK_LITTERMAN.value: BlackLittermanOptimizer,
        OptimizerType.HRP.value: HRPOptimizer,
    }

    def __init__(self) -> None:
        pass

    def create(
        self,
        optimizer_type: str,
        cov_matrix: Optional[Dict[str, Dict[str, float]]] = None,
        expected_returns: Optional[Dict[str, float]] = None,
        constraints: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Optimizer:
        """Create an optimizer instance.

        Args:
            optimizer_type: One of 'mean_variance', 'risk_parity',
                'black_litterman', 'hierarchical_risk_parity'.
            cov_matrix: Asset covariance matrix.
            expected_returns: Expected returns per asset.
            constraints: Optimization constraints.
            **kwargs: Optimizer-specific parameters.

        Returns:
            Configured optimizer instance.
        """
        cls = self._registry.get(optimizer_type)
        if cls is None:
            raise ValueError(
                f"Unknown optimizer type '{optimizer_type}'. "
                f"Available: {list(self._registry.keys())}"
            )

        logger.info("Creating optimizer: %s", optimizer_type)

        # Merge constraints with kwargs for optimizer-specific params
        merged_kwargs = dict(kwargs)
        if constraints:
            merged_kwargs["constraints"] = constraints

        return cls(
            cov_matrix=cov_matrix or {},
            expected_returns=expected_returns or {},
            **merged_kwargs,
        )

    def register(self, name: str, optimizer_cls: type) -> None:
        """Register a custom optimizer type."""
        self._registry[name] = optimizer_cls
        logger.info("Registered custom optimizer: %s", name)

    def list_types(self) -> list:
        return sorted(self._registry.keys())
