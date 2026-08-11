"""
Portfolio Runtime — Lifecycle & Dependency Injection

Bootstraps all multi-strategy portfolio subsystems and wires them
into MultiStrategyPortfolio.

Lifecycle: INIT → CONFIGURE → BOOTSTRAP → ACTIVE → SHUTDOWN
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RuntimeState(str, Enum):
    INIT = "INIT"
    CONFIGURING = "CONFIGURING"
    BOOTSTRAPPING = "BOOTSTRAPPING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    TERMINATED = "TERMINATED"


class PortfolioRuntime:
    """
    Bootstraps and wires all portfolio subsystems in dependency order.
    Injects them into MultiStrategyPortfolio.
    """

    def __init__(
        self,
        runtime_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.runtime_id = runtime_id or f"pr-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self.state = RuntimeState.INIT
        self._portfolio = None
        self._boot_errors: List[Dict[str, Any]] = []

    def configure(self, overrides: Optional[Dict[str, Any]] = None) -> None:
        self.state = RuntimeState.CONFIGURING
        if overrides:
            self.config.update(overrides)

    def bootstrap(self) -> bool:
        self.state = RuntimeState.BOOTSTRAPPING
        self._boot_errors.clear()

        try:
            from .multi_strategy_portfolio import MultiStrategyPortfolio
            from .strategy_registry import StrategyRegistry
            from .strategy_signal_aggregator import StrategySignalAggregator
            from .signal_netting_engine import SignalNettingEngine
            from .position_netting_engine import PositionNettingEngine
            from .portfolio_builder import PortfolioBuilder
            from .portfolio_optimizer import PortfolioOptimizer
            from .risk_aggregator import RiskAggregator
            from .capital_coordinator import CapitalCoordinator
            from .rebalance_engine import RebalanceEngine
            from .orchestration_guard import OrchestrationGuard

            # Foundation
            strategy_registry = StrategyRegistry(config=self.config.get("registry", {}))
            signal_agg = StrategySignalAggregator(registry=strategy_registry)
            signal_netting = SignalNettingEngine()
            position_netting = PositionNettingEngine()
            portfolio_builder = PortfolioBuilder()
            portfolio_optimizer = PortfolioOptimizer()
            risk_aggregator = RiskAggregator(strategy_registry=strategy_registry)
            capital_coordinator = CapitalCoordinator()
            rebalance_engine = RebalanceEngine()
            guard = OrchestrationGuard()

            # Wire into portfolio
            self._portfolio = MultiStrategyPortfolio(
                portfolio_id=self.runtime_id,
                config=self.config,
            )
            self._portfolio._strategy_registry = strategy_registry
            self._portfolio._signal_aggregator = signal_agg
            self._portfolio._signal_netting = signal_netting
            self._portfolio._position_netting = position_netting
            self._portfolio._portfolio_builder = portfolio_builder
            self._portfolio._portfolio_optimizer = portfolio_optimizer
            self._portfolio._risk_aggregator = risk_aggregator
            self._portfolio._capital_coordinator = capital_coordinator
            self._portfolio._rebalance_engine = rebalance_engine
            self._portfolio._guard = guard
            self._portfolio.initialize()

            self.state = RuntimeState.ACTIVE
            return True

        except Exception as e:
            self._boot_errors.append({"phase": "bootstrap", "error": str(e)})
            logger.error(f"Bootstrap failed: {e}")
            return False

    def shutdown(self) -> None:
        if self._portfolio:
            self._portfolio.freeze()
        self.state = RuntimeState.TERMINATED

    @property
    def portfolio(self):
        return self._portfolio

    def get_status(self) -> Dict[str, Any]:
        return {
            "runtime_id": self.runtime_id,
            "state": self.state.value,
            "boot_ok": len(self._boot_errors) == 0,
            "subsystems": {
                "portfolio": self._portfolio is not None,
            },
        }
