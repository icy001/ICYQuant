"""Factor Repository — persistence layer for factor research entities.

Provides CRUD operations for factors, alpha entries, evaluation results,
and feature records with pluggable storage backends.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class FactorRepository:
    """Pluggable persistence layer for factor research entities.

    Supports:
    * Factor CRUD (create, read, update, delete, list, search)
    * Alpha entry storage
    * Evaluation result storage
    * Feature record storage

    Backend: currently in-memory; designed for swap to SQL/NoSQL.
    """

    def __init__(self, backend: str = "memory") -> None:
        self._backend = backend
        self._factors: Dict[str, Dict[str, Any]] = {}
        self._alpha_entries: Dict[str, Dict[str, Any]] = {}
        self._evaluations: Dict[str, Dict[str, Any]] = {}
        self._features: Dict[str, Dict[str, Any]] = {}
        self._factor_runs: Dict[str, Dict[str, Any]] = {}

    # ── factor CRUD ───────────────────────────────────────────────────────

    async def create_factor(self, data: Dict[str, Any]) -> Dict[str, Any]:
        factor_id = data.get("id") or str(uuid4())
        now = datetime.now(timezone.utc)
        record = {
            "id": factor_id,
            "name": data.get("name", ""),
            "factor_type": data.get("factor_type", "custom"),
            "expression": data.get("expression"),
            "universe": data.get("universe", []),
            "params": data.get("params", {}),
            "metadata": data.get("metadata", {}),
            "tags": data.get("tags", []),
            "status": data.get("status", "draft"),
            "version": data.get("version", 1),
            "created_at": data.get("created_at", now),
            "updated_at": data.get("updated_at", now),
        }
        self._factors[factor_id] = record
        logger.info("Factor %s created: %s", factor_id, record["name"])
        return record

    async def get_factor(self, factor_id: str) -> Optional[Dict[str, Any]]:
        return self._factors.get(factor_id)

    async def update_factor(
        self, factor_id: str, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        record = self._factors.get(factor_id)
        if record is None:
            return None
        updates["updated_at"] = datetime.now(timezone.utc)
        record.update(updates)
        return record

    async def delete_factor(self, factor_id: str) -> bool:
        return self._factors.pop(factor_id, None) is not None

    async def list_factors(
        self,
        factor_type: Optional[str] = None,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        results = list(self._factors.values())
        if factor_type:
            results = [f for f in results if f.get("factor_type") == factor_type]
        if status:
            results = [f for f in results if f.get("status") == status]
        if tags:
            results = [
                f for f in results if any(t in f.get("tags", []) for t in tags)
            ]
        results.sort(key=lambda f: f.get("created_at", ""), reverse=True)
        return results[offset : offset + limit]

    async def search_factors(self, query: str) -> List[Dict[str, Any]]:
        query_lower = query.lower()
        return [
            f
            for f in self._factors.values()
            if query_lower in f.get("name", "").lower()
            or query_lower in f.get("factor_type", "").lower()
            or any(query_lower in t.lower() for t in f.get("tags", []))
        ]

    # ── alpha entry CRUD ──────────────────────────────────────────────────

    async def create_alpha_entry(self, data: Dict[str, Any]) -> Dict[str, Any]:
        entry_id = data.get("id") or str(uuid4())
        now = datetime.now(timezone.utc)
        record = {
            "id": entry_id,
            "factor_id": data.get("factor_id", ""),
            "factor_name": data.get("factor_name", ""),
            "ic_mean": data.get("ic_mean", 0.0),
            "icir": data.get("icir", 0.0),
            "rank_ic": data.get("rank_ic", 0.0),
            "status": data.get("status", "candidate"),
            "tags": data.get("tags", []),
            "created_at": data.get("created_at", now),
            "updated_at": data.get("updated_at", now),
        }
        self._alpha_entries[entry_id] = record
        return record

    async def get_alpha_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        return self._alpha_entries.get(entry_id)

    async def list_alpha_entries(
        self, status: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        results = list(self._alpha_entries.values())
        if status:
            results = [e for e in results if e.get("status") == status]
        results.sort(key=lambda e: e.get("icir", 0), reverse=True)
        return results[:limit]

    async def update_alpha_entry(
        self, entry_id: str, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        record = self._alpha_entries.get(entry_id)
        if record is None:
            return None
        updates["updated_at"] = datetime.now(timezone.utc)
        record.update(updates)
        return record

    # ── evaluation CRUD ───────────────────────────────────────────────────

    async def create_evaluation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        eval_id = data.get("id") or str(uuid4())
        now = datetime.now(timezone.utc)
        record = {
            "id": eval_id,
            "factor_id": data.get("factor_id", ""),
            "eval_type": data.get("eval_type", ""),
            "metrics": data.get("metrics", {}),
            "created_at": data.get("created_at", now),
        }
        self._evaluations[eval_id] = record
        return record

    async def get_evaluations_for_factor(
        self, factor_id: str
    ) -> List[Dict[str, Any]]:
        return [
            e
            for e in self._evaluations.values()
            if e.get("factor_id") == factor_id
        ]

    # ── feature CRUD ──────────────────────────────────────────────────────

    async def create_feature(self, data: Dict[str, Any]) -> Dict[str, Any]:
        feature_id = data.get("id") or str(uuid4())
        now = datetime.now(timezone.utc)
        record = {
            "id": feature_id,
            "name": data.get("name", ""),
            "feature_type": data.get("feature_type", "custom"),
            "source": data.get("source"),
            "params": data.get("params", {}),
            "metadata": data.get("metadata", {}),
            "version": data.get("version", 1),
            "created_at": data.get("created_at", now),
            "updated_at": data.get("updated_at", now),
        }
        self._features[feature_id] = record
        return record

    async def list_features(
        self,
        feature_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        results = list(self._features.values())
        if feature_type:
            results = [f for f in results if f.get("feature_type") == feature_type]
        return results[:limit]

    # ── factor run CRUD ───────────────────────────────────────────────────

    async def create_factor_run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        run_id = data.get("id") or str(uuid4())
        now = datetime.now(timezone.utc)
        record = {
            "id": run_id,
            "factor_id": data.get("factor_id", ""),
            "dataset_id": data.get("dataset_id"),
            "start_date": data.get("start_date"),
            "end_date": data.get("end_date"),
            "config": data.get("config", {}),
            "status": data.get("status", "pending"),
            "created_at": data.get("created_at", now),
            "updated_at": data.get("updated_at", now),
        }
        self._factor_runs[run_id] = record
        return record

    async def get_factor_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        return self._factor_runs.get(run_id)

    async def list_factor_runs(
        self, factor_id: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        results = list(self._factor_runs.values())
        if factor_id:
            results = [r for r in results if r.get("factor_id") == factor_id]
        results.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return results[:limit]

    # ── stats ─────────────────────────────────────────────────────────────

    def stats(self) -> Dict[str, int]:
        return {
            "factors": len(self._factors),
            "alpha_entries": len(self._alpha_entries),
            "evaluations": len(self._evaluations),
            "features": len(self._features),
            "factor_runs": len(self._factor_runs),
        }
