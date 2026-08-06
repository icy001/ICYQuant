"""Portfolio Repository — persistence layer for portfolio entities.

Provides CRUD operations for portfolios, weights, optimizations,
risk reports, stress tests, and portfolio reports.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class PortfolioRepository:
    """Pluggable persistence layer for portfolio entities.

    Supports:
    * Portfolio CRUD
    * Weight snapshot storage
    * Optimization result storage
    * Risk report storage
    * Stress test result storage
    * Portfolio report storage

    Backend: currently in-memory; designed for swap to SQL/NoSQL.
    """

    def __init__(self, backend: str = "memory") -> None:
        self._backend = backend
        self._portfolios: Dict[str, Dict[str, Any]] = {}
        self._weights: Dict[str, List[Dict[str, Any]]] = {}
        self._optimizations: Dict[str, Dict[str, Any]] = {}
        self._risk_reports: Dict[str, Dict[str, Any]] = {}
        self._stress_tests: Dict[str, Dict[str, Any]] = {}
        self._scenarios: Dict[str, Dict[str, Any]] = {}
        self._reports: Dict[str, Dict[str, Any]] = {}
        self._exposures: Dict[str, Dict[str, Any]] = {}
        self._attributions: Dict[str, Dict[str, Any]] = {}

    # ── portfolio CRUD ─────────────────────────────────────────────────────

    async def create_portfolio(self, data: Dict[str, Any]) -> Dict[str, Any]:
        p_id = data.get("id") or str(uuid4())
        now = datetime.now(timezone.utc)
        record = {
            "id": p_id,
            "name": data.get("name", ""),
            "category": data.get("category", "long_only"),
            "universe": data.get("universe", []),
            "benchmark": data.get("benchmark", "CSI300"),
            "optimizer": data.get("optimizer", "mean_variance"),
            "status": data.get("status", "draft"),
            "weights": data.get("weights", {}),
            "target_return": data.get("target_return"),
            "risk_aversion": data.get("risk_aversion", 1.0),
            "constraints": data.get("constraints", {}),
            "tags": data.get("tags", []),
            "metadata": data.get("metadata", {}),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        self._portfolios[p_id] = record
        logger.info("Created portfolio: %s (%s)", p_id, record.get("name"))
        return record

    async def get_portfolio(self, p_id: str) -> Optional[Dict[str, Any]]:
        return self._portfolios.get(p_id)

    async def update_portfolio(
        self, p_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        record = self._portfolios.get(p_id)
        if record is None:
            return None
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        record.update(data)
        return record

    async def delete_portfolio(self, p_id: str) -> bool:
        if p_id in self._portfolios:
            del self._portfolios[p_id]
            return True
        return False

    async def list_portfolios(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        results = list(self._portfolios.values())
        if category:
            results = [r for r in results if r.get("category") == category]
        if status:
            results = [r for r in results if r.get("status") == status]
        if tags:
            results = [r for r in results if set(tags) & set(r.get("tags", []))]
        return results

    # ── weights ────────────────────────────────────────────────────────────

    async def save_weights(
        self, portfolio_id: str, weights: Dict[str, float], date: Optional[str] = None
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        record = {
            "id": str(uuid4()),
            "portfolio_id": portfolio_id,
            "weights": weights,
            "date": date or now.strftime("%Y-%m-%d"),
            "timestamp": now.isoformat(),
        }
        self._weights.setdefault(portfolio_id, []).append(record)
        return record

    async def get_latest_weights(
        self, portfolio_id: str
    ) -> Optional[Dict[str, Any]]:
        records = self._weights.get(portfolio_id, [])
        return records[-1] if records else None

    async def get_weights_history(
        self, portfolio_id: str
    ) -> List[Dict[str, Any]]:
        return self._weights.get(portfolio_id, [])

    # ── optimizations ──────────────────────────────────────────────────────

    async def save_optimization(
        self, portfolio_id: str, result: Dict[str, Any]
    ) -> Dict[str, Any]:
        opt_id = str(uuid4())
        now = datetime.now(timezone.utc)
        record = {
            "id": opt_id,
            "portfolio_id": portfolio_id,
            "result": result,
            "created_at": now.isoformat(),
        }
        self._optimizations[opt_id] = record
        return record

    async def get_optimization(self, opt_id: str) -> Optional[Dict[str, Any]]:
        return self._optimizations.get(opt_id)

    # ── risk reports ───────────────────────────────────────────────────────

    async def save_risk_report(
        self, portfolio_id: str, report: Dict[str, Any]
    ) -> Dict[str, Any]:
        r_id = str(uuid4())
        now = datetime.now(timezone.utc)
        record = {
            "id": r_id,
            "portfolio_id": portfolio_id,
            "report": report,
            "created_at": now.isoformat(),
        }
        self._risk_reports[r_id] = record
        return record

    async def get_risk_report(self, r_id: str) -> Optional[Dict[str, Any]]:
        return self._risk_reports.get(r_id)

    # ── stress tests ───────────────────────────────────────────────────────

    async def save_stress_test(
        self, portfolio_id: str, result: Dict[str, Any]
    ) -> Dict[str, Any]:
        s_id = str(uuid4())
        now = datetime.now(timezone.utc)
        record = {
            "id": s_id,
            "portfolio_id": portfolio_id,
            "result": result,
            "created_at": now.isoformat(),
        }
        self._stress_tests[s_id] = record
        return record

    async def get_stress_test(self, s_id: str) -> Optional[Dict[str, Any]]:
        return self._stress_tests.get(s_id)

    # ── scenarios ──────────────────────────────────────────────────────────

    async def save_scenario(
        self, portfolio_id: str, scenario: Dict[str, Any]
    ) -> Dict[str, Any]:
        s_id = str(uuid4())
        now = datetime.now(timezone.utc)
        record = {
            "id": s_id,
            "portfolio_id": portfolio_id,
            "scenario": scenario,
            "created_at": now.isoformat(),
        }
        self._scenarios[s_id] = record
        return record

    # ── reports ────────────────────────────────────────────────────────────

    async def save_report(
        self, portfolio_id: str, report: Dict[str, Any]
    ) -> Dict[str, Any]:
        r_id = str(uuid4())
        now = datetime.now(timezone.utc)
        record = {
            "id": r_id,
            "portfolio_id": portfolio_id,
            "report": report,
            "created_at": now.isoformat(),
        }
        self._reports[r_id] = record
        return record

    async def get_report(self, r_id: str) -> Optional[Dict[str, Any]]:
        return self._reports.get(r_id)

    # ── exposures ──────────────────────────────────────────────────────────

    async def save_exposure(
        self, portfolio_id: str, exposure: Dict[str, Any]
    ) -> Dict[str, Any]:
        e_id = str(uuid4())
        now = datetime.now(timezone.utc)
        record = {
            "id": e_id,
            "portfolio_id": portfolio_id,
            "exposure": exposure,
            "created_at": now.isoformat(),
        }
        self._exposures[e_id] = record
        return record

    # ── attributions ───────────────────────────────────────────────────────

    async def save_attribution(
        self, portfolio_id: str, attribution: Dict[str, Any]
    ) -> Dict[str, Any]:
        a_id = str(uuid4())
        now = datetime.now(timezone.utc)
        record = {
            "id": a_id,
            "portfolio_id": portfolio_id,
            "attribution": attribution,
            "created_at": now.isoformat(),
        }
        self._attributions[a_id] = record
        return record
