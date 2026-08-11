"""Research Adapter — bridges the AI Platform to the ICYQuant Research Platform.

The ResearchAdapter translates AI agent research requests into Research Platform
calls for factor analysis, backtesting, and data exploration. It provides a
clean interface for agents to leverage the full research capabilities.

Capabilities:
    - Factor discovery and evaluation
    - Backtesting execution
    - Data query and transformation
    - Research result normalization
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ResearchRequest:
    """A research request from an AI agent."""
    request_id: str = ""
    agent_id: str = ""
    request_type: str = ""  # factor, backtest, data_query
    params: Dict[str, Any] = field(default_factory=dict)
    timeout_sec: float = 120.0


@dataclass
class ResearchResult:
    """Result from a research platform call."""
    request_id: str = ""
    success: bool = False
    data: Any = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class ResearchAdapter:
    """Adapter for the ICYQuant Research Platform.

    Provides AI agents with access to factor analysis, backtesting,
    and data exploration capabilities of the Research Platform.

    Usage:
        ra = ResearchAdapter()
        await ra.initialize()
        result = await ra.query(ResearchRequest(agent_id="agent_1", request_type="backtest", params={...}))
    """

    def __init__(self) -> None:
        self._total_requests: int = 0
        self._total_success: int = 0
        self._total_errors: int = 0
        self._results: List[ResearchResult] = []
        self._max_results: int = 1000
        self._initialized: bool = False
        logger.info("ResearchAdapter created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("ResearchAdapter initialized")

    async def shutdown(self) -> None:
        self._results.clear()
        self._initialized = False
        logger.info("ResearchAdapter shutdown complete")

    async def query(self, request: ResearchRequest) -> ResearchResult:
        """Execute a research request.

        Routes the request to the appropriate Research Platform service
        based on request_type.
        """
        self._total_requests += 1

        # TODO: Actual integration with Research Platform
        result = ResearchResult(
            request_id=request.request_id,
            success=True,
            data={"message": f"Research request '{request.request_type}' processed"},
        )

        if result.success:
            self._total_success += 1
        else:
            self._total_errors += 1

        self._results.append(result)
        if len(self._results) > self._max_results:
            self._results = self._results[-self._max_results:]

        logger.info("ResearchAdapter: processed %s request from agent %s", request.request_type, request.agent_id)
        return result

    async def discover_factors(self, agent_id: str, params: Dict[str, Any]) -> ResearchResult:
        """Discover factors using the Research Platform."""
        return await self.query(ResearchRequest(agent_id=agent_id, request_type="factor_discovery", params=params))

    async def run_backtest(self, agent_id: str, params: Dict[str, Any]) -> ResearchResult:
        """Run a backtest using the Research Platform."""
        return await self.query(ResearchRequest(agent_id=agent_id, request_type="backtest", params=params))

    async def query_data(self, agent_id: str, params: Dict[str, Any]) -> ResearchResult:
        """Query market data using the Research Platform."""
        return await self.query(ResearchRequest(agent_id=agent_id, request_type="data_query", params=params))

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "total_requests": self._total_requests,
            "total_success": self._total_success,
            "total_errors": self._total_errors,
            "success_rate": round(self._total_success / self._total_requests * 100, 1) if self._total_requests > 0 else 0.0,
        }
