"""Autonomy Gateway — Unified API for autonomous quant operations.

Exposes the autonomous research capabilities to external systems:
scanning, discovery, hypothesis generation, factor mining, and
strategy candidate creation.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .autonomous_platform import AutonomyConfig

logger = logging.getLogger(__name__)


@dataclass
class ScanRequest:
    """Market scan request."""

    request_id: str
    universe: Optional[List[str]] = None
    scan_types: List[str] = field(default_factory=lambda: ["price", "volume", "volatility"])
    timeframe: str = "daily"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ResearchRequest:
    """Research execution request."""

    request_id: str
    hypothesis_id: Optional[str] = None
    priority: int = 0
    parameters: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AutonomyGateway:
    """Autonomy Gateway — facade for autonomous quant capabilities.

    Public endpoints:
        - scan_market() → List[Observation]
        - detect_opportunities() → List[Opportunity]
        - generate_hypotheses() → List[Hypothesis]
        - discover_factors() → List[Factor]
        - discover_alpha() → List[AlphaCandidate]
        - generate_strategies() → List[StrategyCandidate]
        - run_backtest() → BacktestResult
        - get_status() → PlatformStatus
    """

    def __init__(self, config: "AutonomyConfig") -> None:
        self.config = config
        self._components: Dict[str, Any] = {}
        self._request_count: Dict[str, int] = {}
        self._started = False

    async def start(self) -> None:
        self._started = True
        logger.info("Autonomy Gateway started")

    async def stop(self) -> None:
        self._started = False
        self._components.clear()
        logger.info("Autonomy Gateway stopped")

    def _get_components(self) -> Dict[str, Any]:
        """Lazy-load components."""
        if not self._components:
            from .market_scanner import MarketScanner
            from .opportunity_detector import OpportunityDetector
            from .hypothesis_generator import HypothesisGenerator
            from .factor_miner import FactorMiner
            from .alpha_discovery import AlphaDiscovery
            from .strategy_generator import StrategyGenerator
            from .backtest_orchestrator import BacktestOrchestrator

            self._components = {
                "scanner": MarketScanner(),
                "opportunity": OpportunityDetector(),
                "hypothesis": HypothesisGenerator(),
                "factor_miner": FactorMiner(),
                "alpha": AlphaDiscovery(),
                "strategy": StrategyGenerator(),
                "backtest": BacktestOrchestrator(),
            }
        return self._components

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def scan_market(
        self,
        universe: Optional[List[str]] = None,
        scan_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Scan market for observations."""
        components = self._get_components()
        self._track("scan")
        return await components["scanner"].scan(universe=universe, scan_types=scan_types)

    async def detect_opportunities(
        self,
        observations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Detect research opportunities from observations."""
        components = self._get_components()
        self._track("opportunity")
        return await components["opportunity"].detect(observations)

    async def generate_hypotheses(
        self,
        opportunities: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate hypotheses from opportunities."""
        components = self._get_components()
        self._track("hypothesis")
        return await components["hypothesis"].generate(opportunities)

    async def discover_factors(
        self,
        hypothesis_id: str,
    ) -> Dict[str, Any]:
        """Mine factors for a hypothesis."""
        components = self._get_components()
        self._track("factor")
        return await components["factor_miner"].mine(hypothesis_id)

    async def discover_alpha(
        self,
        factors: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Discover alpha from factors."""
        components = self._get_components()
        self._track("alpha")
        return await components["alpha"].discover(factors)

    async def generate_strategies(
        self,
        alpha_candidates: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate strategy candidates from alphas."""
        components = self._get_components()
        self._track("strategy")
        return await components["strategy"].generate(alpha_candidates)

    async def run_backtest(
        self,
        strategy_candidate: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run backtest for a strategy candidate."""
        components = self._get_components()
        self._track("backtest")
        return await components["backtest"].run(strategy_candidate)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _track(self, endpoint: str) -> None:
        self._request_count[endpoint] = self._request_count.get(endpoint, 0) + 1

    async def health(self) -> Dict[str, Any]:
        return {
            "started": self._started,
            "requests": dict(self._request_count),
            "components": list(self._components.keys()) if self._components else [],
        }
