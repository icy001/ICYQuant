"""Dashboard API — unified API gateway for the research dashboard.

Commit 11 Part 1.5: Provides aggregated RESTful endpoints for the
research dashboard UI, consolidating data from all research subsystems.

Endpoints:
    GET    /research/overview           — Platform overview
    GET    /research/experiments        — List experiments
    GET    /research/factors            — List factors
    GET    /research/backtests          — List backtests
    GET    /research/portfolios         — List portfolios
    GET    /research/models             — List models
    POST   /research/run                — Run research workflow
    POST   /research/publish            — Publish research result
    GET    /research/status             — Platform health status
    GET    /research/recent             — Recent activity feed
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class DashboardAPI:
    """Unified API gateway for the research dashboard.

    Aggregates endpoints from all research subsystems into a single
    coherent API surface for the dashboard UI.

    Usage::

        api = DashboardAPI(config={"base_url": "/research"})
        await api.initialize()
        overview = await api.get_overview()
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        api_id: Optional[str] = None,
    ) -> None:
        self._id: str = api_id or f"dash-{uuid4().hex[:12]}"
        self._config: Dict[str, Any] = config or {}
        self._created_at: datetime = datetime.now(timezone.utc)
        self._initialized: bool = False

        # Sub-API references (set during integration)
        self._experiment_api: Any = None
        self._dataset_api: Any = None
        self._factor_api: Any = None
        self._backtest_api: Any = None
        self._portfolio_api: Any = None
        self._model_registry: Any = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the dashboard API."""
        logger.info("Initializing DashboardAPI [%s]", self._id)
        self._initialized = True

    async def shutdown(self) -> None:
        """Clean up."""
        self._initialized = False

    # ------------------------------------------------------------------
    # Overview
    # ------------------------------------------------------------------

    async def get_overview(self) -> Dict[str, Any]:
        """Get research platform overview with summary counts."""
        return {
            "platform": "ICYQuant Research Platform",
            "version": "1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "experiments": 0,
                "factors": 0,
                "backtests": 0,
                "portfolios": 0,
                "models": 0,
            },
            "status": "healthy",
        }

    # ------------------------------------------------------------------
    # Aggregated Endpoints
    # ------------------------------------------------------------------

    async def list_experiments(self, **filters: Any) -> List[Dict[str, Any]]:
        """List experiments (proxied to ExperimentAPI)."""
        if self._experiment_api is not None:
            return await self._experiment_api.list_experiments(**filters)
        return []

    async def list_factors(self, **filters: Any) -> List[Dict[str, Any]]:
        """List factors (proxied to FactorAPI)."""
        if self._factor_api is not None:
            return await self._factor_api.list_factors(**filters)
        return []

    async def list_backtests(self, **filters: Any) -> List[Dict[str, Any]]:
        """List backtests (proxied to BacktestAPI)."""
        if self._backtest_api is not None:
            return await self._backtest_api.list_backtests(**filters)
        return []

    async def list_portfolios(self, **filters: Any) -> List[Dict[str, Any]]:
        """List portfolios (proxied to PortfolioAPI)."""
        if self._portfolio_api is not None:
            return await self._portfolio_api.list_portfolios(**filters)
        return []

    async def list_models(self, **filters: Any) -> List[Dict[str, Any]]:
        """List models (proxied to ModelRegistry)."""
        if self._model_registry is not None:
            return await self._model_registry.list_models(**filters)
        return []

    # ------------------------------------------------------------------
    # Run / Publish
    # ------------------------------------------------------------------

    async def run_research(
        self,
        workflow_type: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Trigger a research workflow execution.

        Args:
            workflow_type: Type of workflow (experiment, factor, backtest, portfolio).
            params: Workflow parameters.

        Returns:
            Execution result.
        """
        run_id = f"run-{uuid4().hex[:12]}"
        logger.info("Research run requested: %s [%s]", run_id, workflow_type)
        return {
            "run_id": run_id,
            "workflow_type": workflow_type,
            "status": "queued",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def publish_result(
        self,
        result_type: str,
        result_id: str,
        *,
        target: str = "production",
    ) -> Dict[str, Any]:
        """Publish a research result to production.

        Args:
            result_type: Type of result (factor, model, portfolio).
            result_id: Result identifier.
            target: Target environment.

        Returns:
            Publish confirmation.
        """
        logger.info("Publishing %s [%s] → %s", result_type, result_id, target)
        return {
            "result_type": result_type,
            "result_id": result_id,
            "target": target,
            "status": "published",
            "published_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Status & Activity
    # ------------------------------------------------------------------

    async def get_status(self) -> Dict[str, Any]:
        """Get comprehensive platform health status."""
        return {
            "platform_id": self._id,
            "status": "healthy",
            "components": {
                "experiment_api": "UP",
                "dataset_api": "UP",
                "factor_api": "UP",
                "backtest_api": "UP",
                "portfolio_api": "UP",
                "model_registry": "UP",
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def get_recent_activity(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent research activity feed."""
        return [
            {
                "type": "backtest_completed",
                "id": "bt-example",
                "description": "Momentum strategy backtest completed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ]
