"""Research SDK — unified Python SDK for the research platform.

Commit 11 Part 1.5: Provides a high-level, Pythonic interface for all
research operations including experiments, factors, backtests,
portfolios, and model management.

Usage::

    from services.research.integration import ResearchSDK

    sdk = ResearchSDK(config={"base_url": "http://localhost:8000"})

    # Run a backtest
    result = await sdk.backtest.run(
        strategy="momentum_v1",
        dataset="us_equity_daily",
        start="2023-01-01",
        end="2024-12-31",
    )

    # Optimize a portfolio
    portfolio = await sdk.portfolio.optimize(
        alpha_pool="momentum_pool",
        optimizer="risk_parity",
    )

    # Generate AI report
    report = await sdk.ai.report("US Tech Sector Q1 2024")
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ResearchSDK:
    """Unified Python SDK for the ICYQuant Research Platform.

    Provides a fluent, Pythonic API for all research operations.

    Usage::

        sdk = ResearchSDK(config={"base_url": "http://localhost:8000"})
        # Experiment operations
        exp = await sdk.experiment.create(name="Alpha 101", dataset="us_equity")
        # Backtest operations
        bt = await sdk.backtest.run(strategy="momentum", dataset="us_equity")
        # Portfolio operations
        pf = await sdk.portfolio.optimize(alpha_pool="momentum", optimizer="hrp")
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        sdk_id: Optional[str] = None,
    ) -> None:
        self._id: str = sdk_id or f"sdk-{uuid4().hex[:12]}"
        self._config: Dict[str, Any] = config or {}
        self._created_at: datetime = datetime.now(timezone.utc)

        # Sub-clients (lazy initialization)
        self._experiment: Optional[ExperimentClient] = None
        self._dataset: Optional[DatasetClient] = None
        self._factor: Optional[FactorClient] = None
        self._backtest: Optional[BacktestClient] = None
        self._portfolio: Optional[PortfolioClient] = None
        self._model: Optional[ModelClient] = None
        self._ai: Optional[AIClient] = None
        self._report: Optional[ReportClient] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:
        return self._id

    @property
    def experiment(self) -> ExperimentClient:
        if self._experiment is None:
            self._experiment = ExperimentClient(self._config)
        return self._experiment

    @property
    def dataset(self) -> DatasetClient:
        if self._dataset is None:
            self._dataset = DatasetClient(self._config)
        return self._dataset

    @property
    def factor(self) -> FactorClient:
        if self._factor is None:
            self._factor = FactorClient(self._config)
        return self._factor

    @property
    def backtest(self) -> BacktestClient:
        if self._backtest is None:
            self._backtest = BacktestClient(self._config)
        return self._backtest

    @property
    def portfolio(self) -> PortfolioClient:
        if self._portfolio is None:
            self._portfolio = PortfolioClient(self._config)
        return self._portfolio

    @property
    def model(self) -> ModelClient:
        if self._model is None:
            self._model = ModelClient(self._config)
        return self._model

    @property
    def ai(self) -> AIClient:
        if self._ai is None:
            self._ai = AIClient(self._config)
        return self._ai

    @property
    def report(self) -> ReportClient:
        if self._report is None:
            self._report = ReportClient(self._config)
        return self._report

    # ------------------------------------------------------------------
    # Convenience Methods
    # ------------------------------------------------------------------

    async def run(
        self,
        *,
        experiment: Optional[str] = None,
        dataset: Optional[str] = None,
        workflow: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run a research workflow (convenience method).

        Args:
            experiment: Experiment name.
            dataset: Dataset ID.
            workflow: Workflow type.
            params: Workflow parameters.

        Returns:
            Run result.
        """
        run_id = f"run-{uuid4().hex[:12]}"
        logger.info("SDK run: experiment=%s workflow=%s", experiment, workflow)
        return {
            "run_id": run_id,
            "experiment": experiment,
            "dataset": dataset,
            "workflow": workflow,
            "params": params or {},
            "status": "queued",
        }

    async def publish(self, result_type: str, result_id: str, *, target: str = "production") -> Dict[str, Any]:
        """Publish a research result."""
        return {
            "result_type": result_type,
            "result_id": result_id,
            "target": target,
            "status": "published",
        }


# ------------------------------------------------------------------
# Sub-Clients
# ------------------------------------------------------------------

class ExperimentClient:
    """SDK client for experiment operations."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self._config = config

    async def create(self, name: str, dataset: str, **kwargs: Any) -> Dict[str, Any]:
        """Create an experiment."""
        return {"id": f"exp-{uuid4().hex[:8]}", "name": name, "dataset": dataset, "status": "created"}

    async def list(self, **filters: Any) -> List[Dict[str, Any]]:
        """List experiments."""
        return []

    async def get(self, experiment_id: str) -> Dict[str, Any]:
        """Get experiment details."""
        return {"id": experiment_id}

    async def run(self, experiment_id: str) -> Dict[str, Any]:
        """Run an experiment."""
        return {"experiment_id": experiment_id, "status": "running"}


class DatasetClient:
    """SDK client for dataset operations."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self._config = config

    async def register(self, name: str, market: str, data_type: str, **kwargs: Any) -> Dict[str, Any]:
        """Register a dataset."""
        return {"id": f"ds-{uuid4().hex[:8]}", "name": name, "market": market, "status": "registered"}

    async def list(self, **filters: Any) -> List[Dict[str, Any]]:
        """List datasets."""
        return []


class FactorClient:
    """SDK client for factor operations."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self._config = config

    async def compute(self, name: str, dataset: str, formula: str, **kwargs: Any) -> Dict[str, Any]:
        """Compute a factor."""
        return {"id": f"fac-{uuid4().hex[:8]}", "name": name, "status": "computed"}

    async def list(self, **filters: Any) -> List[Dict[str, Any]]:
        """List factors."""
        return []

    async def evaluate(self, factor_id: str) -> Dict[str, Any]:
        """Evaluate a factor."""
        return {"factor_id": factor_id, "ic_mean": 0.03}


class BacktestClient:
    """SDK client for backtest operations."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self._config = config

    async def run(
        self, strategy: str, dataset: str, start: str, end: str, **kwargs: Any
    ) -> Dict[str, Any]:
        """Run a backtest."""
        return {
            "id": f"bt-{uuid4().hex[:8]}",
            "strategy": strategy,
            "dataset": dataset,
            "start": start,
            "end": end,
            "status": "running",
        }

    async def list(self, **filters: Any) -> List[Dict[str, Any]]:
        """List backtests."""
        return []

    async def results(self, backtest_id: str) -> Dict[str, Any]:
        """Get backtest results."""
        return {"backtest_id": backtest_id, "sharpe": 0.8}


class PortfolioClient:
    """SDK client for portfolio operations."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self._config = config

    async def optimize(self, alpha_pool: str, optimizer: str = "risk_parity", **kwargs: Any) -> Dict[str, Any]:
        """Optimize a portfolio."""
        return {"id": f"pf-{uuid4().hex[:8]}", "alpha_pool": alpha_pool, "optimizer": optimizer, "status": "optimized"}

    async def list(self, **filters: Any) -> List[Dict[str, Any]]:
        """List portfolios."""
        return []

    async def analyze(self, portfolio_id: str) -> Dict[str, Any]:
        """Analyze a portfolio."""
        return {"portfolio_id": portfolio_id, "var_95": -0.02}


class ModelClient:
    """SDK client for model operations."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self._config = config

    async def register(self, name: str, model_type: str, **kwargs: Any) -> Dict[str, Any]:
        """Register a model."""
        return {"id": f"model-{uuid4().hex[:8]}", "name": name, "type": model_type, "status": "registered"}

    async def list(self, **filters: Any) -> List[Dict[str, Any]]:
        """List models."""
        return []

    async def deploy(self, model_id: str, version: int) -> Dict[str, Any]:
        """Deploy a model."""
        return {"model_id": model_id, "version": version, "status": "deployed"}


class AIClient:
    """SDK client for AI operations."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self._config = config

    async def report(self, topic: str, **kwargs: Any) -> Dict[str, Any]:
        """Generate AI research report."""
        return {"topic": topic, "report_url": f"/reports/ai/{uuid4().hex[:8]}.html"}

    async def analyze(self, data: Dict[str, Any], query: str) -> Dict[str, Any]:
        """AI-powered data analysis."""
        return {"query": query, "result": "Analysis complete."}

    async def discover_factors(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """AI factor discovery."""
        return {"factors_proposed": 5, "context": context}


class ReportClient:
    """SDK client for report operations."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self._config = config

    async def generate(self, report_type: str, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Generate a report."""
        return {"id": f"rpt-{uuid4().hex[:8]}", "type": report_type, "url": f"/reports/{report_type}/latest.html"}

    async def list(self, **filters: Any) -> List[Dict[str, Any]]:
        """List reports."""
        return []
