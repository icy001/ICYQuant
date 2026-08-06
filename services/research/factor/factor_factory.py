"""Factor Factory — object construction for factor research entities.

Provides factory methods for creating factors, alpha entries, evaluation
runs, and related entities with consistent defaults.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class FactorFactory:
    """Factory for constructing factor research entities.

    Each factory method produces a dictionary suitable for persistence
    via FactorRepository, ensuring consistent defaults and required fields.
    """

    @staticmethod
    def create_factor(
        name: str,
        factor_type: str = "custom",
        expression: Optional[str] = None,
        universe: Optional[List[str]] = None,
        params: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        return {
            "id": str(uuid4()),
            "name": name,
            "factor_type": factor_type,
            "expression": expression,
            "universe": universe or [],
            "params": params or {},
            "metadata": metadata or {},
            "tags": tags or [],
            "status": "draft",
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }

    @staticmethod
    def create_factor_run(
        factor_id: str,
        dataset_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        return {
            "id": str(uuid4()),
            "factor_id": factor_id,
            "dataset_id": dataset_id,
            "start_date": start_date,
            "end_date": end_date,
            "config": config or {},
            "status": "pending",
            "created_at": now,
            "updated_at": now,
        }

    @staticmethod
    def create_alpha_entry(
        factor_id: str,
        factor_name: str,
        ic_mean: float = 0.0,
        icir: float = 0.0,
        rank_ic: float = 0.0,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        return {
            "id": str(uuid4()),
            "factor_id": factor_id,
            "factor_name": factor_name,
            "ic_mean": ic_mean,
            "icir": icir,
            "rank_ic": rank_ic,
            "status": "candidate",
            "tags": tags or [],
            "created_at": now,
            "updated_at": now,
        }

    @staticmethod
    def create_evaluation(
        factor_id: str,
        eval_type: str,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        return {
            "id": str(uuid4()),
            "factor_id": factor_id,
            "eval_type": eval_type,
            "metrics": metrics or {},
            "created_at": now,
        }

    @staticmethod
    def create_feature(
        name: str,
        feature_type: str = "custom",
        source: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        return {
            "id": str(uuid4()),
            "name": name,
            "feature_type": feature_type,
            "source": source,
            "params": params or {},
            "metadata": metadata or {},
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
