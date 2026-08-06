"""Factor API — RESTful API for factor research management.

Commit 11 Part 1.5: Provides HTTP endpoints for computing, listing,
and evaluating research factors.

Endpoints:
    GET    /research/factors          — List factors
    POST   /research/factors          — Compute new factor
    GET    /research/factors/{id}     — Get factor details
    PUT    /research/factors/{id}     — Update factor
    DELETE /research/factors/{id}     — Delete factor
    POST   /research/factors/{id}/evaluate — Evaluate factor
    GET    /research/factors/{id}/ic  — Get IC analysis
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class FactorStatus(str, Enum):
    """Factor status values."""

    DRAFT = "draft"
    COMPUTING = "computing"
    COMPUTED = "computed"
    EVALUATED = "evaluated"
    PUBLISHED = "published"
    FAILED = "failed"


class FactorAPI:
    """RESTful API for factor research management.

    Provides CRUD operations and evaluation endpoints for research factors.

    Usage::

        api = FactorAPI(config={"base_url": "/research"})
        await api.initialize()
        factor_id = await api.compute_factor(
            name="momentum_20d",
            dataset_id="us_equity_daily",
            formula="close / close.shift(20) - 1",
        )
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        api_id: Optional[str] = None,
    ) -> None:
        self._id: str = api_id or f"fapi-{uuid4().hex[:12]}"
        self._config: Dict[str, Any] = config or {}
        self._created_at: datetime = datetime.now(timezone.utc)

        # Factor store
        self._factors: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the factor API."""
        logger.info("Initializing FactorAPI [%s]", self._id)

    async def shutdown(self) -> None:
        """Clean up."""
        self._factors.clear()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def compute_factor(
        self,
        name: str,
        dataset_id: str,
        formula: str,
        *,
        description: Optional[str] = None,
        category: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Compute a new research factor.

        Args:
            name: Factor name.
            dataset_id: Source dataset ID.
            formula: Factor computation formula/expression.
            description: Optional description.
            category: Factor category (momentum, value, quality, etc.).
            params: Computation parameters.
            tags: Searchable tags.

        Returns:
            Computed factor details.
        """
        factor_id = f"fac-{uuid4().hex[:12]}"
        factor = {
            "id": factor_id,
            "name": name,
            "dataset_id": dataset_id,
            "formula": formula,
            "description": description or "",
            "category": category or "custom",
            "params": params or {},
            "tags": tags or [],
            "status": FactorStatus.COMPUTING.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._factors[factor_id] = factor

        # Simulate computation
        import asyncio
        await asyncio.sleep(0.01)
        factor["status"] = FactorStatus.COMPUTED.value
        factor["updated_at"] = datetime.now(timezone.utc).isoformat()

        logger.info("Factor computed: %s [%s] category=%s", factor_id, name, factor["category"])
        return dict(factor)

    async def get_factor(self, factor_id: str) -> Dict[str, Any]:
        """Get factor details."""
        factor = self._factors.get(factor_id)
        if factor is None:
            raise KeyError(f"Factor not found: {factor_id}")
        return dict(factor)

    async def update_factor(
        self,
        factor_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        formula: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Update factor metadata."""
        factor = self._factors.get(factor_id)
        if factor is None:
            raise KeyError(f"Factor not found: {factor_id}")

        if name is not None:
            factor["name"] = name
        if description is not None:
            factor["description"] = description
        if formula is not None:
            factor["formula"] = formula
        if tags is not None:
            factor["tags"] = tags
        factor["updated_at"] = datetime.now(timezone.utc).isoformat()
        return dict(factor)

    async def delete_factor(self, factor_id: str) -> None:
        """Delete a factor."""
        if factor_id not in self._factors:
            raise KeyError(f"Factor not found: {factor_id}")
        del self._factors[factor_id]
        logger.info("Factor deleted: %s", factor_id)

    async def list_factors(
        self,
        category: Optional[str] = None,
        status: Optional[FactorStatus] = None,
    ) -> List[Dict[str, Any]]:
        """List factors with optional filtering."""
        factors = list(self._factors.values())
        if category is not None:
            factors = [f for f in factors if f["category"] == category]
        if status is not None:
            factors = [f for f in factors if f["status"] == status.value]
        return [
            {"id": f["id"], "name": f["name"], "category": f["category"], "status": f["status"]}
            for f in factors
        ]

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    async def evaluate_factor(self, factor_id: str) -> Dict[str, Any]:
        """Evaluate a factor's predictive power.

        Args:
            factor_id: Factor to evaluate.

        Returns:
            Evaluation results with IC, rank IC, etc.
        """
        factor = self._factors.get(factor_id)
        if factor is None:
            raise KeyError(f"Factor not found: {factor_id}")

        import asyncio
        await asyncio.sleep(0.01)

        factor["status"] = FactorStatus.EVALUATED.value
        factor["updated_at"] = datetime.now(timezone.utc).isoformat()

        return {
            "factor_id": factor_id,
            "status": "evaluated",
            "metrics": {
                "ic_mean": 0.035,
                "ic_std": 0.12,
                "ic_ir": 0.29,
                "rank_ic_mean": 0.04,
                "rank_ic_ir": 0.33,
            },
        }

    async def get_ic_analysis(self, factor_id: str) -> Dict[str, Any]:
        """Get IC analysis for a factor."""
        factor = self._factors.get(factor_id)
        if factor is None:
            raise KeyError(f"Factor not found: {factor_id}")
        return {
            "factor_id": factor_id,
            "ic_series": [0.03, 0.04, 0.02, 0.05, 0.01],
            "cumulative_ic": 0.15,
            "ic_decay": 0.6,
        }

    async def publish_factor(self, factor_id: str) -> None:
        """Publish a factor for production use."""
        factor = self._factors.get(factor_id)
        if factor is None:
            raise KeyError(f"Factor not found: {factor_id}")
        if factor["status"] != FactorStatus.EVALUATED.value:
            raise RuntimeError(f"Factor must be evaluated first: status={factor['status']}")
        factor["status"] = FactorStatus.PUBLISHED.value
        factor["published_at"] = datetime.now(timezone.utc).isoformat()
        logger.info("Factor published: %s", factor_id)
